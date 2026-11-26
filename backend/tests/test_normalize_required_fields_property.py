"""정규화 필수 필드 필터 속성 테스트 (Property 11).

SerpApi `visual_matches[]` 항목을 `NormalizedResult`로 변환하는
`normalize_visual_matches` 순수 함수를 검증한다. 외부 호출 없이 순수 모듈
(`normalize.py`)만 검증한다(design.md "속성 ↔ 증거" 표의 P11 → normalize
필수 필드 필터 매핑 참조).

Property 11: 정규화 결과는 필수 필드(상품명 title / 상품 이미지 URL image_url /
판매 페이지 URL link)를 모두 보유하며, 셋 중 하나라도 비거나 누락된 입력은
정규화 출력에서 제외된다(Req 9.1, 9.2).

필수 이미지 URL은 `image`가 비거나 없으면 `thumbnail`로 폴백하므로(Req 8.6),
"이미지 필드 보유" 판정은 image/thumbnail 둘 다 비어 있을 때만 누락으로 본다.
기대값(각 입력이 통과해야 하는지)은 입력 딕셔너리에서 직접 파생해 구현과 독립적으로
판정한다. 스킴·중복은 이 속성의 관심사가 아니므로, 통과해야 하는 입력은 항상
유효한 http(s) 스킴과 유일한 링크를 갖도록 생성기에서 보장한다.
"""

from typing import Optional

from hypothesis import given, settings
from hypothesis import strategies as st

from closeller.normalize import normalize_visual_matches

# --- 필수 필드 "비어 있음" 판정(구현과 독립적인 기대값 파생용) ----------------

# 생성기가 쓰는 "비어 있음"에 해당하는 값들. 문자열이 아니거나, 공백만으로 채워진
# 값은 normalize._clean_str 규칙상 빈 문자열로 취급되어 누락과 동일하게 다뤄진다.
_EMPTYISH_VALUES = (
    None,
    "",
    "   ",
    "\t",
    "\n  ",
    123,        # 문자열이 아닌 값 → 빈 문자열로 취급
    [],
    {},
)


def _is_present(value: object) -> bool:
    """필수 필드 값이 "존재"하는지 판정한다(normalize._clean_str와 동일 규칙).

    문자열이면서 양끝 공백 제거 후 비어 있지 않을 때만 존재로 본다. 그 외(None·
    비문자열·공백만)는 누락과 동일하게 False.
    """
    return isinstance(value, str) and value.strip() != ""


def _item_has_image(item: dict) -> bool:
    """항목이 필수 이미지 URL을 갖는지 판정한다(image 우선, thumbnail 폴백)."""
    return _is_present(item.get("image")) or _is_present(item.get("thumbnail"))


def _item_should_pass_required_fields(item: dict) -> bool:
    """항목이 필수 필드 셋을 모두 갖는지 판정한다(기대값 파생).

    셋 중 하나라도 없으면 제외 대상(False). 생성기는 통과 대상 항목에 대해 스킴·
    중복 조건까지 만족시키므로, 이 판정값이 곧 정규화 통과 여부여야 한다.
    """
    return (
        _is_present(item.get("title"))
        and _is_present(item.get("link"))
        and _item_has_image(item)
    )


# --- 생성기(generator): 필수 필드 존재/누락 공간을 지능적으로 구성한다 --------

# 존재하는(유효한) 필드 값. 양끝 공백이 있어도 strip 후 내용이 남도록 구성한다.
_present_titles = st.sampled_from(
    ("빈티지 데님 자켓", "Nike Tee", " 가죽 지갑 ", "Acne Studios Scarf", "맨투맨"),
)
_present_images = st.sampled_from(
    (
        "https://img.example.com/a.jpg",
        "http://cdn.example.org/p/42.png",
        "https://example.net/i/x.webp",
    ),
)
# 통과 대상 링크는 반드시 http(s)여야 한다(스킴 필터는 이 속성의 관심사가 아님).
_present_links = st.sampled_from(
    (
        "https://shop.example.com/p/1",
        "http://example.org/item/2",
        "https://store.example.net/goods/3",
        "https://example.co.kr/a/4",
    ),
)

# 비어있거나 누락에 해당하는 값(명시적 None 포함).
_emptyish = st.sampled_from(_EMPTYISH_VALUES)


@st.composite
def _title_value(draw: st.DrawFn, present: bool) -> object:
    return draw(_present_titles) if present else draw(_emptyish)


@st.composite
def _link_value(draw: st.DrawFn, present: bool) -> object:
    return draw(_present_links) if present else draw(_emptyish)


@st.composite
def _image_fields(draw: st.DrawFn, present: bool) -> dict:
    """image/thumbnail 두 필드를 생성한다.

    present=True면 image 또는 thumbnail 중 적어도 하나는 유효(폴백 포함). present=
    False면 둘 다 비어 있어 이미지 누락이 되도록 한다.
    """
    fields: dict = {}
    if present:
        mode = draw(st.sampled_from(("image", "thumbnail", "both")))
        if mode in ("image", "both"):
            fields["image"] = draw(_present_images)
        else:
            # image는 비워 폴백을 강제하고, thumbnail만 유효하게 둔다.
            if draw(st.booleans()):
                fields["image"] = draw(_emptyish)
        if mode in ("thumbnail", "both"):
            fields["thumbnail"] = draw(_present_images)
    else:
        # 둘 다 비어있거나 누락. 일부는 키 자체를 생략한다.
        if draw(st.booleans()):
            fields["image"] = draw(_emptyish)
        if draw(st.booleans()):
            fields["thumbnail"] = draw(_emptyish)
    return fields


@st.composite
def _item(draw: st.DrawFn) -> dict:
    """단일 visual_matches 항목을 생성한다.

    각 필수 필드의 존재 여부를 독립적으로 뽑아 통과/제외 양쪽을 폭넓게 탐색한다.
    통과하려면 셋 다 존재해야 하므로, 전부 존재일 확률을 적당히 높여 통과 사례도
    충분히 생성되게 한다. 키 자체를 생략하는 경우(누락)도 섞는다.
    """
    title_present = draw(st.booleans())
    link_present = draw(st.booleans())
    image_present = draw(st.booleans())

    item: dict = {}

    # title: 존재/비어있음/키 누락 중 선택.
    if title_present:
        item["title"] = draw(_title_value(present=True))
    elif draw(st.booleans()):
        item["title"] = draw(_title_value(present=False))
    # else: title 키 자체를 생략(누락)

    # link: 존재/비어있음/키 누락 중 선택.
    if link_present:
        item["link"] = draw(_link_value(present=True))
    elif draw(st.booleans()):
        item["link"] = draw(_link_value(present=False))

    # image/thumbnail.
    item.update(draw(_image_fields(present=image_present)))

    # 부가 필드(선택). 필수 필드 판정에 영향을 주지 않아야 한다.
    if draw(st.booleans()):
        item["position"] = draw(st.integers(min_value=1, max_value=50))
    if draw(st.booleans()):
        item["exact_matches"] = draw(st.booleans())

    return item


@st.composite
def _matches_with_unique_links(draw: st.DrawFn) -> list[dict]:
    """항목 리스트를 생성하되, 통과 가능한 항목끼리는 서로 다른 링크를 갖게 한다.

    중복 제거(Req 9.6)는 이 속성의 관심사가 아니므로, 같은 정규화 링크로 인해
    통과 대상 항목이 제거되어 "통과 여부 == 필수 필드 보유 여부" 불변식이 흔들리는
    것을 막는다. 통과 대상에는 리스트 인덱스를 경로에 섞어 유일한 링크를 부여한다.
    제외 대상(필수 필드 누락)은 그대로 둔다.
    """
    items = draw(st.lists(_item(), min_size=0, max_size=8))
    for idx, item in enumerate(items):
        if _item_should_pass_required_fields(item):
            # 유일 링크 부여(스킴은 http(s) 유지). 통과 여부는 유지된다.
            item["link"] = f"https://example.com/unique/{idx}"
    return items


# --- 속성 테스트 -------------------------------------------------------------


# Feature: closeller-mvp, Property 11: 정규화 결과는 필수 필드 모두 보유, 누락 시 제외
@settings(max_examples=200)
@given(items=_matches_with_unique_links())
def test_every_result_has_all_required_fields(items: list[dict]) -> None:
    """정규화 출력의 모든 결과는 필수 필드 셋을 비어있지 않게 보유한다(Req 9.1, 9.2).

    title·link·image_url 모두 문자열이면서 strip 후 비어 있지 않아야 한다.
    """
    results = normalize_visual_matches(items)
    for result in results:
        assert _is_present(result.title)
        assert _is_present(result.link)
        assert _is_present(result.image_url)


# Feature: closeller-mvp, Property 11: 정규화 결과는 필수 필드 모두 보유, 누락 시 제외
@settings(max_examples=200)
@given(items=_matches_with_unique_links())
def test_missing_required_field_items_are_excluded(items: list[dict]) -> None:
    """필수 필드가 하나라도 없는 입력 항목은 정규화 출력에서 제외된다(Req 9.2).

    출력에 남은 결과 수는 입력 중 "필수 필드를 모두 보유한" 항목 수와 정확히
    일치해야 한다. 통과 대상에는 생성기가 유일 링크·유효 스킴을 보장하므로,
    통과 여부가 곧 필수 필드 보유 여부와 일치한다.
    """
    expected_pass = sum(
        1 for item in items if _item_should_pass_required_fields(item)
    )
    results = normalize_visual_matches(items)
    assert len(results) == expected_pass


# Feature: closeller-mvp, Property 11: 정규화 결과는 필수 필드 모두 보유, 누락 시 제외
@settings(max_examples=200)
@given(item=_item())
def test_single_item_pass_iff_all_required_present(item: dict) -> None:
    """단일 항목 기준: 정규화 통과 여부는 필수 필드 보유 여부와 동치다(Req 9.2).

    스킴·중복을 배제하기 위해, 통과 대상으로 판정된 항목에는 유효한 유일 링크를
    부여한 뒤 비교한다. 제외 대상은 그대로 두어 "누락 시 제외"를 확인한다.
    """
    if _item_should_pass_required_fields(item):
        item = {**item, "link": "https://example.com/p/single"}
        results = normalize_visual_matches([item])
        assert len(results) == 1
        assert _is_present(results[0].title)
        assert _is_present(results[0].link)
        assert _is_present(results[0].image_url)
    else:
        assert normalize_visual_matches([item]) == []


# Feature: closeller-mvp, Property 11: 정규화 결과는 필수 필드 모두 보유, 누락 시 제외
@settings(max_examples=100)
@given(
    title=st.one_of(st.none(), _present_titles, _emptyish),
    link_present=st.booleans(),
    image_present=st.booleans(),
)
def test_each_missing_field_alone_causes_exclusion(
    title: object, link_present: bool, image_present: bool
) -> None:
    """어느 한 필수 필드만 비어도 제외된다(Req 9.2, 필드별 독립 확인).

    title/link/image 중 정확히 어떤 조합이 비는지에 따라 통과 여부가 달라지며,
    셋이 모두 존재할 때만 1건이 남는다. 통과 경로에서는 유효 스킴·단일 항목이라
    스킴·중복의 영향이 없다.
    """
    item: dict = {}
    if title is not None or isinstance(title, str):
        item["title"] = title
    if link_present:
        item["link"] = "https://example.com/p/combo"
    if image_present:
        item["image"] = "https://img.example.com/combo.jpg"

    results = normalize_visual_matches([item])
    should_pass = _is_present(item.get("title")) and link_present and image_present
    assert len(results) == (1 if should_pass else 0)
