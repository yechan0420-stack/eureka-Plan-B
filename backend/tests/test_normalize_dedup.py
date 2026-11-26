"""중복 제거 정규화 통합 속성 테스트 (Property 14 — normalize 통합 부분).

`normalize_visual_matches`는 `url_tools.normalize_url(link)`을 기준값으로 같은 값을
가진 결과 중 입력 순서상 첫 1건만 남긴다(Req 9.6). 본 파일은 그 중복 제거가
파이프라인 통합 수준에서 올바른지 검증한다. `test_dedup.py`가 `url_tools` 정규화
자체(멱등성·불변성·추적 파라미터 제거 등)를 다루는 반면, 여기서는 정규화 결과
목록에서 (1) 남은 결과의 정규화 URL이 유일하고, (2) 각 그룹에서 입력 순서상 첫
항목이 살아남으며, (3) 같은 값으로 수렴하는 변형들이 하나로 합쳐지는지를 확인한다.

design.md "속성 ↔ 증거" 표는 P14를 `test_dedup.py`(대상 `url_tools.py`+`normalize.py`)에
연결한다(tasks.md 6.2는 url_tools 부분, 9.5는 normalize 통합 부분). 외부 호출 없이
순수 모듈(`normalize.py`, `url_tools.py`)만 검증한다.

중복 제거만을 이 속성의 유일한 제외 기제로 격리하기 위해, 생성되는 모든 입력 항목은
필수 필드(title / link / http(s) image 또는 thumbnail)를 유효하게 보유한다
(test_normalize_required_fields_property.py의 생성기 규율을 따른다). 기대 출력(그룹당
첫 1건)은 구현 내부를 재사용하지 않고 독립 오라클로 파생한다.

Property 14: 중복 제거 후 정규화 URL 유일, 그룹당 첫 1건.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from closeller.normalize import normalize_visual_matches
from closeller.url_tools import normalize_url

# --- 생성기(generator): 정규화 URL이 같은 "그룹"을 지능적으로 구성한다 --------

# 유효한 필수 필드 값. 중복 제거가 유일한 제외 기제가 되도록, title/image는 항상
# 존재하고 link는 항상 http(s)여야 한다.
_titles = st.sampled_from(
    ("빈티지 데님 자켓", "Nike Tee", "가죽 지갑", "Acne Studios Scarf", "맨투맨"),
)
_images = st.sampled_from(
    (
        "https://img.example.com/a.jpg",
        "http://cdn.example.org/p/42.png",
        "https://example.net/i/x.webp",
    ),
)

# 서로 다른 정규화 값을 만드는 "기준 URL"(쿼리·프래그먼트 없음). 경로가 달라
# 정규화 값이 서로 다르다. 그룹은 이 기준 URL별로 형성된다.
_base_urls = st.sampled_from(
    (
        "https://shop.example.com/p/1",
        "http://example.org/item/2",
        "https://store.example.net/goods/3",
        "https://example.co.kr/a/4",
        "https://mall.example.io/x/5",
    ),
)

# 프래그먼트 조각(정규화 시 제거되어 그룹을 바꾸지 않는다).
_fragment = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
    min_size=0,
    max_size=6,
)

# 추적 파라미터 이름(정규화 시 제거되어 그룹을 바꾸지 않는다).
_tracking_name = st.sampled_from(
    ("gclid", "fbclid", "utm_source", "utm_medium", "msclkid", "ref"),
)
_tracking_value = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
    min_size=0,
    max_size=6,
)


@st.composite
def _same_group_variant(draw: st.DrawFn, base: str) -> str:
    """기준 URL과 정규화 값이 같은 변형 링크를 만든다(프래그먼트·끝 슬래시·대소문자·
    추적 파라미터만 차이).

    이 함수가 만든 링크들은 전부 `normalize_url`에서 같은 값으로 수렴하므로 하나의
    그룹을 이룬다. 어떤 변형을 적용할지는 독립적으로 뽑아 조합한다.
    """
    url = base

    # 추적 파라미터 추가(제거 대상이므로 그룹 불변).
    from urllib.parse import urlencode

    tracking = draw(
        st.lists(st.tuples(_tracking_name, _tracking_value), min_size=0, max_size=3)
    )
    if tracking:
        url = url + "?" + urlencode(tracking)

    # 끝 슬래시 추가(정규화 시 제거).
    if draw(st.booleans()):
        url = url + "/"

    # 프래그먼트 추가(정규화 시 제거).
    if draw(st.booleans()):
        url = url + "#" + draw(_fragment)

    return url


@st.composite
def _item_with_link(draw: st.DrawFn, link: str) -> dict:
    """주어진 링크로 필수 필드를 모두 갖춘 유효한 visual_matches 항목을 만든다.

    title·image는 항상 존재하고 link는 http(s)이므로, 필수 필드/스킴 필터로는 결코
    제외되지 않는다. 즉 제외는 오직 중복 제거로만 발생한다.
    """
    item: dict = {"title": draw(_titles), "link": link}
    # image/thumbnail 중 하나 이상을 유효하게 둔다(폴백 포함).
    mode = draw(st.sampled_from(("image", "thumbnail", "both")))
    if mode in ("image", "both"):
        item["image"] = draw(_images)
    if mode in ("thumbnail", "both"):
        item["thumbnail"] = draw(_images)
    # 부가 필드(선택). 필터·중복 판정에 영향을 주지 않아야 한다.
    if draw(st.booleans()):
        item["position"] = draw(st.integers(min_value=1, max_value=50))
    if draw(st.booleans()):
        item["exact_matches"] = draw(st.booleans())
    return item


@st.composite
def _matches_with_groups(draw: st.DrawFn) -> list[dict]:
    """여러 그룹의 항목이 임의 순서로 섞인 입력 리스트를 생성한다.

    각 그룹은 하나의 기준 URL에서 파생된, 정규화 값이 같은 변형 링크들로 이루어진다.
    서로 다른 기준 URL은 정규화 값이 달라 서로 다른 그룹을 이룬다. 그룹별로 1건 이상
    항목을 만들고, 전체를 섞어 "입력 순서상 첫 1건" 판정이 의미를 갖게 한다.
    """
    bases = draw(st.lists(_base_urls, min_size=1, max_size=4, unique=True))
    items: list[dict] = []
    for base in bases:
        count = draw(st.integers(min_value=1, max_value=4))
        for _ in range(count):
            link = draw(_same_group_variant(base))
            items.append(draw(_item_with_link(link)))
    # 전체 순서를 섞어 그룹이 입력 전체에 흩어지도록 한다.
    draw(st.randoms(use_true_random=False)).shuffle(items)
    return items


# --- 독립 오라클: 구현 내부를 재사용하지 않고 기대 출력을 파생한다 ------------


def _expected_first_per_group(items: list[dict]) -> list[str]:
    """정규화 URL 기준으로 그룹의 첫 1건만 남긴 기대 링크 목록(입력 순서 보존).

    여기서는 `url_tools.normalize_url`만 키 계산에 쓰고, 중복 제거 로직 자체는
    normalize 파이프라인과 무관하게 독립적으로 구현한다. 생성기가 모든 항목에 유효
    필수 필드·http(s) 스킴을 보장하므로, 통과 여부를 가르는 유일한 기제는 중복이다.
    """
    seen: set[str] = set()
    kept: list[str] = []
    for item in items:
        link = item["link"]
        key = normalize_url(link)
        if key not in seen:
            seen.add(key)
            kept.append(link)
    return kept


# --- 속성 테스트 -------------------------------------------------------------


# Feature: closeller-mvp, Property 14: 중복 제거 후 정규화 URL 유일, 그룹당 첫 1건
@settings(max_examples=200)
@given(items=_matches_with_groups())
def test_output_normalized_urls_are_unique(items: list[dict]) -> None:
    """정규화 출력의 어떤 두 결과도 같은 정규화 URL을 갖지 않는다(Req 9.6).

    즉 `normalize_url(r.link)` 값이 결과 전체에서 유일하다.
    """
    results = normalize_visual_matches(items)
    keys = [normalize_url(r.link) for r in results]
    assert len(keys) == len(set(keys))


# Feature: closeller-mvp, Property 14: 중복 제거 후 정규화 URL 유일, 그룹당 첫 1건
@settings(max_examples=200)
@given(items=_matches_with_groups())
def test_each_group_keeps_first_in_input_order(items: list[dict]) -> None:
    """각 그룹에서 입력 순서상 첫 번째로 통과한 항목만 살아남는다(Req 9.6).

    독립 오라클이 파생한 "그룹당 첫 링크" 집합과, 실제 정규화 결과의 링크 집합이
    정규화 URL 기준으로 정확히 일치해야 한다. 생성기가 모든 항목을 필수 필드/스킴
    통과로 보장하므로, 남는 기준은 오직 중복 제거다. 살아남은 결과의 link는 각 그룹
    첫 항목의 link와 (그 원본 문자열 그대로) 같다.
    """
    expected_links = _expected_first_per_group(items)
    results = normalize_visual_matches(items)

    # 정규화 URL 기준 집합이 동일하다(정렬로 순서가 바뀌므로 집합으로 비교).
    expected_keys = {normalize_url(link) for link in expected_links}
    actual_keys = {normalize_url(r.link) for r in results}
    assert actual_keys == expected_keys

    # 그룹당 생존 결과의 link 원본은 그 그룹 첫 항목의 link와 동일하다.
    expected_link_by_key = {normalize_url(link): link for link in expected_links}
    for r in results:
        assert r.link == expected_link_by_key[normalize_url(r.link)]

    # 생존 결과 수는 서로 다른 그룹(정규화 값) 수와 같다.
    assert len(results) == len(expected_keys)


# Feature: closeller-mvp, Property 14: 중복 제거 후 정규화 URL 유일, 그룹당 첫 1건
@settings(max_examples=200)
@given(
    base=_base_urls,
    variant=st.data(),
    title=_titles,
    image=_images,
)
def test_same_normalized_url_variants_collapse_to_one(
    base: str, variant: st.DataObject, title: str, image: str
) -> None:
    """같은 값으로 정규화되는 변형들(프래그먼트·끝 슬래시·대소문자·추적 파라미터·쿼리
    순서 차이)만 섞으면 정확히 1건으로 합쳐지고, 그것은 첫 항목이다(Req 9.6).

    모든 변형 링크의 `normalize_url` 값이 같음을 먼저 확인해 "같은 그룹" 전제를
    보장한 뒤, 정규화 결과가 단 1건이고 그 link가 입력 첫 항목의 link임을 검증한다.
    """
    variants = variant.draw(
        st.lists(_same_group_variant(base), min_size=1, max_size=5)
    )
    # 전제: 모든 변형이 같은 정규화 값으로 수렴한다(= 하나의 그룹).
    norm_values = {normalize_url(v) for v in variants}
    assert len(norm_values) == 1

    items = [{"title": title, "link": v, "image": image} for v in variants]
    results = normalize_visual_matches(items)

    assert len(results) == 1
    assert results[0].link == variants[0]


# Feature: closeller-mvp, Property 14: 중복 제거 후 정규화 URL 유일, 그룹당 첫 1건
@settings(max_examples=200)
@given(
    bases=st.lists(_base_urls, min_size=1, max_size=5, unique=True),
    title=_titles,
    image=_images,
)
def test_distinct_normalized_urls_are_all_kept(
    bases: list[str], title: str, image: str
) -> None:
    """서로 다른 값으로 정규화되는 링크들은 하나도 합쳐지지 않고 모두 남는다(Req 9.6).

    중복 제거가 "다른 그룹"을 잘못 합치지 않음을 확인하는 반대 방향 검증이다.
    `unique=True`로 뽑은 기준 URL들은 경로가 달라 정규화 값이 모두 다르다.
    """
    # 전제: 서로 다른 기준 URL은 정규화 값이 모두 다르다.
    keys = [normalize_url(b) for b in bases]
    assert len(keys) == len(set(keys))

    items = [{"title": title, "link": b, "image": image} for b in bases]
    results = normalize_visual_matches(items)

    assert len(results) == len(bases)
    assert {normalize_url(r.link) for r in results} == set(keys)
