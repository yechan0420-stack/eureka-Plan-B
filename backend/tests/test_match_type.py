"""동일/유사 유형 구분 속성 테스트 (Property 18).

SerpApi `visual_matches[]` 항목을 `NormalizedResult`로 변환하는
`normalize_visual_matches` 순수 함수의 유형(match_type) 분류를 검증한다. 외부
호출 없이 순수 모듈(`normalize.py`)만 검증한다(design.md "속성 ↔ 증거" 표의
P18 → test_match_type 매핑 참조).

Property 18: 동일/유사 유형은 `exact_matches`로 결정된다. 어떤 visual_matches
항목이든 `exact_matches`가 파이썬 불리언 True일 때만 "동일 상품 후보"(동일 상품
후보)로 분류되고, 그 외(None·누락·False·비불리언)는 "유사 상품"으로 분류된다
(Req 11.1, 11.2).

Req 11.1: 상품 식별자 일치 또는 상품 페이지 직접 링크를 가리키는 결과 유형은
"동일 상품 후보"로 분류한다. 본 정규화 파이프라인은 그 근거를 SerpApi
`exact_matches == True`로 받는다.
Req 11.2: "동일 상품 후보"로 볼 근거가 없으면 "유사 상품"으로 분류한다.

기대값(각 항목이 가져야 할 유형)은 입력 딕셔너리의 `exact_matches` 값에서
직접 파생해 구현과 독립적으로 판정한다. 필수 필드·스킴·중복은 이 속성의 관심사가
아니므로, 각 항목은 항상 유효한 상품명·유일한 http(s) 링크·유효한 이미지를 갖도록
생성기에서 보장한다(그래야 생성한 모든 항목이 정규화를 통과해 유형 비교가 가능하다).
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from closeller.match_grade import MATCH_TYPE_IDENTICAL, MATCH_TYPE_SIMILAR
from closeller.normalize import normalize_visual_matches


def _expected_match_type(exact_matches_value: object) -> str:
    """`exact_matches` 값에서 기대 유형을 구현과 독립적으로 파생한다.

    파이썬 불리언 True일 때만 "동일 상품 후보", 그 외(None·누락·False·비불리언)는
    모두 "유사 상품"이다(Req 11.1, 11.2). `is True` 판정이라 1 같은 truthy 값도
    "동일 상품 후보"가 되지 않는다.
    """
    if exact_matches_value is True:
        return MATCH_TYPE_IDENTICAL
    return MATCH_TYPE_SIMILAR


# --- 생성기(generator): exact_matches 전체 입력 공간을 탐색한다 --------------

# exact_matches 후보값. True / False / None 외에, 키 누락과 비불리언(문자열·정수)을
# 섞어 "오직 파이썬 불리언 True만 동일 상품 후보"임을 증명한다. 센티넬 _MISSING은
# 키 자체를 생략하는 경우를 표현한다.
_MISSING = object()

_exact_matches_values = st.sampled_from(
    (
        True,       # 유일하게 "동일 상품 후보"가 되는 값
        False,      # "유사 상품"
        None,       # "유사 상품"
        _MISSING,   # 키 누락 → "유사 상품"
        "true",     # 비불리언(truthy 문자열) → "유사 상품"
        "True",
        1,          # 비불리언 정수(truthy) → "유사 상품"
        0,          # 비불리언 정수(falsy) → "유사 상품"
    ),
)


@st.composite
def _item(draw: st.DrawFn, idx: int) -> dict:
    """정규화를 반드시 통과하는 단일 항목을 생성하되 exact_matches만 변주한다.

    필수 필드(title/link/image)는 항상 유효하게 채우고, 링크는 인덱스를 섞어
    유일하게 만들어 중복 제거(Req 9.6)로 제거되지 않게 한다. position은 유형
    분류와 무관하므로 선택적으로만 넣는다. 핵심 변주 대상은 exact_matches다.
    """
    item: dict = {
        "title": draw(
            st.sampled_from(("빈티지 데님 자켓", "Nike Tee", "가죽 지갑", "맨투맨")),
        ),
        "link": f"https://example.com/unique/{idx}",
        "image": "https://img.example.com/a.jpg",
    }

    exact = draw(_exact_matches_values)
    if exact is not _MISSING:
        item["exact_matches"] = exact

    # position은 유형 분류에 영향을 주지 않는다. 일부 항목에만 부여해 무관함을 보인다.
    if draw(st.booleans()):
        item["position"] = draw(st.integers(min_value=1, max_value=50))

    return item


@st.composite
def _items(draw: st.DrawFn) -> list[dict]:
    """정규화를 모두 통과하는 유일 링크 항목들의 리스트를 생성한다.

    각 항목은 유효 필수 필드·유일 링크를 가지므로 입력 수 == 출력 수가 되며,
    출력 결과의 유형을 입력의 exact_matches와 1:1로 대응해 비교할 수 있다.
    """
    size = draw(st.integers(min_value=0, max_value=8))
    return [draw(_item(idx=i)) for i in range(size)]


# --- 속성 테스트 -------------------------------------------------------------


# Feature: closeller-mvp, Property 18: 동일/유사 유형은 exact_matches로 결정
@settings(max_examples=200)
@given(items=_items())
def test_match_type_decided_by_exact_matches(items: list[dict]) -> None:
    """정규화 결과의 유형은 입력 exact_matches와 1:1로 대응한다(Req 11.1, 11.2).

    모든 항목이 필수 필드·유일 링크를 갖춰 정규화를 통과하므로, 입력과 출력은
    같은 순서·같은 개수로 대응된다. 각 결과의 match_type은 대응 입력의
    exact_matches에서 파생한 기대값과 정확히 일치해야 한다.
    """
    results = normalize_visual_matches(items)

    # 전부 통과 대상이므로 개수가 보존된다.
    assert len(results) == len(items)

    # 링크를 기준으로 입력과 출력을 짝지어 유형을 비교한다(정렬로 순서가 바뀌어도 안전).
    expected_by_link = {
        item["link"]: _expected_match_type(item.get("exact_matches", _MISSING))
        for item in items
    }
    for result in results:
        assert result.match_type == expected_by_link[result.link]
        # 유형 문자열은 두 상수 중 하나여야 한다.
        assert result.match_type in (MATCH_TYPE_IDENTICAL, MATCH_TYPE_SIMILAR)


# Feature: closeller-mvp, Property 18: 동일/유사 유형은 exact_matches로 결정
@settings(max_examples=100)
@given(exact=_exact_matches_values)
def test_identical_only_for_boolean_true(exact: object) -> None:
    """오직 파이썬 불리언 True만 "동일 상품 후보"가 된다(Req 11.1, 11.2).

    단일 항목으로 exact_matches 전체 입력 공간을 훑어, True일 때만
    "동일 상품 후보"이고 나머지(None·누락·False·비불리언 truthy/falsy)는 모두
    "유사 상품"임을 확인한다.
    """
    item: dict = {
        "title": "테스트 상품",
        "link": "https://example.com/p/single",
        "image": "https://img.example.com/x.jpg",
    }
    if exact is not _MISSING:
        item["exact_matches"] = exact

    results = normalize_visual_matches([item])
    assert len(results) == 1

    expected = _expected_match_type(item.get("exact_matches", _MISSING))
    assert results[0].match_type == expected
    if exact is True:
        assert results[0].match_type == MATCH_TYPE_IDENTICAL
    else:
        assert results[0].match_type == MATCH_TYPE_SIMILAR
