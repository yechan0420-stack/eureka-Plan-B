"""가격 미확인 처리 속성 테스트 (Property 13).

SerpApi `visual_matches[]` 항목을 `NormalizedResult`로 변환하는
`normalize_visual_matches` 순수 함수를 검증한다. 외부 호출 없이 순수 모듈
(`normalize.py`)만 검증한다(design.md "속성 ↔ 증거" 표의 P13 →
`test_normalize_price_missing.py` 매핑 참조).

Property 13: 가격이 없거나 숫자로 파싱할 수 없는 결과에 대해, 정규화 결과의 표시
가격은 "미확인"(PRICE_UNKNOWN), 정렬값(`price_sort_value`)은 None이며, 해당 결과는
제외되지 않고 그대로 유지된다(Req 9.5, 9.9).

normalize._parse_price / _coerce_float 규칙(공식 필드만 사용):
- 정렬값은 오직 `price.extracted_value`가 숫자로 파싱될 때만 산출된다. bool은 제외,
  숫자(int/float)와 공백 제거 후 float 변환 가능한 문자열만 파싱되며, NaN·무한대는
  정렬값으로 부적합해 제외된다.
- `extracted_value`가 없거나 숫자로 파싱할 수 없으면 표시 가격은 "미확인", 정렬값은
  None이다. 이때도 결과 자체는 유지된다(응답에 없는 값을 지어내지 않되 결과를
  임의로 버리지도 않음, Req 9.5, 9.9).
- price 객체가 dict가 아니거나(없음·비정상 형태) 아예 부재여도 동일하게 "미확인"+None.

본 속성의 관심사는 "가격 미확인 처리·결과 유지"이므로, 각 항목은 필수 필드
(title/image/link)와 http(s) 스킴·유일 링크를 갖도록 생성해 필수 필드 필터(Req 9.2)·
스킴(Req 9.8)·중복(Req 9.6)의 영향을 배제한다. 기대값은 입력 price 객체에서 직접
파생해 구현과 독립적으로 판정한다.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from closeller.normalize import PRICE_UNKNOWN, normalize_visual_matches

# --- 구현과 독립적인 기대값 파생 헬퍼 ----------------------------------------


def _parses_as_number(value: object) -> bool:
    """값이 정렬용 숫자로 파싱 가능한지 판정한다(normalize._coerce_float와 동일 규칙).

    bool은 제외, 숫자(int/float)와 공백 제거 후 float 변환 가능한 문자열만 True.
    NaN·무한대는 정렬값으로 부적합하므로 False.
    """
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        result = float(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return False
        try:
            result = float(text)
        except ValueError:
            return False
    else:
        return False
    if result != result or result in (float("inf"), float("-inf")):
        return False
    return True


def _price_is_missing(price_obj: object) -> bool:
    """가격이 "없거나 숫자로 파싱할 수 없는" 경우인지 판정한다(구현과 독립).

    price 객체가 dict가 아니면(부재·비정상) 가격 없음. dict이면 오직
    `extracted_value`가 숫자로 파싱 가능한지로만 정렬값 산출 가능 여부가 결정되므로,
    파싱 불가일 때 가격 미확인으로 본다.
    """
    if not isinstance(price_obj, dict):
        return True
    return not _parses_as_number(price_obj.get("extracted_value"))


# --- 생성기(generator): "가격 없음·파싱 불가" 입력 공간을 지능적으로 구성한다 -

# 숫자로 파싱할 수 없는 extracted_value 후보.
_unparseable_extracted = st.one_of(
    st.none(),
    st.just(""),
    st.sampled_from(("가격문의", "N/A", "문의", "price", "--", "  ")),
    st.booleans(),                  # bool은 명시적으로 숫자에서 제외된다
    st.sampled_from(("NaN", "inf", "-inf")),  # 특수값 문자열 → float 부적합
    st.floats(allow_nan=True, allow_infinity=True).filter(
        lambda f: f != f or f in (float("inf"), float("-inf"))
    ),
    st.lists(st.integers(), max_size=2),  # 비숫자·비문자열 타입
)

# 표시용 value 후보: value가 있어도 extracted_value가 없으면 "미확인"이어야 한다.
_value_candidate = st.one_of(
    st.none(),
    st.just(""),
    st.sampled_from(("₩120,000", "$1,299.00", "가격문의")),
    st.integers(min_value=0, max_value=1_000_000),
)

# 통화 후보: 통화가 보존되더라도 가격 미확인 판정에는 영향을 주지 않아야 한다.
_currency_candidate = st.one_of(
    st.none(),
    st.just(""),
    st.sampled_from(("KRW", "USD", "EUR", "₩", "$")),
)


@st.composite
def _price_missing_object(draw: st.DrawFn) -> object:
    """정렬용 숫자 가격이 없는 price 입력을 생성한다(또는 price 자체 부재).

    세 갈래로 가격 없음 경로를 폭넓게 탐색한다:
      1) price 객체 자체가 dict가 아님(None·숫자·짧은 문자열 등 비정상 형태).
      2) dict이지만 extracted_value 키를 아예 생략(정렬값 산출 불가).
      3) dict이며 extracted_value가 존재하나 숫자로 파싱 불가(빈 문자열·비숫자 등).
    어느 경로든 value·currency는 다양하게 섞어 "미확인·결과 유지"가 가격 외
    필드와 무관하게 성립하는지 확인한다.
    """
    mode = draw(st.sampled_from(("non_dict", "no_extracted", "unparseable_extracted")))

    if mode == "non_dict":
        return draw(st.one_of(st.none(), st.integers(), st.text(max_size=3)))

    price_obj: dict = {}
    if draw(st.booleans()):
        price_obj["value"] = draw(_value_candidate)
    if draw(st.booleans()):
        price_obj["currency"] = draw(_currency_candidate)

    if mode == "unparseable_extracted":
        price_obj["extracted_value"] = draw(_unparseable_extracted)
    # no_extracted: extracted_value 키 생략

    return price_obj


@st.composite
def _item_with_missing_price(draw: st.DrawFn, index: int) -> dict:
    """필수 필드를 갖춘 유효 항목을 생성하되, price는 "가격 없음"만 생성한다.

    title/image는 유효하게 고정하고 link는 인덱스로 유일하게 만들어 필수 필드·스킴·
    중복의 영향을 배제한다. 가격 미확인 처리·결과 유지만 관심사로 남긴다.
    """
    return {
        "title": draw(st.sampled_from(("빈티지 자켓", "Nike Tee", "가죽 지갑"))),
        "image": "https://img.example.com/a.jpg",
        "link": f"https://example.com/p/{index}",
        "price": draw(_price_missing_object()),
    }


@st.composite
def _items_missing_price(draw: st.DrawFn) -> list[dict]:
    """가격 없는 유효 항목 리스트를 생성한다(각 항목 유일 링크)."""
    size = draw(st.integers(min_value=1, max_value=8))
    return [draw(_item_with_missing_price(index=i)) for i in range(size)]


# --- 속성 테스트 -------------------------------------------------------------


# Feature: closeller-mvp, Property 13: 가격 없으면 "미확인"·priceSortValue null·결과 유지
@settings(max_examples=200)
@given(items=_items_missing_price())
def test_missing_price_yields_unknown_null_and_result_retained(items: list[dict]) -> None:
    """가격이 없는 모든 항목은 "미확인"·정렬값 None으로 변환되고 전부 유지된다.

    링크가 유일하고 필수 필드가 모두 존재하므로, 가격 없음만으로는 어떤 결과도
    제외되지 않아야 한다. 즉 출력 개수는 입력 개수와 동일하고, 각 결과의 price는
    PRICE_UNKNOWN, price_sort_value는 None이다(Req 9.5, 9.9).
    """
    results = normalize_visual_matches(items)

    # 가격 없음은 제외 사유가 아니다 → 모든 항목이 1:1로 유지된다.
    assert len(results) == len(items)

    result_links = {result.link for result in results}
    assert result_links == {item["link"] for item in items}

    for result in results:
        assert result.price == PRICE_UNKNOWN
        assert result.price_sort_value is None


# Feature: closeller-mvp, Property 13: 가격 없으면 "미확인"·priceSortValue null·결과 유지
@settings(max_examples=100)
@given(price_obj=_price_missing_object())
def test_single_missing_price_is_unknown_with_null_sort_value(price_obj: object) -> None:
    """단일 항목 기준으로, 가격이 없으면 "미확인"+정렬값 None이며 결과는 유지된다.

    구현과 독립적으로 입력 price 객체에서 "가격 없음"을 판정하고, 그 경우 결과가
    정확히 1건 유지되며 표시 가격이 PRICE_UNKNOWN, 정렬값이 None임을 확인한다
    (Req 9.5, 9.9).
    """
    assert _price_is_missing(price_obj)  # 생성기가 보장하는 전제의 명시적 검증

    item = {
        "title": "테스트 상품",
        "image": "https://img.example.com/a.jpg",
        "link": "https://example.com/p/single",
        "price": price_obj,
    }
    results = normalize_visual_matches([item])

    # 가격 없음에도 결과는 버려지지 않고 유지된다.
    assert len(results) == 1
    result = results[0]
    assert result.price == PRICE_UNKNOWN
    assert result.price_sort_value is None


# Feature: closeller-mvp, Property 13: 가격 없으면 "미확인"·priceSortValue null·결과 유지
@settings(max_examples=100)
@given(price_obj=_price_missing_object())
def test_unknown_price_and_null_sort_value_are_consistent(price_obj: object) -> None:
    """가격이 없을 때 "미확인"과 정렬값 None은 항상 함께 성립한다.

    가격 미확인이면 정렬값은 반드시 None이어야 한다(미확인인데 정렬 숫자값이 남아
    있으면 안 된다). 값을 지어내지 않는다는 규칙과 정렬 안정성 전제를 보강한다
    (Req 9.5, 9.9).
    """
    item = {
        "title": "테스트 상품",
        "image": "https://img.example.com/a.jpg",
        "link": "https://example.com/p/consistency",
        "price": price_obj,
    }
    results = normalize_visual_matches([item])
    assert len(results) == 1
    result = results[0]

    if result.price == PRICE_UNKNOWN:
        assert result.price_sort_value is None
