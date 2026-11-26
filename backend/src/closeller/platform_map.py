"""판매 플랫폼 분류(순수 모듈).

정규화 파이프라인(normalize.py)이 사용하는 도메인 → (플랫폼명, 국내/해외) 분류를
담당한다. I/O·외부 의존성(boto3·네트워크·파일)이 없는 순수 함수만 포함하며,
표준 라이브러리 `urllib.parse`만 사용한다(design.md 모듈 분리표 참조).

Platform_Map은 "도메인 → (플랫폼명, 국내/해외 구분)" 매핑표이며, 이 모듈 한 곳에서만
관리한다(Req 10.6, 단일 출처). 분류 로직은 다음 알고리즘을 따른다(design.md):

1. `link`에서 호스트를 추출 → 소문자 변환 → 선행 `www.` 제거.
2. Platform_Map 조회 → 적중 시 (플랫폼명, "국내"/"해외") 반환(Req 10.1, 10.4).
   매핑된 도메인의 하위 도메인(예: `m.bunjang.co.kr`, `shop.musinsa.com`)도
   같은 플랫폼으로 분류한다.
3. 미적중이지만 브랜드 공식 홈페이지로 볼 근거가 있으면
   ("공식 홈페이지 후보", "미확인") 반환(Req 10.2, 10.5).
4. 미적중이고 근거가 없으면 ("기타", "미확인") 반환(Req 10.3, 10.5).

구분 문자열은 models.py `NormalizedResult.region`과 일치하도록
정확히 "국내" | "해외" | "미확인"만 사용한다.

동일 입력에 대해 항상 동일한 결과를 반환하는 결정적 함수다(Property 16).
"""

from urllib.parse import urlsplit

__all__ = [
    "PLATFORM_MAP",
    "PLATFORM_OTHER",
    "PLATFORM_OFFICIAL_CANDIDATE",
    "REGION_DOMESTIC",
    "REGION_OVERSEAS",
    "REGION_UNKNOWN",
    "classify_platform",
]

# 국내/해외/미확인 구분 문자열. models.py NormalizedResult.region과 반드시 일치시킨다.
REGION_DOMESTIC: str = "국내"
REGION_OVERSEAS: str = "해외"
REGION_UNKNOWN: str = "미확인"

# 미적중 시 사용하는 플랫폼명(Req 10.2, 10.3).
PLATFORM_OTHER: str = "기타"
PLATFORM_OFFICIAL_CANDIDATE: str = "공식 홈페이지 후보"

# Platform_Map: 도메인 → (플랫폼명, 국내/해외 구분) 단일 출처(Req 10.6).
# 키는 선행 `www.`를 제거한 소문자 호스트다. 하위 도메인은 _match_mapped_domain에서
# 접미사 매칭으로 함께 처리하므로(예: m.bunjang.co.kr) 여기서는 대표 도메인만 둔다.
# 번개장터는 design.md 표에 `m.bunjang.co.kr`도 명시되어 있으나, 접미사 매칭으로
# `bunjang.co.kr` 항목에 포함되므로 별도 등록이 필요 없다.
PLATFORM_MAP: dict[str, tuple[str, str]] = {
    "fruitsfamily.com": ("후루츠패밀리", REGION_DOMESTIC),
    "bunjang.co.kr": ("번개장터", REGION_DOMESTIC),
    "musinsa.com": ("무신사", REGION_DOMESTIC),
    "kream.co.kr": ("KREAM", REGION_DOMESTIC),
    "ebay.com": ("eBay", REGION_OVERSEAS),
    "grailed.com": ("Grailed", REGION_OVERSEAS),
    "vestiairecollective.com": ("Vestiaire Collective", REGION_OVERSEAS),
}


def _extract_host(link: str) -> str:
    """URL에서 호스트를 추출해 소문자로 바꾸고 선행 `www.`를 제거한다(내부 헬퍼).

    호스트가 없으면 빈 문자열을 반환한다. 비교·조회의 기준값으로 쓰인다.
    """
    host = urlsplit(link).hostname or ""
    host = host.lower()
    if host.startswith("www."):
        host = host[len("www.") :]
    return host


def _match_mapped_domain(host: str) -> tuple[str, str] | None:
    """호스트가 Platform_Map의 도메인과 일치(또는 그 하위 도메인)하는지 조회한다.

    정확히 일치하거나, 매핑 도메인의 하위 도메인(예: `shop.musinsa.com`,
    `m.bunjang.co.kr`)이면 해당 (플랫폼명, 구분)을 반환한다. 하위 도메인 판정은
    `host == domain` 또는 `host`가 `"." + domain`으로 끝나는지로 한다. 점 경계를
    확인하므로 `notbunjang.co.kr` 같은 유사 도메인은 오탐하지 않는다. 미적중이면
    None을 반환한다.
    """
    for domain, info in PLATFORM_MAP.items():
        if host == domain or host.endswith("." + domain):
            return info
    return None


def _looks_like_official_homepage(host: str, brand: str | None) -> bool:
    """미적중 호스트가 브랜드 공식 홈페이지로 볼 근거가 있는지 판정한다(휴리스틱).

    주의: 이것은 휴리스틱이며 확정 판정이 아니다. 그래서 분류 결과도 단정적인
    플랫폼명이 아니라 "공식 홈페이지 후보"로 둔다(Req 10.2). 근거는 다음과 같다.

    - 브랜드 힌트(`brand`)가 주어지고, 그 브랜드명을 영숫자만 남겨 정규화한 토큰이
      호스트의 도메인 라벨 중 하나와 일치하면 공식 홈페이지 후보로 본다.
      예) brand="Acne Studios", host="acnestudios.com" → 라벨 "acnestudios"가
          정규화 토큰 "acnestudios"와 일치 → True.
    - 브랜드 힌트가 없으면 링크만으로는 공식 홈페이지라는 근거가 없으므로 False.
      (SerpApi 응답에는 브랜드 전용 필드가 없어 기본적으로 brand=None이며,
       이 경우 미적중 호스트는 "기타"로 분류된다 — Req 10.3.)

    브랜드명과 호스트 라벨을 모두 영숫자 소문자로 정규화해 공백·기호·대소문자
    차이를 흡수한다.
    """
    if not brand:
        return False

    brand_token = "".join(ch for ch in brand.lower() if ch.isalnum())
    if not brand_token:
        return False

    # 호스트의 도메인 라벨(점 기준 분할)을 영숫자로 정규화해 비교한다.
    for label in host.split("."):
        label_token = "".join(ch for ch in label if ch.isalnum())
        if label_token and label_token == brand_token:
            return True
    return False


def classify_platform(link: str, brand: str | None = None) -> tuple[str, str]:
    """판매 페이지 링크를 (플랫폼명, 국내/해외 구분)으로 분류한다.

    매개변수:
      link: 판매 페이지 URL. 호스트를 추출해 Platform_Map과 대조한다.
      brand: 선택적 브랜드 힌트. 미적중 시 공식 홈페이지 후보 판정에만 쓰인다.
             (기본 None — SerpApi 응답에 브랜드 전용 필드가 없기 때문이다.)

    반환: (플랫폼명, 구분) 튜플. 구분은 "국내" | "해외" | "미확인" 중 하나다.

    분류 규칙(Req 10.1~10.5):
      - Platform_Map 적중(하위 도메인 포함): 정의된 (플랫폼명, "국내"/"해외").
      - 미적중 + 공식 홈페이지 근거 있음: ("공식 홈페이지 후보", "미확인").
      - 미적중 + 근거 없음: ("기타", "미확인").

    결정적 함수이므로 동일 입력은 항상 동일한 결과를 반환한다(Property 16).
    """
    host = _extract_host(link)

    mapped = _match_mapped_domain(host)
    if mapped is not None:
        return mapped

    if _looks_like_official_homepage(host, brand):
        return (PLATFORM_OFFICIAL_CANDIDATE, REGION_UNKNOWN)

    return (PLATFORM_OTHER, REGION_UNKNOWN)
