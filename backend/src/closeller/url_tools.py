"""URL 도구(순수 모듈).

정규화 파이프라인(normalize.py)이 사용하는 URL 유틸리티를 담당한다.
I/O·외부 의존성(boto3·네트워크·파일)이 없는 순수 함수만 포함하며,
표준 라이브러리 `urllib.parse`만 사용한다(design.md 모듈 분리표 참조).

- URL 정규화: 스킴·호스트를 소문자로 바꾸고, 추적용 쿼리 파라미터와 프래그먼트를
  제거하며, 경로 끝 슬래시를 제거한다. 이 정규화 값은 중복 판정의 기준이 된다
  (Req 9.6, Property 14). 같은 상품을 가리키는 URL이라도 추적 파라미터·프래그먼트·
  대소문자·끝 슬래시 차이로 서로 달라 보일 수 있으므로 이를 걷어내 동일 여부를 맞춘다.
- 스킴 검사: URL의 스킴이 http 또는 https인지 판정한다. 그 외 스킴(ftp·javascript·
  data·mailto 등)을 가진 결과는 정규화 파이프라인에서 제외된다(Req 9.8, Property 15).

두 함수 모두 동일 입력에 대해 항상 동일한 결과를 반환하는 결정적 함수다.
"""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# http/https 허용 스킴 (Req 9.8). 소문자로 비교한다.
_ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})

# 추적용(트래킹) 쿼리 파라미터 집합.
# 상품 식별에 무관하며 같은 페이지의 중복 URL을 서로 다르게 보이게 만드는 대표적인
# 트래킹 파라미터를 제거한다. 선택 근거:
#   - utm_* : Google Analytics UTM 캠페인 파라미터 (utm_source/medium/campaign/term/content 등)
#   - gclid / dclid / gbraid / wbraid : Google Ads·DoubleClick 클릭 식별자
#   - fbclid : Meta(Facebook) 클릭 식별자
#   - msclkid : Microsoft Ads 클릭 식별자
#   - yclid   : Yandex 클릭 식별자
#   - mc_eid / mc_cid : Mailchimp 이메일·캠페인 식별자
#   - igshid : Instagram 공유 식별자
#   - ref / ref_src / ref_ / referrer : 일반적인 리퍼러/추천 트래킹 파라미터
#   - spm / scm : 알리·타오바오 등에서 쓰는 트래킹 파라미터
#   - _hsenc / _hsmi / hsCtaTracking : HubSpot 트래킹 파라미터
# utm_ 접두사는 접두사 매칭(_TRACKING_PREFIXES)으로도 처리해 세부 변형까지 폭넓게 제거한다.
# 트래킹이 아닌 쿼리(상품 식별에 쓰일 수 있는 id·variant 등)는 보존한다.
_TRACKING_PARAMS: frozenset[str] = frozenset(
    {
        "gclid",
        "dclid",
        "gbraid",
        "wbraid",
        "fbclid",
        "msclkid",
        "yclid",
        "mc_eid",
        "mc_cid",
        "igshid",
        "ref",
        "ref_src",
        "ref_",
        "referrer",
        "spm",
        "scm",
        "_hsenc",
        "_hsmi",
        "hsctatracking",
    }
)

# 접두사로 시작하는 트래킹 파라미터군(변형이 많아 집합으로 모두 열거하기 어려운 것).
_TRACKING_PREFIXES: tuple[str, ...] = ("utm_",)


def _is_tracking_param(name: str) -> bool:
    """쿼리 파라미터 이름이 추적용인지 판정한다(내부 헬퍼).

    이름은 소문자로 정규화해 집합·접두사와 비교한다.
    """
    lowered = name.lower()
    if lowered in _TRACKING_PARAMS:
        return True
    return any(lowered.startswith(prefix) for prefix in _TRACKING_PREFIXES)


def is_http_scheme(url: str) -> bool:
    """URL의 스킴이 http 또는 https인지 여부를 반환한다(Req 9.8).

    스킴 비교는 대소문자를 구분하지 않는다(예: "HTTP"도 True).
    스킴이 없거나 그 외 스킴(ftp·javascript·data·mailto 등)이면 False를 반환한다.
    정규화 파이프라인은 이 함수가 False인 결과를 제외한다(Property 15).
    """
    return urlsplit(url).scheme.lower() in _ALLOWED_SCHEMES


def normalize_url(url: str) -> str:
    """판매 페이지 URL을 중복 판정 기준값으로 정규화한다(Req 9.6).

    정규화 규칙:
      1. 스킴과 호스트를 소문자로 변환한다.
      2. 추적용 쿼리 파라미터(utm_*, gclid, fbclid 등)를 제거한다.
         남은 쿼리는 키 기준으로 정렬해 순서 차이에 영향받지 않도록 한다.
      3. 프래그먼트(`#...`)를 제거한다.
      4. 경로 끝의 슬래시 하나를 제거한다(루트 경로 "/"는 빈 경로로 둔다).

    동일한 상품을 가리키는 URL은 위 차이를 제거한 뒤 같은 문자열로 수렴하며,
    이 값이 같은 결과는 중복으로 간주된다(Property 14). 결정적 함수이므로
    동일 입력은 항상 동일한 결과를 반환한다.
    """
    parts = urlsplit(url)

    scheme = parts.scheme.lower()
    host = parts.hostname.lower() if parts.hostname else ""

    # 호스트(소문자) + 포트/인증정보를 재구성한다. 포트·userinfo는 보존한다.
    netloc = host
    if parts.port is not None:
        netloc = f"{host}:{parts.port}"
    if parts.username is not None:
        userinfo = parts.username
        if parts.password is not None:
            userinfo = f"{userinfo}:{parts.password}"
        netloc = f"{userinfo}@{netloc}"

    # 끝 슬래시 제거: 경로가 "/"뿐이면 빈 경로로, 그 외에는 오른쪽 슬래시 하나만 제거.
    path = parts.path
    if path != "/":
        path = path.rstrip("/")
    else:
        path = ""

    # 추적 파라미터를 제거하고 남은 쿼리를 키 기준으로 정렬(결정적 순서).
    kept_pairs = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not _is_tracking_param(key)
    ]
    kept_pairs.sort()
    query = urlencode(kept_pairs)

    # 프래그먼트는 제거한다(빈 문자열).
    return urlunsplit((scheme, netloc, path, query, ""))
