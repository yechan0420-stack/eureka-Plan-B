"""가격 값·통화 보존 속성 테스트 (Property 12).

SerpApi `visual_matches[]` 항목을 `NormalizedResult`로 변환하는
`normalize_visual_matches` 순수 함수를 검증한다. 외부 호출 없이 순수 모듈
(`normalize.py`)만 검증한다(design.md "속성 ↔ 증거" 표의 P12 → normalize
가격 보존 매핑 참조).

Property 12: 가격·통화 정보가 있는 결과에 대해, 정규화 결과의 가격 값과 통화는
SerpApi 응답 값과 동일하게 보존되며 임의로 생성·추론되지 않는다(Req 9.4, 9.9).

design.md 매핑표 / normalize._parse_price 규칙(공식 필드만 사용):
- `currency`는 `price.currency`가 비어 있지 않은 문자열일 때만 그대로 보존하고,
  그 외에는 None으로 둔다(없는 값을 지어내지 않음).
- `price.extracted_value`가 숫자로 파싱되면 표시 가격은 `price.value`를 그대로
  보존한다(문자열은 원문 그대로, 숫자형은 str()로 담되 변조하지 않음).
  `value`가 없으면 "미확인"으로 두되, 없는 문자열을 만들어 채우지 않는다.

본 속성의 관심사는 "보존·무변조"이므로, 각 항목은 필수 필드(title/image/link)와
http(s) 스킴·유일 링크를 갖도록 생성해 필수 필드 필터(Req 9.2)·스킴(Req 9.8)·
중복(Req 9.6)의 영향을 배제한다. 기대값은 입력 price 객체에서 직접 파생해 구현과
독립적으로 판정한다.
"""

from typing import Optional

from hypothesis import given, settings
from hypothesis import strategies as st

from closeller.normalize import PRICE_UNKNOWN, normalize_visual_matches

# --- 구현과 독립적인 기대값 파생 헬퍼 ----------------------------------------


def _expected_currency(price_obj: object) -> Optional[str]:
    """입력 price 객체에서 기대 통화를 파생한다(구현과 독립).

    `price.currency`가 비어 있지 않은 문자열이면 그 값을 그대로, 그 외에는 None.
    """
    if not isinstance(price_obj, dict):
        return None
    currency = price_obj.get("currency")
    if isinstance(currency, str) and currency:
        return currency
    return None


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


def _expected_price(price_obj: object) -> str:
    """입력 price 객체에서 기대 표시 가격을 파생한다(구현과 독립).

    extracted_value가 숫자로 파싱되면 value를 그대로 보존(문자열은 원문, 숫자형은
    str()). value가 없으면 "미확인". extracted_value가 숫자가 아니면 "미확인".
    """
    if not isinstance(price_obj, dict):
        return PRICE_UNKNOWN
    if not _parses_as_number(price_obj.get("extracted_value")):
        return PRICE_UNKNOWN
    display = price_obj.get("value")
    if isinstance(display, str) and display.strip():
        return display
    if isinstance(display, (int, float)) and not isinstance(display, bool):
        return str(display)
    return PRICE_UNKNOWN


# --- 생성기(generator): 가격·통화 입력 공간을 지능적으로 구성한다 -------------

# 통화 코드 후보: 유효한 코드와 "비어있음"(None·빈 문자열·비문자열)을 섞는다.
_currency_value = st.one_of(
    st.sampled_from(("KRW", "USD", "EUR", "JPY", "GBP", "₩", "$")),
    st.none(),
    st.just(""),
    st.integers(),          # 비문자열 → None으로 떨어져야 함
)

# 표시용 value 후보: 원문 보존을 확인하기 위해 통화 기호·구분자·공백을 포함한다.
_value_text = st.sampled_from(
    (
        "₩120,000",
        "$1,299.00",
        "120000",
        "1299.00",
        "€89",
        " 50,000 ",   # 양끝 공백 포함 원문도 그대로 보존되어야 함
        "USD 42",
    ),
)

# 숫자형 value(문자열이 아닌 가격 표시값). str()로 보존된다.
_value_numeric = st.one_of(
    st.integers(min_value=0, max_value=10_000_000),
    st.floats(min_value=0, max_value=1_000_000, allow_nan=False, allow_infinity=False),
)

# 정렬용 extracted_value: 파싱 가능/불가를 섞는다.
_extracted_value = st.one_of(
    st.integers(min_value=0, max_value=10_000_000),
    st.floats(min_value=0, max_value=1_000_000, allow_nan=False, allow_infinity=False),
    st.sampled_from(("12000", "99.99", "0")),   # 숫자 문자열(파싱 가능)
    st.sampled_from(("가격문의", "", "N/A")),      # 파싱 불가 → "미확인"
    st.none(),
)


@st.composite
def _price_object(draw: st.DrawFn) -> object:
    """price 객체(또는 price 자체 부재를 나타내는 None)를 생성한다.

    value는 문자열/숫자형/부재를 섞고, currency·extracted_value를 독립적으로 뽑아
    보존·미확인·무변조 경로를 폭넓게 탐색한다.
    """
    # 가끔 price 객체 자체를 비정상 형태로 둔다(→ 전부 "미확인"+None 기대).
    if draw(st.integers(min_value=0, max_value=9)) == 0:
        return draw(st.one_of(st.none(), st.integers(), st.text(max_size=3)))

    price_obj: dict = {}

    value_mode = draw(st.sampled_from(("text", "numeric", "absent")))
    if value_mode == "text":
        price_obj["value"] = draw(_value_text)
    elif value_mode == "numeric":
        price_obj["value"] = draw(_value_numeric)
    # absent: value 키 생략

    if draw(st.booleans()):
        price_obj["currency"] = draw(_currency_value)

    if draw(st.booleans()):
        price_obj["extracted_value"] = draw(_extracted_value)

    return price_obj


@st.composite
def _item_with_price(draw: st.DrawFn, index: int) -> dict:
    """필수 필드를 갖춘 유효 항목을 생성하되, price만 다양하게 바꾼다.

    title/image는 유효하게 고정하고 link는 인덱스로 유일하게 만들어 필수 필드·스킴·
    중복의 영향을 배제한다. 가격·통화 보존만 관심사로 남긴다.
    """
    return {
        "title": draw(st.sampled_from(("빈티지 자켓", "Nike Tee", "가죽 지갑"))),
        "image": "https://img.example.com/a.jpg",
        "link": f"https://example.com/p/{index}",
        "price": draw(_price_object()),
    }


@st.composite
def _items(draw: st.DrawFn) -> list[dict]:
    """유효 항목 리스트를 생성한다(각 항목 유일 링크)."""
    size = draw(st.integers(min_value=1, max_value=8))
    return [draw(_item_with_price(index=i)) for i in range(size)]


# --- 속성 테스트 -------------------------------------------------------------


# Feature: closeller-mvp, Property 12: 가격 값과 통화는 변조 없이 보존
@settings(max_examples=200)
@given(items=_items())
def test_price_and_currency_preserved_without_tampering(items: list[dict]) -> None:
    """정규화 결과의 가격·통화는 입력 price 객체에서 파생한 기대값과 정확히 일치한다.

    링크가 유일하고 필수 필드가 모두 존재하므로 입력 순서와 출력 개수가 1:1 대응한다.
    각 결과의 price/currency가 응답값과 동일하게 보존되는지(무변조) 확인한다
    (Req 9.4, 9.9).
    """
    results = normalize_visual_matches(items)
    assert len(results) == len(items)

    # 링크 기준으로 입력 항목과 출력 결과를 대응시킨다(정렬로 순서가 바뀔 수 있음).
    items_by_link = {item["link"]: item for item in items}
    for result in results:
        source_item = items_by_link[result.link]
        price_obj = source_item.get("price")
        assert result.price == _expected_price(price_obj)
        assert result.currency == _expected_currency(price_obj)


# Feature: closeller-mvp, Property 12: 가격 값과 통화는 변조 없이 보존
@settings(max_examples=100)
@given(price_obj=_price_object())
def test_present_price_value_is_never_fabricated(price_obj: object) -> None:
    """표시 가격은 응답의 value를 그대로 보존하거나 "미확인"일 뿐, 날조되지 않는다.

    price가 "미확인"이 아니면, 그 값은 반드시 입력 `value`(문자열 원문 또는 숫자형의
    str())와 동일해야 한다. 즉 존재하지 않는 가격 문자열을 지어내지 않는다(Req 9.9).
    """
    item = {
        "title": "테스트 상품",
        "image": "https://img.example.com/a.jpg",
        "link": "https://example.com/p/single",
        "price": price_obj,
    }
    results = normalize_visual_matches([item])
    assert len(results) == 1
    result = results[0]

    if result.price != PRICE_UNKNOWN:
        assert isinstance(price_obj, dict)
        value = price_obj.get("value")
        if isinstance(value, str):
            assert result.price == value          # 원문 그대로(공백 포함)
        else:
            assert result.price == str(value)     # 숫자형은 str()로만 보존


# Feature: closeller-mvp, Property 12: 가격 값과 통화는 변조 없이 보존
@settings(max_examples=100)
@given(price_obj=_price_object())
def test_currency_is_preserved_or_none_never_invented(price_obj: object) -> None:
    """통화는 입력 통화 그대로 보존되거나 None이며, 없는 통화를 만들어내지 않는다.

    출력 currency는 항상 입력 `price.currency`(비어있지 않은 문자열)와 동일하거나
    None이어야 한다. 존재하지 않는 통화 코드를 추론·생성하지 않는다(Req 9.4, 9.9).
    """
    item = {
        "title": "테스트 상품",
        "image": "https://img.example.com/a.jpg",
        "link": "https://example.com/p/single",
        "price": price_obj,
    }
    results = normalize_visual_matches([item])
    assert len(results) == 1
    currency = results[0].currency

    assert currency == _expected_currency(price_obj)
    if currency is not None:
        # 보존된 통화는 반드시 입력에 실제로 존재한 비어있지 않은 문자열이어야 한다.
        assert isinstance(price_obj, dict)
        assert currency == price_obj.get("currency")
        assert isinstance(currency, str) and currency != ""
