"""Upload_Lambda — `POST /uploads` 핸들러(I/O 모듈).

크롭된 이미지를 Image_Bucket에 직접 올릴 수 있도록 S3 Presigned POST를 발급하는
책임을 담당한다(design.md "Upload_Lambda (POST /uploads)" 절, Req 4.1·4.2·4.4·4.5).
Upload_Lambda는 외부 검색(SerpApi)을 호출하지 않으며 DB 쓰기도 하지 않는다. S3
presign 권한만 사용하고 3초 이내에 응답한다(design.md 경계 규칙, Req 21.6).

설계 규칙(cache.py / rate_limit.py / serp_client.py / cleanup.py와 동일한 boto3
주입 관례):
  - **import 시 boto3·네트워크 사용 금지.** 모듈 import는 부작용이 없어야 한다.
  - Presigned POST를 발급하는 S3 클라이언트는 주입 가능하게 둔다. 테스트는 실제
    AWS 호출 없이 `generate_presigned_post`만 구현한 가짜(fake) 클라이언트를 넘겨
    검증할 수 있다.
  - 런타임/핸들러용으로는 함수 본문 안에서 `import boto3`를 수행하는 지연(lazy)
    `get_s3_client()` 헬퍼를 제공한다.

순수 로직 분리(단위·속성 테스트 대상, design.md Property 1·2):
  - `generate_object_key()`: 객체 키 `uploads/<uuid4>`를 만든다(Req 4.4). 버전 4
    랜덤 UUID만 쓰며 원본 파일명 조각을 포함하지 않는다(Req 4.5, Property 1).
  - `build_presigned_post_conditions()` / `build_presigned_post_fields()`:
    Presigned POST 정책의 조건/필드 딕셔너리를 만든다 — 유효기간 300초,
    content-length-range 최대 10MB, 허용 Content-Type 고정(Req 4.2, Property 2).
  이들은 네트워크·boto3 의존이 없어 그대로 단위/속성 테스트할 수 있다.

Lambda 진입 함수(`handler`)는 위 순수 로직을 조립해 API Gateway HTTP API(payload
v2) 형식의 응답(statusCode/headers/body JSON)을 돌려준다.
"""

import json
import uuid
from typing import Any, Optional

from .validation import MAX_IMAGE_SIZE_BYTES

__all__ = [
    "KEY_PREFIX",
    "PRESIGNED_POST_EXPIRY_SECONDS",
    "MAX_UPLOAD_SIZE_BYTES",
    "ALLOWED_CONTENT_TYPES",
    "generate_object_key",
    "build_presigned_post_conditions",
    "build_presigned_post_fields",
    "create_presigned_post",
    "get_s3_client",
    "handler",
]

# 객체 키 접두사. 업로드 객체는 항상 `uploads/<uuid4>` 형태다(Req 4.4).
KEY_PREFIX: str = "uploads/"

# Presigned POST 유효 시간: 300초(5분). Req 4.2 / design.md 보안 설계.
PRESIGNED_POST_EXPIRY_SECONDS: int = 300

# 업로드 최대 크기: 10MB. validation.py의 서버 재검증 한도와 동일하게 맞춘다
# (Req 4.2, 5.2) — 한 곳(validation.MAX_IMAGE_SIZE_BYTES)에서 상수를 재사용한다.
MAX_UPLOAD_SIZE_BYTES: int = MAX_IMAGE_SIZE_BYTES

# 허용 Content-Type 고정 목록(Req 4.2). Presigned POST 정책에 고정 조건으로 넣어
# 이 목록에 없는 Content-Type 업로드를 S3가 거부하도록 한다(Req 4.8).
ALLOWED_CONTENT_TYPES: tuple[str, ...] = (
    "image/jpeg",
    "image/png",
    "image/webp",
)


def generate_object_key() -> str:
    """업로드 객체 키 `uploads/<uuid4>`를 생성한다(Req 4.4, 4.5 / Property 1).

    버전 4 랜덤 UUID(`uuid.uuid4()`)만 사용하므로 키에 원본 파일명 조각이 포함되지
    않는다(Req 4.5). 반환 형식은 항상 `uploads/` + 36자 UUID 문자열이다.
    """
    return f"{KEY_PREFIX}{uuid.uuid4()}"


def build_presigned_post_conditions(content_type: str) -> list[Any]:
    """Presigned POST 정책의 conditions 리스트를 만든다(Req 4.2 / Property 2).

    항상 포함하는 조건:
      - content-length-range: 0 ~ 10MB. 업로드 크기를 10MB로 제한한다(Req 4.2, 4.6).
      - Content-Type 고정: 주어진 `content_type`으로 정확히 일치해야 한다(Req 4.2, 4.8).

    유효기간(300초)은 boto3 `generate_presigned_post(ExpiresIn=...)`로 전달하는
    별도 인자이므로 conditions 리스트에는 넣지 않는다(정책 만료는 서명 시점에
    `ExpiresIn`으로 적용된다). 본 함수는 네트워크·boto3 의존이 없는 순수 함수다.
    """
    return [
        {"Content-Type": content_type},
        ["content-length-range", 0, MAX_UPLOAD_SIZE_BYTES],
    ]


def build_presigned_post_fields(content_type: str) -> dict[str, str]:
    """Presigned POST의 기본 fields 딕셔너리를 만든다(Req 4.2).

    Content-Type을 고정 필드로 넣어, 업로드 폼이 이 값을 그대로 전송하도록 한다.
    객체 키(`key`)와 서명 관련 필드(`policy`, `x-amz-signature` 등)는 S3가
    서명 시점에 채워 넣으므로 여기서는 포함하지 않는다.
    """
    return {"Content-Type": content_type}


def is_allowed_content_type(content_type: Optional[str]) -> bool:
    """Content-Type이 허용 목록(image/jpeg, image/png, image/webp)에 있는지 여부(Req 4.2)."""
    return isinstance(content_type, str) and content_type in ALLOWED_CONTENT_TYPES


def create_presigned_post(
    s3_client: Any,
    bucket: str,
    content_type: str,
    *,
    object_key: Optional[str] = None,
    expires_in: int = PRESIGNED_POST_EXPIRY_SECONDS,
) -> dict[str, Any]:
    """주입된 S3 클라이언트로 Presigned POST를 발급한다(Req 4.2, 4.4, 4.5).

    순수 로직(`generate_object_key`, `build_presigned_post_*`)을 조립해 boto3
    `generate_presigned_post` 호출 인자를 구성하고, 그 결과(`url`/`fields`)에
    객체 키·유효기간을 더해 반환한다. 외부 검색·DB 쓰기는 하지 않는다.

    Args:
        s3_client: `generate_presigned_post(...)`를 지원하는 S3 클라이언트
            (런타임의 boto3 클라이언트 또는 테스트용 fake).
        bucket: Image_Bucket 이름.
        content_type: 허용 Content-Type 중 하나. 정책에 고정 조건으로 들어간다.
        object_key: 객체 키. 주지 않으면 `uploads/<uuid4>`를 새로 생성한다(Req 4.4).
        expires_in: 유효기간(초). 기본 300초(Req 4.2).

    Returns:
        `{"objectKey": ..., "upload": {"url": ..., "fields": {...}},
          "expiresInSeconds": ...}` 형태의 딕셔너리.
    """
    key = object_key if object_key is not None else generate_object_key()
    conditions = build_presigned_post_conditions(content_type)
    fields = build_presigned_post_fields(content_type)

    presigned = s3_client.generate_presigned_post(
        Bucket=bucket,
        Key=key,
        Fields=fields,
        Conditions=conditions,
        ExpiresIn=expires_in,
    )

    return {
        "objectKey": key,
        "upload": {
            "url": presigned["url"],
            "fields": presigned["fields"],
        },
        "expiresInSeconds": expires_in,
    }


def _response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    """API Gateway HTTP API(payload v2) 형식의 응답을 만든다.

    CORS 허용 출처는 API Gateway 레벨(template.yaml, Req 20.4)에서 적용하므로
    여기서는 Content-Type만 설정한다.
    """
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False),
    }


def _parse_body(event: dict[str, Any]) -> dict[str, Any]:
    """API Gateway HTTP API 이벤트에서 JSON 본문을 꺼낸다.

    본문이 없거나 JSON이 아니면 빈 dict를 반환한다. 원본 파일명 같은 필드는
    사용하지 않는다(Req 4.5) — Content-Type만 읽는다.
    """
    raw = event.get("body")
    if raw is None:
        return {}
    if isinstance(raw, (dict, list)):
        return raw if isinstance(raw, dict) else {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Upload_Lambda 진입점: `POST /uploads` 요청을 처리한다(Req 4.1, 4.2, 4.4, 4.5).

    동작:
      1. 요청 본문에서 `contentType`만 읽는다(원본 파일명은 읽지도 저장하지도
         않는다 — Req 4.5).
      2. `contentType`이 허용 목록(image/jpeg, image/png, image/webp)에 없으면
         400을 반환한다(Req 4.2).
      3. 객체 키 `uploads/<uuid4>`를 만들고(Req 4.4), 유효 300초·10MB·Content-Type
         고정 조건의 Presigned POST를 발급한다(Req 4.2).
      4. objectKey/upload(url,fields)/expiresInSeconds를 담아 200으로 응답한다.

    외부 검색(SerpApi) 호출·DB 쓰기는 하지 않으며, S3 presign만 수행해 3초 이내에
    응답한다(Req 21.6, design.md 경계 규칙).

    S3 클라이언트는 런타임에 `get_s3_client()`로 지연 생성하고, 버킷 이름은
    환경변수 `IMAGE_BUCKET`에서 읽는다. 테스트는 `create_presigned_post`에 가짜
    클라이언트를 직접 주입해 이 진입점을 거치지 않고도 순수/조립 로직을 검증한다.
    """
    body = _parse_body(event)
    content_type = body.get("contentType")

    if not is_allowed_content_type(content_type):
        return _response(
            400,
            {
                "error": "UNSUPPORTED_CONTENT_TYPE",
                "message": "허용 Content-Type은 image/jpeg, image/png, image/webp 입니다.",
            },
        )

    import os

    bucket = os.environ.get("IMAGE_BUCKET")
    if not bucket:
        return _response(
            500,
            {
                "error": "INTERNAL_ERROR",
                "message": "업로드 버킷이 설정되지 않았습니다.",
            },
        )

    s3_client = get_s3_client()
    result = create_presigned_post(s3_client, bucket, content_type)
    return _response(200, result)


def get_s3_client() -> Any:
    """런타임/핸들러용 S3 클라이언트를 지연 생성해 반환한다.

    boto3를 함수 본문 안에서 import 하여, 모듈 import·단위 테스트 시점에는 boto3와
    네트워크가 필요 없도록 한다(cache.py / rate_limit.py / serp_client.py /
    cleanup.py와 동일한 주입 관례). Presigned POST 서명에는 리전별 S3 엔드포인트가
    필요하므로 리전은 boto3 기본 해석(환경변수·설정)을 따른다. 테스트는 이 헬퍼를
    호출하지 않고 가짜 클라이언트를 직접 주입한다.
    """
    import boto3

    return boto3.client("s3")
