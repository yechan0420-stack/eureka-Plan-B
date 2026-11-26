"""원본 이미지 즉시 삭제(I/O 모듈).

Search_Lambda가 검색 처리를 완료하면 성공·실패 여부와 무관하게 Image_Bucket의
원본 이미지를 즉시 삭제한다(Req 12.1). 핸들러(task 16.4)는 이 모듈의 삭제 함수를
`finally` 성격의 경로에서 호출하여, 정규화 성공·검증 실패·한도 초과·SerpApi 실패 등
모든 처리 경로에서 삭제가 보장되도록 한다(design.md Property 19, 보안 설계 "원본 삭제"
행). S3 Lifecycle(1일)과 함께 이중으로 원본을 제거한다(Req 12.2).

설계 규칙(cache.py / rate_limit.py / serp_client.py와 동일한 boto3 주입 관례):
  - **import 시 boto3·네트워크 사용 금지.** 모듈 import는 부작용이 없어야 한다.
  - 핵심 삭제 함수는 (bucket, key)로 객체를 삭제하며, S3 클라이언트를 인자로 주입받는다.
    테스트는 실제 AWS 호출 없이 가짜(fake) S3 클라이언트를 넘겨 검증할 수 있다.
  - 런타임/핸들러용으로는 함수 본문 안에서 `import boto3`를 수행하는 지연(lazy)
    `get_s3_client()` 헬퍼를 제공한다. 이렇게 하면 순수 모듈 import·단위 테스트에서
    boto3가 필요 없다.

삭제 실패 처리(Req 12.1 해석):
  요구사항 12.1은 "검색 처리를 완료하면 성공·실패 여부와 무관하게 원본을 즉시 삭제한다"
  이다. 핵심 의도는 (a) 삭제가 모든 처리 경로에서 시도되는 것과 (b) 사용자 데이터가
  서버에 남지 않는 것이다. 핸들러가 이 함수를 finally 경로에서 호출하므로, 삭제 자체가
  실패하더라도 그 예외가 1차 처리 결과(정규화 결과 또는 원래의 오류 응답)를 가리면 안
  된다. 따라서 복원력 있는 헬퍼 `delete_original_safe()`를 제공한다. 이 헬퍼는 삭제를
  시도하고, 삭제가 성공했는지 여부를 bool로 보고하며, 삭제 중 발생한 예외를 삼켜
  1차 결과를 덮어쓰지 않는다. (삭제 실패 시에도 S3 Lifecycle 1일 규칙이 원본을 제거하는
  2차 안전장치로 동작한다 — Req 12.2.) 예외를 그대로 전파해야 하는 호출부를 위해서는
  저수준 `delete_object()`를 별도로 제공한다.
"""

from typing import Any

__all__ = ["delete_object", "delete_original_safe", "get_s3_client"]


def delete_object(s3_client: Any, bucket: str, key: str) -> None:
    """S3 객체(bucket, key)를 삭제한다(Req 12.1).

    주입된 `s3_client`로 `delete_object`를 호출한다. 테스트는 실제 AWS 호출 없이
    가짜 클라이언트를 넘겨 호출 인자를 검증할 수 있다(boto3·네트워크 미사용).

    이 함수는 S3 호출에서 발생한 예외를 **그대로 전파**한다. 핸들러의 finally 경로처럼
    삭제 실패가 1차 결과를 가리면 안 되는 자리에서는 `delete_original_safe()`를 쓴다.

    Args:
        s3_client: `delete_object(Bucket=..., Key=...)`를 지원하는 S3 클라이언트
            (런타임의 boto3 클라이언트 또는 테스트용 fake).
        bucket: Image_Bucket 이름.
        key: 삭제할 객체 키(예: ``uploads/<uuid4>``).
    """
    s3_client.delete_object(Bucket=bucket, Key=key)


def delete_original_safe(s3_client: Any, bucket: str, key: str) -> bool:
    """원본 객체 삭제를 시도하되, 삭제 실패가 1차 결과를 가리지 않도록 한다(Req 12.1).

    핸들러(task 16.4)가 성공·실패 무관의 finally 성격 경로에서 호출하도록 설계한
    복원력 있는 헬퍼다. 내부적으로 `delete_object()`를 호출하고, 그 과정에서 발생한
    모든 예외를 삼켜(swallow) 1차 처리 결과(정규화 결과 또는 원래 오류 응답)를 덮어쓰지
    않는다. 삭제가 실패하더라도 S3 Lifecycle(1일) 규칙이 2차 안전장치로 원본을
    제거한다(Req 12.2).

    Args:
        s3_client: `delete_object(Bucket=..., Key=...)`를 지원하는 S3 클라이언트.
        bucket: Image_Bucket 이름.
        key: 삭제할 객체 키.

    Returns:
        삭제 호출이 예외 없이 완료되면 ``True``, 삭제 중 예외가 발생해 삼켜졌으면
        ``False``. 반환값은 호출부가 로깅·관찰에 사용할 수 있으며, 어느 경우에도
        예외는 전파되지 않는다.
    """
    try:
        delete_object(s3_client, bucket, key)
        return True
    except Exception:
        # 삭제 실패는 1차 결과를 가리지 않도록 삼킨다(Req 12.1 의도).
        # Lifecycle 1일 규칙이 원본을 제거하는 2차 안전장치다(Req 12.2).
        return False


def get_s3_client() -> Any:
    """런타임/핸들러용 S3 클라이언트를 지연 생성해 반환한다.

    boto3를 함수 본문 안에서 import 하여, 모듈 import·단위 테스트 시점에는 boto3와
    네트워크가 필요 없도록 한다(cache.py / rate_limit.py / serp_client.py와 동일한
    주입 관례). 테스트는 이 헬퍼를 호출하지 않고 가짜 클라이언트를 직접 주입한다.

    리전은 boto3 기본 해석(환경변수·설정)을 따른다.
    """
    import boto3

    return boto3.client("s3")
