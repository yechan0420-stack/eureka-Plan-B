"""Search_Lambda — `POST /search` 핸들러(I/O 모듈, 파이프라인 조립).

이 모듈은 앞서 구현한 순수/ I/O 모듈을 하나의 검색 파이프라인으로 연결(wiring)한다
(design.md "Search_Lambda (POST /search)" 절, 모듈 분리표의 `handler.py` 행).
새로운 도메인 로직을 재구현하지 않고, 기존 모듈의 공개 API만 조립한다:

    validation  → 서버 재검증(존재/크기/매직 바이트)           (Req 5.1~5.4)
    hashing     → 이미지 바이트 SHA-256                         (Req 6.1)
    cache       → Cache_Table 조회/저장(TTL 24h)                (Req 6.2~6.4)
    rate_limit  → Counter_Table 조건부 원자 증가(월간/IP일일)    (Req 7.1~7.8)
    serp_client → SerpApi google_lens 호출(주입된 http_get만)    (Req 8.3~8.6)
    normalize   → visual_matches → NormalizedResult + 정렬      (Req 9.x, 11.x)
    cleanup     → 원본 즉시 삭제(모든 경로)                      (Req 12.1)
    mock        → USE_MOCK_SEARCH=true일 때 고정 데이터 반환      (Req 19.x)

파이프라인 순서(design.md 시퀀스 다이어그램 그대로):

    1. 검증(존재/크기/매직 바이트) — 실패 시 SerpApi 미호출(Req 5.4).
    2. SHA-256 해시(Req 6.1).
    3. 캐시 조회 — 적중 시 결과 반환, 카운터 미증가·외부 미호출(Req 6.3, 7.2).
    4. 호출 제한 — 월간 GLOBAL + IP 일일 조건부 원자 증가(Req 7.1~7.7).
    5. 5분 Presigned GET URL 발급(Req 8.1).
    6. SerpApi 호출(또는 Mock 모드면 mock.py 반환, 외부 미호출·카운터 미증가).
    7. 정규화·분류·등급·정렬(Req 9.x, 11.x).
    8. 캐시 저장(TTL 24h, currencyMixed 포함)(Req 6.4).
    9. 원본 즉시 삭제 — 성공·실패 모든 경로에서(Req 12.1, Property 19).

경계 규칙:
  - IP는 **오직** `event.requestContext.http.sourceIp`에서만 읽는다. 요청 본문에서
    IP를 받지 않는다(Req 7.8, design.md 경계 규칙).
  - `USE_MOCK_SEARCH=true`이면 SerpApi를 호출하지 않고 `mock.py` 데이터를 반환하며,
    카운터를 증가시키지 않는다(Req 19.1, 19.6).
  - 🔒 실제 SerpApi/AWS 호출은 주입된 콜러블·리소스 뒤에 있으며, 사용자 승인 전에는
    실제 네트워크 호출이 일어나지 않도록 상위에서 통제한다(Req 23.1).

테스트 가능성(design.md Testing Strategy, Property 5/7/19/24):
  - 핵심 파이프라인은 `run_search_pipeline(...)` **의존성 주입** 함수로 노출한다.
    테이블 객체, S3 클라이언트, serp `http_get`, `api_key_loader`, `presign_get`,
    시계(`now`)를 모두 인자로 받아 가짜(fake)로 구동할 수 있어 실제 I/O가 없다.
    이로써 검증 게이트(16.5)·캐시 적중(16.6)·원본 삭제(16.7)·Mock 모드(16.8) 속성
    테스트가 이 함수를 직접 호출해 검증할 수 있다.
  - Lambda 진입점 `handler(event, context)`는 환경변수·boto3 리소스를 지연 생성해
    `run_search_pipeline`에 주입할 뿐이다(cache/rate_limit/serp_client/cleanup/
    upload_handler와 동일한 지연 import·주입 관례).
"""

import json
import os
import time
from dataclasses import asdict
from typing import Any, Callable, Optional

from . import cache, cleanup, rate_limit, serp_client, validation
from .hashing import hash_image_bytes
from .mock import get_mock_results
from .models import NormalizedResult
from .normalize import PRICE_UNKNOWN, normalize_visual_matches

__all__ = [
    "ERROR_UPLOAD_FAILED",
    "ERROR_VALIDATION_FAILED",
    "ERROR_SEARCH_TIMEOUT",
    "ERROR_NO_RESULTS",
    "ERROR_RATE_LIMITED",
    "ERROR_INTERNAL_ERROR",
    "SOURCE_SERP",
    "SOURCE_MOCK",
    "PRESIGNED_GET_EXPIRY_SECONDS",
    "SearchError",
    "PipelineResult",
    "compute_currency_mixed",
    "run_search_pipeline",
    "handler",
]

# ---------------------------------------------------------------------------
# 오류 코드(design.md 오류 코드표). 백엔드는 안정적 코드를, 프론트는 해당 코드에
# 매핑된 한국어 메시지를 보여준다(Req 17.1~17.4, design.md Error Handling).
# ---------------------------------------------------------------------------
ERROR_UPLOAD_FAILED: str = "UPLOAD_FAILED"          # 업로드 단계 실패(Req 17.1)
ERROR_VALIDATION_FAILED: str = "VALIDATION_FAILED"  # 미존재/크기/매직 바이트(Req 5.4)
ERROR_SEARCH_TIMEOUT: str = "SEARCH_TIMEOUT"        # 검색 시간 초과(Req 17.2)
ERROR_NO_RESULTS: str = "NO_RESULTS"                # 정규화 후 0건(Req 17.3)
ERROR_RATE_LIMITED: str = "RATE_LIMITED"            # 월간/IP 상한 초과(Req 7.6, 7.7, 17.4)
ERROR_INTERNAL_ERROR: str = "INTERNAL_ERROR"        # 기타 내부 오류

# source 값(design.md 응답 스키마). normalize.SOURCE_SERP / mock.MOCK_SOURCE와 맞춘다.
SOURCE_SERP: str = "SERP"
SOURCE_MOCK: str = "MOCK"

# Presigned GET 유효 시간: 5분(300초). SerpApi 이미지 접근 전용(Req 8.1, design.md 보안 설계).
PRESIGNED_GET_EXPIRY_SECONDS: int = 300


class SearchError(Exception):
    """파이프라인 내부에서 오류 응답으로 매핑되는 예외.

    `error_code`는 design.md 오류 코드표의 안정적 코드이며, `status_code`는 API
    Gateway HTTP API(payload v2) 응답의 HTTP 상태 코드다. 파이프라인은 이 예외를
    던져 공통 오류 응답 경로로 흐르게 하고, 그 과정에서도 원본 이미지는 반드시
    삭제된다(Req 12.1, Property 19).
    """

    def __init__(self, error_code: str, status_code: int, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code
        self.message = message


class PipelineResult:
    """`run_search_pipeline`의 성공 결과(응답 본문 재료).

    `source`는 "SERP"|"MOCK", `cached`는 캐시 적중 여부, `currency_mixed`는 통화
    혼재 여부, `results`는 정규화된 결과 목록이다. 핸들러는 이를 design.md 응답
    스키마(JSON)로 직렬화한다.
    """

    __slots__ = ("source", "cached", "currency_mixed", "results")

    def __init__(
        self,
        source: str,
        cached: bool,
        currency_mixed: bool,
        results: list[NormalizedResult],
    ) -> None:
        self.source = source
        self.cached = cached
        self.currency_mixed = currency_mixed
        self.results = results

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PipelineResult):
            return NotImplemented
        return (
            self.source == other.source
            and self.cached == other.cached
            and self.currency_mixed == other.currency_mixed
            and self.results == other.results
        )

    def __repr__(self) -> str:  # pragma: no cover - 디버깅 편의용
        return (
            "PipelineResult("
            f"source={self.source!r}, cached={self.cached!r}, "
            f"currency_mixed={self.currency_mixed!r}, "
            f"results=<{len(self.results)} items>)"
        )


def compute_currency_mixed(results: list[NormalizedResult]) -> bool:
    """결과 목록에 서로 다른 통화가 2종 이상 섞여 있으면 True를 반환한다(Req 15.4).

    가격 "미확인"으로 통화가 없는(None) 결과는 통화 종류 집합에서 제외한다. 통화를
    변환하지 않으며(환율 변환은 범위 밖), 단지 혼재 여부만 판정한다(design.md
    Data Models·Property 22). 서로 다른 0~1종이면 False, 2종 이상이면 True다.
    """
    currencies = {r.currency for r in results if r.currency}
    return len(currencies) > 1


def _extract_source_ip(event: dict[str, Any]) -> Optional[str]:
    """IP를 **오직** `event.requestContext.http.sourceIp`에서만 읽는다(Req 7.8).

    요청 본문에서 IP를 받지 않는다. 경로가 없으면 None을 반환한다(상위에서 내부
    오류로 처리). 원본 IP는 로깅·저장하지 않고, 카운터 키 생성 시 즉시 SHA-256
    해시로만 쓰인다(hashing.hash_ip, Property 10).
    """
    request_context = event.get("requestContext")
    if not isinstance(request_context, dict):
        return None
    http = request_context.get("http")
    if not isinstance(http, dict):
        return None
    source_ip = http.get("sourceIp")
    if isinstance(source_ip, str) and source_ip:
        return source_ip
    return None


def _parse_body(event: dict[str, Any]) -> dict[str, Any]:
    """API Gateway HTTP API 이벤트에서 JSON 본문(dict)을 꺼낸다.

    본문이 없거나 JSON이 아니면 빈 dict를 반환한다. 본문에서는 `objectKey`만
    사용하며 IP는 절대 읽지 않는다(Req 7.8).
    """
    raw = event.get("body")
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _load_object_bytes_default(s3_client: Any, bucket: str, key: str) -> tuple[bytes, int]:
    """런타임 기본 객체 로더: S3에서 객체 바이트와 크기를 읽는다.

    먼저 `head_object`로 존재·크기를 확인하고, `get_object`로 바이트를 읽는다.
    객체가 없으면 S3가 예외를 던지며, 상위(run_search_pipeline)가 이를 검증 실패로
    매핑한다. 테스트는 이 기본 로더 대신 가짜 `load_object`를 주입해 실제 S3 접근
    없이 구동한다.
    """
    head = s3_client.head_object(Bucket=bucket, Key=key)
    size = int(head.get("ContentLength", 0))
    obj = s3_client.get_object(Bucket=bucket, Key=key)
    data = obj["Body"].read()
    return data, size


def _presign_get_default(s3_client: Any, bucket: str, key: str, expires_in: int) -> str:
    """런타임 기본 Presigned GET 발급기: 5분 유효 GET URL을 만든다(Req 8.1).

    boto3 `generate_presigned_url`을 호출한다. 테스트는 이 기본 구현 대신 가짜
    `presign_get`을 주입해 실제 서명 없이 구동한다.
    """
    return s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )


def run_search_pipeline(
    *,
    event: dict[str, Any],
    bucket: str,
    cache_table: Any,
    counter_table: Any,
    s3_client: Any,
    serp_http_get: Callable[..., dict],
    api_key_loader: Callable[[], str],
    use_mock: bool,
    monthly_limit: int,
    ip_daily_limit: int,
    load_object: Optional[Callable[[Any, str, str], tuple[bytes, int]]] = None,
    presign_get: Optional[Callable[[Any, str, str, int], str]] = None,
    serp_country: Optional[str] = None,
    serp_hl: Optional[str] = None,
    now: Optional[int] = None,
) -> PipelineResult:
    """검색 파이프라인 본체(의존성 주입). 성공 시 `PipelineResult`를 반환한다.

    모든 외부 의존성(테이블·S3·serp http_get·api_key_loader·로더·presign·시계)을
    인자로 받으므로, 테스트는 가짜를 주입해 실제 I/O 없이 전 경로를 검증할 수 있다
    (design.md Testing Strategy; Property 5/7/19/24). 어떤 경로로 끝나든 원본
    이미지는 `finally`에서 삭제된다(Req 12.1, Property 19).

    매개변수:
      event: API Gateway HTTP API(payload v2) 이벤트. 본문에서 `objectKey`만,
        IP는 `requestContext.http.sourceIp`에서만 읽는다(Req 7.8).
      bucket: Image_Bucket 이름.
      cache_table / counter_table: cache.py / rate_limit.py가 쓰는 DynamoDB Table
        (또는 테스트용 fake).
      s3_client: head/get/presign/delete를 지원하는 S3 클라이언트(또는 fake).
      serp_http_get: serp_client에 넘길 HTTP 콜러블. Mock 모드에서는 호출되지 않는다.
      api_key_loader: serp_client에 넘길 api_key 지연 로더. Mock 모드에서는 호출되지
        않는다.
      use_mock: True면 SerpApi 미호출·카운터 미증가·mock.py 데이터 반환(Req 19.1).
      monthly_limit / ip_daily_limit: 호출 상한(Req 7.3, 7.4).
      load_object: (s3_client, bucket, key) → (bytes, size) 로더. 기본은 S3 head/get.
      presign_get: (s3_client, bucket, key, expires_in) → url. 기본은 boto3 presign.
      serp_country / serp_hl: SerpApi 선택 파라미터(있을 때만 전달).
      now: 현재 epoch 초(캐시 TTL·카운터 키 기간 계산용). 미지정 시 실제 시각.

    예외:
      SearchError: 검증 실패/한도 초과/결과 없음/시간 초과 등 매핑된 오류. 호출부
        (handler)가 오류 응답으로 변환한다. 어떤 경우에도 원본은 삭제된다.
    """
    effective_now = int(time.time()) if now is None else int(now)
    effective_load_object = load_object or _load_object_bytes_default
    effective_presign_get = presign_get or _presign_get_default

    body = _parse_body(event)
    object_key = body.get("objectKey")

    deleted_needed = isinstance(object_key, str) and bool(object_key)

    try:
        # objectKey 자체가 없으면 업로드 단계가 성립하지 않은 것으로 본다(Req 17.1).
        if not isinstance(object_key, str) or not object_key:
            raise SearchError(
                ERROR_UPLOAD_FAILED,
                400,
                "objectKey가 없습니다.",
            )

        # --- 1단계: 서버 재검증(존재/크기/매직 바이트) — 실패 시 SerpApi 미호출(Req 5.1~5.4). ---
        try:
            data, size = effective_load_object(s3_client, bucket, object_key)
        except Exception as exc:  # noqa: BLE001 - 객체 미존재/접근 실패는 검증 실패로 매핑
            raise SearchError(
                ERROR_VALIDATION_FAILED,
                400,
                "업로드된 이미지를 찾을 수 없습니다.",
            ) from exc

        result = validation.validate_image(data, size_bytes=size)
        if not result.is_valid:
            # 크기 초과·매직 바이트 불일치: SerpApi를 호출하지 않고 즉시 실패(Req 5.4, Property 5).
            raise SearchError(
                ERROR_VALIDATION_FAILED,
                400,
                "이미지 검증에 실패했습니다.",
            )

        # --- 2단계: SHA-256 해시(Req 6.1). ---
        image_hash = hash_image_bytes(data)

        # --- 3단계: 캐시 조회 — 적중 시 카운터 미증가·외부 미호출(Req 6.3, 7.2, Property 7). ---
        cached_entry = cache.lookup(cache_table, image_hash)
        if cached_entry is not None:
            return PipelineResult(
                source=SOURCE_SERP,
                cached=True,
                currency_mixed=cached_entry.currency_mixed,
                results=cached_entry.results,
            )

        # --- Mock 모드: SerpApi 미호출·카운터 미증가·고정 데이터 반환(Req 19.1, Property 24). ---
        if use_mock:
            mock_results = get_mock_results()
            return PipelineResult(
                source=SOURCE_MOCK,
                cached=False,
                currency_mixed=compute_currency_mixed(mock_results),
                results=mock_results,
            )

        # --- 4단계: 호출 제한 — 월간 GLOBAL + IP 일일 조건부 원자 증가(Req 7.1~7.7). ---
        source_ip = _extract_source_ip(event)
        if source_ip is None:
            # IP는 requestContext에서만 읽는다. 없으면 안전하게 내부 오류로 처리(Req 7.8).
            raise SearchError(
                ERROR_INTERNAL_ERROR,
                500,
                "요청 IP를 확인할 수 없습니다.",
            )

        monthly_id = rate_limit.monthly_counter_id(effective_now)
        monthly_ok = rate_limit.try_increment(
            counter_table,
            monthly_id,
            monthly_limit,
            ttl_seconds=rate_limit.MONTHLY_TTL_SECONDS,
            now=effective_now,
        )
        if not monthly_ok:
            raise SearchError(ERROR_RATE_LIMITED, 429, "월간 호출 한도를 초과했습니다.")

        ip_id = rate_limit.ip_daily_counter_id(source_ip, effective_now)
        ip_ok = rate_limit.try_increment(
            counter_table,
            ip_id,
            ip_daily_limit,
            ttl_seconds=rate_limit.DAILY_TTL_SECONDS,
            now=effective_now,
        )
        if not ip_ok:
            raise SearchError(ERROR_RATE_LIMITED, 429, "일일 호출 한도를 초과했습니다.")

        # --- 5단계: 5분 Presigned GET URL 발급(Req 8.1). ---
        image_url = effective_presign_get(
            s3_client, bucket, object_key, PRESIGNED_GET_EXPIRY_SECONDS
        )

        # --- 6단계: SerpApi 호출(주입된 http_get만). 시간 초과는 SEARCH_TIMEOUT으로 매핑. ---
        try:
            visual_matches = serp_client.search_visual_matches(
                image_url=image_url,
                api_key_loader=api_key_loader,
                country=serp_country,
                hl=serp_hl,
                http_get=serp_http_get,
            )
        except TimeoutError as exc:
            raise SearchError(
                ERROR_SEARCH_TIMEOUT, 504, "검색 시간이 초과되었습니다."
            ) from exc
        except SearchError:
            raise
        except Exception as exc:  # noqa: BLE001 - 외부 호출 실패는 내부 오류로 매핑
            raise SearchError(
                ERROR_INTERNAL_ERROR, 502, "검색 처리 중 오류가 발생했습니다."
            ) from exc

        # --- 7단계: 정규화·분류·등급·정렬(Req 9.x, 11.x). ---
        normalized = normalize_visual_matches(visual_matches)
        if not normalized:
            # 정규화 후 결과 0건(Req 17.3). 카운터는 이미 증가했으나(실제 외부 호출 발생),
            # 캐시에는 저장하지 않는다. 원본은 finally에서 삭제된다.
            raise SearchError(ERROR_NO_RESULTS, 200, "검색 결과가 없습니다.")

        # --- 8단계: 캐시 저장(TTL 24h, currencyMixed 포함)(Req 6.4). ---
        currency_mixed = compute_currency_mixed(normalized)
        cache.store(
            cache_table,
            image_hash,
            normalized,
            currency_mixed,
            created_at=effective_now,
        )

        return PipelineResult(
            source=SOURCE_SERP,
            cached=False,
            currency_mixed=currency_mixed,
            results=normalized,
        )
    finally:
        # --- 9단계: 원본 즉시 삭제 — 성공·실패 모든 경로에서(Req 12.1, Property 19). ---
        # 삭제 실패는 1차 결과(성공 또는 오류)를 가리지 않도록 삼킨다(cleanup 설계).
        if deleted_needed:
            cleanup.delete_original_safe(s3_client, bucket, object_key)


def _response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    """API Gateway HTTP API(payload v2) 형식의 응답을 만든다.

    CORS 허용 출처는 API Gateway 레벨(template.yaml, Req 20.4)에서 적용하므로
    여기서는 Content-Type만 설정한다. 한글 메시지가 깨지지 않도록 ensure_ascii=False.
    """
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False),
    }


def _serialize_results(results: list[NormalizedResult]) -> list[dict[str, Any]]:
    """NormalizedResult 목록을 응답 본문용 dict 목록으로 직렬화한다.

    frozen dataclass를 `asdict`로 그대로 펼친다. 응답에 없는 값을 생성·추론하지
    않으며(Req 9.9), 저장된 값만 담는다.
    """
    return [asdict(r) for r in results]


def _success_response(result: PipelineResult) -> dict[str, Any]:
    """`PipelineResult`를 design.md 응답 스키마(JSON)로 직렬화한다."""
    return _response(
        200,
        {
            "source": result.source,
            "cached": result.cached,
            "currencyMixed": result.currency_mixed,
            "results": _serialize_results(result.results),
        },
    )


def _error_response(error: SearchError) -> dict[str, Any]:
    """`SearchError`를 안정적 errorCode를 담은 오류 응답으로 변환한다(Req 17.x)."""
    return _response(
        error.status_code,
        {"errorCode": error.error_code, "message": error.message},
    )


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Search_Lambda 진입점: `POST /search` 요청을 처리한다(design.md 전반).

    환경변수·boto3 리소스를 지연 생성해 `run_search_pipeline`에 주입할 뿐, 도메인
    로직은 모두 파이프라인/모듈에 있다(cache/rate_limit/serp_client/cleanup/
    upload_handler와 동일한 지연 import·주입 관례). 🔒 실제 SerpApi/AWS 호출은 이
    진입점에서만 실 리소스를 연결하며, 테스트는 `run_search_pipeline`에 가짜를 직접
    주입해 이 진입점을 거치지 않는다(Req 23.1).

    환경변수:
      IMAGE_BUCKET           — Image_Bucket 이름(필수).
      CACHE_TABLE            — Cache_Table 이름(필수).
      COUNTER_TABLE          — Counter_Table 이름(필수).
      USE_MOCK_SEARCH        — "true"면 Mock 모드(외부 미호출, Req 19.1).
      SERP_API_KEY_SSM_PARAM — SerpApi Key가 저장된 SSM 파라미터 이름(실 호출 시).
      AWS_REGION             — 리전(선택, boto3 기본 해석).
      MONTHLY_CALL_LIMIT / IP_DAILY_LIMIT — 호출 상한(rate_limit이 환경변수에서 읽음).

    오류는 안정적 errorCode를 담아 반환하며(Req 17.x), 어떤 경로로 끝나든 원본
    이미지는 파이프라인의 finally에서 삭제된다(Req 12.1).
    """
    bucket = os.environ.get("IMAGE_BUCKET")
    cache_table_name = os.environ.get("CACHE_TABLE")
    counter_table_name = os.environ.get("COUNTER_TABLE")
    if not bucket or not cache_table_name or not counter_table_name:
        return _error_response(
            SearchError(
                ERROR_INTERNAL_ERROR,
                500,
                "서버 리소스 설정이 올바르지 않습니다.",
            )
        )

    use_mock = os.environ.get("USE_MOCK_SEARCH", "false").strip().lower() == "true"
    region_name = os.environ.get("AWS_REGION")

    s3_client = cleanup.get_s3_client()
    cache_table = cache.get_cache_table(cache_table_name, region_name=region_name)
    counter_table = rate_limit.get_counter_table(
        counter_table_name, region_name=region_name
    )

    # api_key_loader / serp_http_get 는 Mock 모드에서는 사용되지 않는다. 실제 호출
    # 경로에서만 SSM/네트워크를 건드리도록 지연 콜러블로 구성한다(Req 8.4, 23.1).
    ssm_param = os.environ.get("SERP_API_KEY_SSM_PARAM", "")

    def _api_key_loader() -> str:
        return serp_client.load_api_key_from_ssm(ssm_param, region_name=region_name)

    try:
        result = run_search_pipeline(
            event=event,
            bucket=bucket,
            cache_table=cache_table,
            counter_table=counter_table,
            s3_client=s3_client,
            serp_http_get=serp_client._default_http_get,
            api_key_loader=_api_key_loader,
            use_mock=use_mock,
            monthly_limit=rate_limit.monthly_limit_from_env(),
            ip_daily_limit=rate_limit.ip_daily_limit_from_env(),
        )
    except SearchError as error:
        return _error_response(error)
    except Exception:  # noqa: BLE001 - 예기치 못한 오류는 내부 오류로 안전하게 매핑
        return _error_response(
            SearchError(
                ERROR_INTERNAL_ERROR,
                500,
                "일시적인 오류가 발생했습니다.",
            )
        )

    return _success_response(result)
