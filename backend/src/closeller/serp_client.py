"""SerpApi Google Lens 클라이언트(I/O 모듈).

Search_Lambda 파이프라인에서 SerpApi Google Lens API(engine=google_lens)를
호출하고, 응답에서 `visual_matches` 배열을 꺼내 반환하는 책임을 담당한다
(design.md 모듈 분리표의 `serp_client.py` 행, Req 8.3~8.6). 순수 모듈과 달리
외부 I/O(SSM 읽기·HTTP 호출)에 의존하므로 I/O 모듈로 분류한다.

🔒 승인 규칙(Req 23.1): **실제 SerpApi 호출은 사용자 승인 전에 실행하지 않는다.**
본 모듈은 호출 "방법"을 정의할 뿐, 호출 자체를 자동 수행하지 않는다. 단위
테스트는 모킹한 HTTP 응답만 사용하며 실제 네트워크·SSM 접근을 하지 않는다.

공식 필드만 사용(Req 8.5, 8.6): 요청/응답 모두 SerpApi Google Lens 공식 문서
(https://serpapi.com/google-lens-api)에 명시된 필드만 사용한다. 문서에 없는
필드는 추측해 사용하거나 응답에서 추론해 만들지 않는다.

설계상 분리(테스트 가능성):
  - **요청 구성**(`build_request_params`): engine/url/api_key 등 요청 파라미터
    딕셔너리를 만드는 순수 함수. 네트워크·SSM 접근이 없어 그대로 단위 테스트할 수
    있다.
  - **응답 파싱**(`parse_visual_matches`): 응답(dict)에서 `visual_matches` 배열을
    꺼내는 순수 함수. 없는 값을 지어내지 않고, 배열이 없거나 형식이 다르면 빈
    리스트를 반환한다.
  - **HTTP 호출**(`search_visual_matches`의 `http_get` 인자): 실제 바깥 호출은
    주입 가능한 콜러블 뒤에 둔다. 테스트는 모킹 응답을 돌려주는 가짜 콜러블을
    넘기며, 기본 구현(`_default_http_get`)은 표준 라이브러리(urllib)만 쓰므로
    추가 의존성이 없고 import 시점에 네트워크를 건드리지 않는다.
  - **api_key 로드**(`search_visual_matches`의 `api_key_loader` 인자): SSM
    SecureString에서 런타임에 키를 읽는 동작도 주입 가능한 콜러블 뒤에 둔다
    (Req 8.4). 테스트는 고정 문자열을 돌려주는 가짜 로더를 넘기고, 런타임(handler)은
    `load_api_key_from_ssm`을 넘긴다. boto3 import는 그 헬퍼 안에서만 수행하므로
    boto3가 없는(또는 모킹된) 테스트 환경에서도 모듈 import가 실패하지 않는다.

본 모듈은 모듈 수준에서 boto3 클라이언트/네트워크 리소스를 만들지 않는다
(`cache.py`·`rate_limit.py`와 동일한 지연 import·주입 패턴).
"""

import json
import urllib.parse
import urllib.request
from typing import Any, Callable, Optional

__all__ = [
    "SERPAPI_ENDPOINT",
    "ENGINE_GOOGLE_LENS",
    "DEFAULT_TIMEOUT_SECONDS",
    "build_request_params",
    "parse_visual_matches",
    "search_visual_matches",
    "load_api_key_from_ssm",
]

# SerpApi 검색 엔드포인트(공식). google_lens 포함 모든 엔진이 이 경로를 쓴다.
SERPAPI_ENDPOINT: str = "https://serpapi.com/search"

# 엔진 고정값(Req 8.3, design.md 요청 매핑표: engine=google_lens).
ENGINE_GOOGLE_LENS: str = "google_lens"

# 기본 HTTP 타임아웃(초). Lambda의 짧은 타임아웃 안에서 매달리지 않도록 보수적으로 둔다.
DEFAULT_TIMEOUT_SECONDS: float = 20.0

# 응답에서 꺼낼 결과 배열의 키(공식 응답 필드). 정규화 파이프라인의 입력이 된다.
_VISUAL_MATCHES_KEY = "visual_matches"


def build_request_params(
    *,
    image_url: str,
    api_key: str,
    country: Optional[str] = None,
    hl: Optional[str] = None,
) -> dict[str, str]:
    """SerpApi Google Lens 요청 파라미터 딕셔너리를 만든다(순수 함수, Req 8.3~8.5).

    공식 문서에 명시된 필드만 사용한다(Req 8.5, 8.6):
      - `engine`: 항상 `google_lens`로 고정한다(Req 8.3).
      - `url`: SerpApi가 접근할 이미지의 5분 Presigned GET URL(Req 8.1, 8.3).
        본 모듈은 URL을 만들지 않고, 호출부가 발급한 값을 그대로 받아 넣는다.
      - `api_key`: SSM SecureString에서 런타임에 읽은 키(Req 8.4). 이 함수는 키를
        읽지 않으며, 호출부가 넘긴 값을 그대로 넣는다.
      - `country`, `hl`: 공식 문서상 선택 파라미터. 호출부가 제공한 경우에만 포함한다
        (빈 값은 넣지 않는다).

    추측 필드를 넣지 않기 위해 위 목록 외의 키는 추가하지 않는다(Req 8.6).

    반환: urllib 인코딩에 바로 쓸 수 있는 문자열 키/값 딕셔너리.
    """
    params: dict[str, str] = {
        "engine": ENGINE_GOOGLE_LENS,
        "url": image_url,
        "api_key": api_key,
    }
    # 선택 파라미터는 실제 값이 있을 때만 포함한다(없는 값을 지어내지 않는다).
    if isinstance(country, str) and country.strip():
        params["country"] = country
    if isinstance(hl, str) and hl.strip():
        params["hl"] = hl
    return params


def parse_visual_matches(response: object) -> list[dict]:
    """SerpApi 응답에서 `visual_matches` 배열을 꺼낸다(순수 함수, Req 8.3, 8.6).

    공식 응답 구조만 신뢰한다:
      - 응답이 dict이고 `visual_matches`가 리스트이면 그 안의 dict 원소만 추려
        순서를 보존해 반환한다.
      - `visual_matches`가 없거나 리스트가 아니면 빈 리스트를 반환한다(없는 값을
        지어내지 않는다, Req 8.6·9.9).

    여기서는 개별 항목의 내부 필드(title/link/image/price 등)를 해석하지 않는다.
    그 매핑은 순수 모듈 `normalize.normalize_visual_matches`가 담당한다. 본 함수는
    "공식 배열을 그대로 꺼내 넘기는" 경계 역할만 한다.
    """
    if not isinstance(response, dict):
        return []
    matches = response.get(_VISUAL_MATCHES_KEY)
    if not isinstance(matches, list):
        return []
    return [item for item in matches if isinstance(item, dict)]


def _default_http_get(url: str, *, timeout: float) -> dict:
    """SerpApi GET 요청을 수행하고 JSON 응답을 dict로 반환한다(기본 HTTP 콜러블).

    표준 라이브러리 `urllib`만 사용하므로 추가 의존성이 없고, 이 함수를 호출하기
    전까지는 네트워크를 건드리지 않는다. 🔒 실제 호출은 상위(handler)가 사용자
    승인 이후에만 수행해야 한다(Req 23.1). 단위 테스트는 이 기본 구현 대신 모킹한
    콜러블을 주입한다.
    """
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as resp:  # noqa: S310 - https 고정 엔드포인트
        charset = resp.headers.get_content_charset() or "utf-8"
        body = resp.read().decode(charset)
    return json.loads(body)


def search_visual_matches(
    *,
    image_url: str,
    api_key_loader: Callable[[], str],
    country: Optional[str] = None,
    hl: Optional[str] = None,
    http_get: Callable[..., dict] = _default_http_get,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    endpoint: str = SERPAPI_ENDPOINT,
) -> list[dict]:
    """SerpApi Google Lens를 호출하고 `visual_matches` 배열을 반환한다(Req 8.3~8.6).

    🔒 실제 네트워크 호출은 주입된 `http_get` 콜러블을 통해서만 일어난다. 사용자
    승인 전에는 실제 `http_get`(기본값)이 호출되지 않도록 상위에서 통제해야 한다
    (Req 23.1). 테스트는 모킹 응답을 돌려주는 가짜 `http_get`과 고정 키를 돌려주는
    가짜 `api_key_loader`를 넘겨 실제 I/O 없이 동작을 검증한다.

    매개변수:
      image_url: SerpApi가 접근할 5분 Presigned GET URL(Req 8.1). 호출부가 발급한
        값을 그대로 쓴다.
      api_key_loader: 호출 시점에 api_key를 돌려주는 콜러블. 런타임에는 SSM
        SecureString에서 읽는 `load_api_key_from_ssm`을 넘긴다(Req 8.4). 키를
        반환 직전까지 로드하지 않도록 지연 콜러블로 받는다.
      country, hl: 공식 선택 파라미터. 주어진 경우에만 요청에 포함한다.
      http_get: 실제 바깥 호출을 수행하는 주입 가능한 콜러블. `http_get(url,
        timeout=...)` 형태로 호출되며 JSON 응답(dict)을 반환해야 한다. 기본값은
        표준 라이브러리 기반 `_default_http_get`.
      timeout: HTTP 타임아웃(초).
      endpoint: SerpApi 검색 엔드포인트. 기본값은 공식 엔드포인트.

    반환: `visual_matches` 배열(dict 리스트). 응답에 배열이 없으면 빈 리스트.
    """
    api_key = api_key_loader()
    params = build_request_params(
        image_url=image_url,
        api_key=api_key,
        country=country,
        hl=hl,
    )
    url = f"{endpoint}?{urllib.parse.urlencode(params)}"
    response = http_get(url, timeout=timeout)
    return parse_visual_matches(response)


def load_api_key_from_ssm(
    parameter_name: str,
    *,
    region_name: Optional[str] = None,
) -> str:
    """런타임(handler)에서 SSM SecureString으로 저장된 SerpApi Key를 읽는다(Req 8.4).

    boto3 import를 이 함수 내부에서만 수행하므로, boto3가 설치되지 않았거나 모킹된
    테스트 환경에서도 `serp_client` 모듈 import 자체는 실패하지 않는다. 테스트는 이
    헬퍼 대신 `search_visual_matches`에 고정 키를 돌려주는 가짜 로더를 직접 주입하면
    되며, 이 함수를 호출하지 않으므로 실제 AWS 호출이 발생하지 않는다.

    `WithDecryption=True`로 SecureString을 복호화해 평문 키를 반환한다. 반환된 키는
    로그에 남기지 않는다(Req 21.4) — 호출부는 키를 로깅·저장하지 않는다.
    """
    import boto3  # 지연 import: 테스트 모킹·경량 import 경로 보호

    client = boto3.client("ssm", region_name=region_name)
    response = client.get_parameter(Name=parameter_name, WithDecryption=True)
    return str(response["Parameter"]["Value"])


def _make_lazy_ssm_loader(
    parameter_name: str,
    *,
    region_name: Optional[str] = None,
) -> Callable[[], str]:
    """`load_api_key_from_ssm`를 인자 없는 지연 콜러블로 감싸는 런타임 헬퍼.

    `search_visual_matches(api_key_loader=...)`에 바로 넘길 수 있는 형태를 만든다.
    호출 시점(검색 직전)에만 SSM을 읽도록 지연시킨다. 테스트는 이 헬퍼를 쓰지 않고
    가짜 로더를 직접 주입한다.
    """

    def _loader() -> str:
        return load_api_key_from_ssm(parameter_name, region_name=region_name)

    return _loader
