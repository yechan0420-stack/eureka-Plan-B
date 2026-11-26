"""검색 결과 정규화 파이프라인(순수 모듈).

SerpApi Google Lens 응답의 `visual_matches[]` 항목을 공식 필드만 사용해
`NormalizedResult`로 변환한다(Req 9.1, 8.5, 8.6). I/O·외부 의존성(boto3·네트워크·
파일)이 없는 순수 함수만 포함하며, 표준 라이브러리와 형제 순수 모듈
(`url_tools`, `platform_map`, `match_grade`)만 사용한다(design.md 모듈 분리표).

데이터 정직성(Req 9.9): 응답에 존재하지 않는 가격·상품·링크 값을 생성하거나
추론해 채우지 않는다. 공식 문서에 없는 필드도 사용하지 않는다(Req 8.6).

처리 순서(연산 순서를 고정해 결정적 결과를 보장한다):

1. **필드 추출·필수 필드 필터**: 각 항목에서 `title` / `link` / `image`(없으면
   `thumbnail`)를 꺼낸다. 셋 중 하나라도 비거나 누락이면 해당 결과를 제외한다
   (Req 9.2).
2. **스킴 필터**: `link`의 스킴이 http/https가 아니면 제외한다(Req 9.8).
3. **중복 제거**: `normalize_url(link)`을 기준값으로 같은 값을 가진 결과 중
   입력 순서상 첫 1건만 남긴다(Req 9.6).
4. **가격 파싱**: `price.value`/`price.currency`는 그대로 보존하고
   `price.extracted_value`를 정렬용 숫자로 쓴다. 숫자로 파싱할 수 없으면
   표시 가격을 "미확인", 정렬값을 None으로 두되 결과는 유지한다(Req 9.4, 9.5).
5. **분류·등급 산정**: `classify_platform(link)`으로 플랫폼·국내/해외를,
   `exact_matches`로 유형("동일 상품 후보"/"유사 상품")을, (유형, `position`)으로
   Match_Grade를 산정한다(Req 10.x, 11.1, 11.2, 11.3~11.6).
6. **서버 기본 정렬**: 가격이 "미확인"이 아닌 결과를 가격 오름차순으로, 가격이
   동일하거나 "미확인"인 결과는 상품명 가나다순으로 정렬한다. 안정 정렬을 써서
   동률 시 입력 순서를 보존한다(Req 9.7, 11/15 안정성).

브랜드는 기본 미포함이다. SerpApi `visual_matches`에는 브랜드 전용 필드가 없어,
없는 값을 추론하지 않는다는 규칙에 따라 `brand=None`으로 둔다(Req 8.6, 9.3, 9.9).

동일 입력에 대해 항상 동일한 결과를 반환하는 결정적 함수들로 구성된다
(Property 11~15, 18).
"""

from typing import Optional

from .match_grade import (
    MATCH_TYPE_IDENTICAL,
    MATCH_TYPE_SIMILAR,
    compute_match_grade,
)
from .models import NormalizedResult
from .platform_map import classify_platform
from .url_tools import is_http_scheme, normalize_url

__all__ = [
    "PRICE_UNKNOWN",
    "SOURCE_SERP",
    "normalize_visual_matches",
]

# 표시용 가격을 확정할 수 없을 때 쓰는 문자열(Req 9.5). models.py의 price 필드가
# 가지는 "미확인" 리터럴과 일치시킨다.
PRICE_UNKNOWN: str = "미확인"

# SerpApi에서 유래한 결과의 source 고정값(Req, design.md 매핑표). Mock 결과는
# 별도 경로에서 "MOCK"을 쓰며 이 모듈은 다루지 않는다.
SOURCE_SERP: str = "SERP"


def _clean_str(value: object) -> str:
    """값을 표시/필터용 문자열로 정리한다(내부 헬퍼).

    문자열이면 양끝 공백을 제거해 반환하고, None·문자열이 아닌 값은 빈 문자열로
    취급한다. 필수 필드(title/link/image)의 "비어 있음" 판정에 쓰이며, 공백만으로
    채워진 값도 누락과 동일하게 다루기 위함이다(Req 9.2).
    """
    if isinstance(value, str):
        return value.strip()
    return ""


def _extract_image_url(item: dict) -> str:
    """항목에서 이미지 URL을 뽑는다. `image`가 없으면 `thumbnail`로 폴백한다.

    둘 다 비거나 누락이면 빈 문자열을 반환한다(호출부에서 제외 판정, Req 9.2).
    공식 문서에 있는 두 필드만 사용한다(Req 8.6).
    """
    image = _clean_str(item.get("image"))
    if image:
        return image
    return _clean_str(item.get("thumbnail"))


def _parse_price(price_obj: object) -> tuple[str, Optional[str], Optional[float]]:
    """`price` 객체에서 (표시 가격, 통화, 정렬값)을 산출한다(내부 헬퍼).

    SerpApi `price`는 `{value, currency, extracted_value}` 형태의 객체다
    (design.md 매핑표, 공식 필드만 사용). 처리 규칙(Req 9.4, 9.5, 9.9):

    - `price.extracted_value`를 float로 파싱할 수 있으면 그 값을 정렬값으로 쓰고,
      표시 가격은 `price.value`를 그대로 보존한다(변조·재구성 금지).
      `price.value`가 비어 있으면 표시 가격은 "미확인"으로 두되, 응답에 있던
      `extracted_value`는 정렬값으로 유지한다(없는 값을 만들지 않되 있는 값은 보존).
    - `extracted_value`가 없거나 숫자로 파싱할 수 없으면 표시 가격을 "미확인",
      정렬값을 None으로 둔다. 이때도 응답에 있던 통화는 그대로 보존한다.

    반환: (display_price, currency, price_sort_value).
    """
    if not isinstance(price_obj, dict):
        return (PRICE_UNKNOWN, None, None)

    currency = price_obj.get("currency")
    currency_out: Optional[str] = currency if isinstance(currency, str) and currency else None

    sort_value = _coerce_float(price_obj.get("extracted_value"))
    if sort_value is None:
        # 파싱 가능한 숫자 가격이 없음 → 표시 "미확인", 정렬값 None(Req 9.5).
        return (PRICE_UNKNOWN, currency_out, None)

    # 정렬값은 확보됐으므로 표시 가격은 응답의 value를 그대로 보존한다(Req 9.4, 9.9).
    display = price_obj.get("value")
    if isinstance(display, str) and display.strip():
        display_out = display
    elif isinstance(display, (int, float)) and not isinstance(display, bool):
        # 숫자형 value도 보존 대상이나, 문자열 표시 필드이므로 문자열로 담는다.
        display_out = str(display)
    else:
        # 정렬값은 있으나 표시용 value가 없으면, 없는 문자열을 지어내지 않고 "미확인".
        display_out = PRICE_UNKNOWN

    return (display_out, currency_out, sort_value)


def _coerce_float(value: object) -> Optional[float]:
    """값을 float로 변환한다. 불가능하면 None(내부 헬퍼).

    bool은 int의 하위 타입이라 True/False가 1.0/0.0으로 새어들 수 있으므로
    명시적으로 배제한다. 문자열은 양끝 공백을 제거한 뒤 변환을 시도한다. NaN·무한대는
    정렬 기준값으로 부적합하므로 None으로 떨어뜨린다.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        result = float(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            result = float(text)
        except ValueError:
            return None
    else:
        return None

    # NaN·±inf는 정렬에 쓸 수 없으므로 제외한다.
    if result != result or result in (float("inf"), float("-inf")):
        return None
    return result


def _resolve_match_type(item: dict) -> str:
    """`exact_matches`로 결과 유형을 결정한다(Req 11.1, 11.2).

    `exact_matches`가 정확히 True(파이썬 불리언)일 때만 "동일 상품 후보"로 보고,
    그 외(None·누락·False·비불리언)는 근거 없음으로 "유사 상품"으로 둔다.
    """
    if item.get("exact_matches") is True:
        return MATCH_TYPE_IDENTICAL
    return MATCH_TYPE_SIMILAR


def _build_result(item: dict) -> Optional[NormalizedResult]:
    """단일 visual_matches 항목을 NormalizedResult로 변환한다(내부 헬퍼).

    필수 필드 누락(Req 9.2) 또는 비 http(s) 스킴(Req 9.8)이면 None을 반환해
    호출부가 제외하도록 한다. 중복 제거(Req 9.6)와 정렬(Req 9.7)은 상위 파이프라인이
    담당하므로 여기서는 다루지 않는다.
    """
    title = _clean_str(item.get("title"))
    if not title:
        return None

    link = _clean_str(item.get("link"))
    if not link:
        return None
    if not is_http_scheme(link):
        return None

    image_url = _extract_image_url(item)
    if not image_url:
        return None

    price, currency, price_sort_value = _parse_price(item.get("price"))

    platform, region = classify_platform(link)

    match_type = _resolve_match_type(item)
    match_grade = compute_match_grade(match_type, item.get("position"))

    return NormalizedResult(
        title=title,
        link=link,
        image_url=image_url,
        price=price,
        currency=currency,
        price_sort_value=price_sort_value,
        platform=platform,
        region=region,
        match_type=match_type,
        match_grade=match_grade,
        source=SOURCE_SERP,
        brand=None,
    )


def _sort_key(result: NormalizedResult) -> tuple:
    """서버 기본 정렬 키를 만든다(Req 9.7, 내부 헬퍼).

    규칙:
      - 가격이 "미확인"이 아니고 정렬 숫자값이 있는 결과를 가격 오름차순으로 둔다.
      - 가격이 "미확인"이거나 정렬값이 없는 결과는 가격 있는 결과 뒤에 모은다.
      - 가격이 동일하거나 "미확인"인 결과끼리는 상품명 가나다순(표준 문자열 순서)으로
        정렬한다.

    키 구성: (가격미확인_플래그, 정렬값, 상품명).
      - 첫 요소 0/1로 "미확인"을 항상 뒤로 보낸다.
      - 정렬값이 없는 경우(미확인) 0.0으로 채워 비교 오류를 막되, 첫 요소가 이미
        1이라 가격 있는 결과와 뒤섞이지 않는다.
      - 세 번째 요소 상품명으로 가격 동률·미확인 그룹 내 가나다순을 결정한다.
    sorted(...)에 그대로 넘겨 안정 정렬로 쓰므로 키가 완전히 같은 경우 입력 순서가
    보존된다.
    """
    has_price = result.price != PRICE_UNKNOWN and result.price_sort_value is not None
    price_missing_flag = 0 if has_price else 1
    sort_value = result.price_sort_value if has_price else 0.0
    return (price_missing_flag, sort_value, result.title)


def normalize_visual_matches(visual_matches: list[dict]) -> list[NormalizedResult]:
    """SerpApi `visual_matches[]`를 정규화된 결과 목록으로 변환한다.

    매개변수:
      visual_matches: SerpApi Google Lens 응답의 `visual_matches` 배열. 각 원소는
        딕셔너리이며, 딕셔너리가 아닌 원소는 무시한다(공식 구조만 처리, Req 8.5).

    반환: 서버 기본 정렬이 적용된 `NormalizedResult` 목록. 필수 필드 누락·비 http(s)
      스킴 결과는 제외되고(Req 9.2, 9.8), 정규화 URL 기준 중복은 첫 1건만 남는다
      (Req 9.6). 응답에 없는 값은 생성·추론하지 않는다(Req 9.9).

    처리 순서는 모듈 docstring의 1~6단계를 그대로 따른다. 결정적 함수다.
    """
    seen_keys: set[str] = set()
    results: list[NormalizedResult] = []

    for item in visual_matches:
        if not isinstance(item, dict):
            continue

        # 1~2단계: 필드 추출·필수 필드/스킴 필터는 _build_result가 수행한다.
        result = _build_result(item)
        if result is None:
            continue

        # 3단계: 정규화 URL 기준 중복 제거 — 그룹의 첫 1건만 유지(Req 9.6).
        dedup_key = normalize_url(result.link)
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        results.append(result)

    # 6단계: 서버 기본 정렬(안정 정렬). 가격 오름차순, 동일·미확인은 상품명 가나다순.
    results.sort(key=_sort_key)
    return results
