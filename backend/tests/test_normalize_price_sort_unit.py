"""정규화 가격 파싱·서버 기본 정렬 단위 테스트 (예시/엣지 케이스 기반).

`normalize_visual_matches` 순수 함수(normalize.py)를 구체적·결정적 예시로 검증한다.
속성 기반 테스트(test_normalize_price_preserve.py / test_normalize_price_missing.py)가
"모든 입력에 대한 불변식"을 다루는 것과 달리, 본 파일은 특정 엣지 케이스와 정렬
예시가 명확히 기대대로 동작하는지 콕 집어 확인한다(tasks.md 9.7).

- Req 9.5: 가격 파싱 엣지 케이스. 가격이 없거나 숫자로 파싱할 수 없으면 표시 가격은
  "미확인"(PRICE_UNKNOWN), 정렬값은 None이며 결과는 제외되지 않고 유지된다.
  파싱 가능한 extracted_value가 있으면 표시 가격은 응답 value를 보존하고 정렬값이
  설정된다(bool·NaN·inf는 숫자에서 배제).
- Req 9.7: 서버 기본 정렬. 가격이 "미확인"이 아닌 결과를 정렬 숫자값 오름차순으로,
  "미확인" 결과는 항상 그 뒤에 배치하며, 가격 동률 또는 "미확인" 그룹 내에서는
  상품명 가나다순(표준 문자열 순서)으로, 완전 동률이면 입력 순서를 보존(안정 정렬)한다.

각 항목은 필수 필드(title/image/link)와 http(s) 스킴·유일 링크를 갖도록 구성해
필수 필드 필터(Req 9.2)·스킴(Req 9.8)·중복(Req 9.6)의 영향을 배제하고, 가격 파싱과
정렬 거동만 분리해 관찰한다.
"""

from closeller.normalize import PRICE_UNKNOWN, normalize_visual_matches

# --- 유효 항목 구성 헬퍼 ------------------------------------------------------


def _item(index: int, title: str, price: object) -> dict:
    """필수 필드를 갖춘 유효 항목을 만든다(링크는 index로 유일화).

    price만 테스트 대상으로 다양하게 주입하고, title/image/link는 가격·정렬 외
    필터(Req 9.2/9.6/9.8)의 영향을 받지 않도록 유효하게 고정한다.
    """
    return {
        "title": title,
        "image": "https://img.example.com/a.jpg",
        "link": f"https://example.com/p/{index}",
        "price": price,
    }


def _single(price: object, title: str = "테스트 상품") -> object:
    """price 하나만 주입한 단일 항목을 정규화해 결과 1건을 돌려준다."""
    results = normalize_visual_matches([_item(0, title, price)])
    assert len(results) == 1
    return results[0]


# --- Req 9.5: 가격 파싱 엣지 케이스 ------------------------------------------


def test_valid_extracted_value_sets_display_and_sort_value() -> None:
    """extracted_value가 숫자면 표시 가격은 value 원문 보존, 정렬값이 설정된다."""
    result = _single({"value": "₩120,000", "currency": "KRW", "extracted_value": 120000})
    assert result.price == "₩120,000"       # 원문 그대로 보존(무변조)
    assert result.currency == "KRW"
    assert result.price_sort_value == 120000.0


def test_numeric_value_is_preserved_as_str() -> None:
    """숫자형 value는 str()로 보존된다(지어내지 않고 형식만 문자열화)."""
    result = _single({"value": 42, "extracted_value": 42})
    assert result.price == "42"
    assert result.price_sort_value == 42.0


def test_price_object_absent_yields_unknown_and_kept() -> None:
    """price 키 자체가 없으면 "미확인"+None이며 결과는 유지된다."""
    item = {
        "title": "가격 없는 상품",
        "image": "https://img.example.com/a.jpg",
        "link": "https://example.com/p/noprice",
    }
    results = normalize_visual_matches([item])
    assert len(results) == 1
    assert results[0].price == PRICE_UNKNOWN
    assert results[0].price_sort_value is None


def test_price_not_a_dict_yields_unknown_and_kept() -> None:
    """price가 dict가 아니면(None·숫자·문자열) "미확인"+None이며 결과는 유지된다."""
    for bad_price in (None, 12345, "₩120,000", ["list"]):
        result = _single(bad_price)
        assert result.price == PRICE_UNKNOWN
        assert result.price_sort_value is None


def test_unparseable_extracted_value_yields_unknown_and_kept() -> None:
    """extracted_value가 숫자로 파싱 불가하면 "미확인"+None이되 결과는 유지된다."""
    for bad in ("가격문의", "", "N/A", "  ", "price"):
        result = _single({"value": "₩120,000", "extracted_value": bad})
        assert result.price == PRICE_UNKNOWN
        assert result.price_sort_value is None


def test_extracted_value_present_but_value_absent_keeps_sort_value() -> None:
    """정렬값은 확보됐으나 표시 value가 없으면 표시 "미확인", 정렬값은 유지된다."""
    result = _single({"extracted_value": 99000})
    assert result.price == PRICE_UNKNOWN      # 없는 문자열을 지어내지 않음
    assert result.price_sort_value == 99000.0  # 있던 값은 보존


def test_bool_extracted_value_is_rejected_to_none() -> None:
    """bool extracted_value(True/False)는 숫자에서 배제되어 "미확인"+None."""
    for flag in (True, False):
        result = _single({"value": "₩1", "extracted_value": flag})
        assert result.price == PRICE_UNKNOWN
        assert result.price_sort_value is None


def test_nan_and_inf_extracted_value_rejected_to_none() -> None:
    """NaN·±inf는 정렬 기준값으로 부적합하므로 "미확인"+None으로 떨어진다."""
    for bad in (float("nan"), float("inf"), float("-inf"), "NaN", "inf", "-inf"):
        result = _single({"value": "₩1", "extracted_value": bad})
        assert result.price == PRICE_UNKNOWN
        assert result.price_sort_value is None


def test_numeric_string_extracted_value_is_parsed() -> None:
    """숫자 문자열 extracted_value는 공백 제거 후 파싱되어 정렬값이 된다."""
    result = _single({"value": "50,000원", "extracted_value": " 50000 "})
    assert result.price == "50,000원"
    assert result.price_sort_value == 50000.0


# --- Req 9.7: 서버 기본 정렬 ------------------------------------------------


def _priced(index: int, title: str, extracted: float, value: str) -> dict:
    """정렬값이 있는 유효 항목을 만든다."""
    return _item(index, title, {"value": value, "extracted_value": extracted})


def _unknown(index: int, title: str) -> dict:
    """가격 미확인(정렬값 None) 유효 항목을 만든다."""
    return _item(index, title, None)


def test_priced_results_sorted_ascending_by_sort_value() -> None:
    """가격 있는 결과는 정렬 숫자값 오름차순으로 배치된다."""
    items = [
        _priced(0, "C상품", 30000, "₩30,000"),
        _priced(1, "A상품", 10000, "₩10,000"),
        _priced(2, "B상품", 20000, "₩20,000"),
    ]
    results = normalize_visual_matches(items)
    assert [r.price_sort_value for r in results] == [10000.0, 20000.0, 30000.0]
    assert [r.title for r in results] == ["A상품", "B상품", "C상품"]


def test_unknown_price_results_placed_after_all_priced() -> None:
    """"미확인" 결과는 가격 있는 모든 결과 뒤에 배치된다(값과 무관)."""
    items = [
        _unknown(0, "가미확인"),
        _priced(1, "비싼상품", 99999, "₩99,999"),
        _unknown(2, "나미확인"),
        _priced(3, "싼상품", 100, "₩100"),
    ]
    results = normalize_visual_matches(items)

    # 앞쪽은 전부 가격 있음(오름차순), 뒤쪽은 전부 미확인.
    assert results[0].title == "싼상품"
    assert results[1].title == "비싼상품"
    assert results[2].price == PRICE_UNKNOWN
    assert results[3].price == PRICE_UNKNOWN
    # 미확인 그룹은 가격 있는 그룹 뒤에만 나타난다.
    first_unknown_index = next(
        i for i, r in enumerate(results) if r.price == PRICE_UNKNOWN
    )
    assert all(
        results[j].price != PRICE_UNKNOWN for j in range(first_unknown_index)
    )


def test_equal_price_group_ordered_by_title() -> None:
    """가격이 동일한 결과들끼리는 상품명 가나다순으로 정렬된다."""
    items = [
        _priced(0, "다상품", 5000, "₩5,000"),
        _priced(1, "가상품", 5000, "₩5,000"),
        _priced(2, "나상품", 5000, "₩5,000"),
    ]
    results = normalize_visual_matches(items)
    assert [r.title for r in results] == ["가상품", "나상품", "다상품"]


def test_unknown_price_group_ordered_by_title() -> None:
    """"미확인" 결과들끼리도 상품명 가나다순으로 정렬된다."""
    items = [
        _unknown(0, "다미확인"),
        _unknown(1, "가미확인"),
        _unknown(2, "나미확인"),
    ]
    results = normalize_visual_matches(items)
    assert [r.title for r in results] == ["가미확인", "나미확인", "다미확인"]


def test_stable_order_preserved_for_fully_equal_keys() -> None:
    """가격·상품명이 모두 같으면 입력 순서가 보존된다(안정 정렬)."""
    items = [
        _priced(0, "동일상품", 7000, "₩7,000"),
        _priced(1, "동일상품", 7000, "₩7,000"),
        _priced(2, "동일상품", 7000, "₩7,000"),
    ]
    results = normalize_visual_matches(items)
    # 완전 동률 키 → 입력 순서(link index) 그대로 유지.
    assert [r.link for r in results] == [
        "https://example.com/p/0",
        "https://example.com/p/1",
        "https://example.com/p/2",
    ]


def test_mixed_priced_and_unknown_full_ordering() -> None:
    """가격 오름차순 → 동률 가나다순 → 미확인 가나다순의 종합 정렬 예시."""
    items = [
        _unknown(0, "힣미확인"),
        _priced(1, "비싼A", 30000, "₩30,000"),
        _priced(2, "저가B", 10000, "₩10,000"),
        _priced(3, "저가A", 10000, "₩10,000"),  # 동률 → 가나다순
        _unknown(4, "가미확인"),
    ]
    results = normalize_visual_matches(items)
    assert [r.title for r in results] == [
        "저가A",     # 10000, 가나다 앞
        "저가B",     # 10000, 가나다 뒤
        "비싼A",     # 30000
        "가미확인",  # 미확인, 가나다 앞
        "힣미확인",  # 미확인, 가나다 뒤
    ]
