"""이미지 서버 재검증(순수 모듈).

Search_Lambda가 SerpApi를 호출하기 전에 수행하는 서버 측 재검증을 담당한다.
I/O·외부 의존성(boto3·네트워크·파일)이 없는 순수 함수만 포함하며,
바이트(및 크기)를 입력받아 결정적인 결과를 반환한다(design.md 모듈 분리표 참조).

- 크기 검증: 객체 크기가 10MB 이하인지 확인한다(Req 5.2).
- 매직 바이트 검증: 파일 내용의 시그니처가 JPG/PNG/WEBP 중 하나인지 확인한다(Req 5.3).
- 검증에 실패하면 어떤 검사에서 실패했는지 식별 가능한 결과를 돌려주며,
  호출 측(handler)은 이를 근거로 SerpApi를 호출하지 않고 오류를 반환한다(Req 5.4).
"""

from dataclasses import dataclass
from enum import Enum

# 허용 최대 크기: 10MB (Req 5.2). 바이트 단위 모듈 상수로 고정한다.
MAX_IMAGE_SIZE_BYTES: int = 10 * 1024 * 1024

# 매직 바이트(파일 시그니처) 상수 (Req 5.3).
# JPG: FF D8 FF (SOI + 마커 시작). 세 번째 바이트까지로 JPEG 계열을 식별한다.
_JPEG_SIGNATURE: bytes = b"\xff\xd8\xff"
# PNG: 89 50 4E 47 0D 0A 1A 0A (8바이트 고정 시그니처).
_PNG_SIGNATURE: bytes = b"\x89PNG\r\n\x1a\n"
# WEBP: RIFF 컨테이너 — 바이트 0~3 == "RIFF", 바이트 8~11 == "WEBP".
_WEBP_RIFF: bytes = b"RIFF"
_WEBP_FORMAT: bytes = b"WEBP"


class FailureReason(Enum):
    """검증 실패 사유.

    검증을 통과하면 사용하지 않으며, 실패 시 어떤 검사에서 걸렸는지 구분한다.
    크기 검사를 매직 바이트 검사보다 먼저 수행한다.
    """

    SIZE_EXCEEDED = "SIZE_EXCEEDED"      # 크기 10MB 초과 (Req 5.2)
    BAD_MAGIC_BYTES = "BAD_MAGIC_BYTES"  # JPG/PNG/WEBP 시그니처 불일치 (Req 5.3)


@dataclass(frozen=True)
class ValidationResult:
    """검증 결과(불변).

    `is_valid`가 True면 `reason`은 None이다.
    실패 시 `reason`에 첫 번째로 걸린 검사의 사유가 담긴다.
    """

    is_valid: bool
    reason: FailureReason | None = None


def is_size_within_limit(size_bytes: int) -> bool:
    """객체 크기가 허용 범위(10MB 이하)인지 여부를 반환한다(Req 5.2).

    음수 크기는 유효하지 않은 입력으로 보고 거부한다.
    """
    return 0 <= size_bytes <= MAX_IMAGE_SIZE_BYTES


def has_valid_magic_bytes(data: bytes) -> bool:
    """바이트 시그니처가 JPG/PNG/WEBP 중 하나인지 여부를 반환한다(Req 5.3).

    실제 파일 시그니처만 통과시키며, 확장자나 선언된 Content-Type은 신뢰하지 않는다.
    """
    if data.startswith(_JPEG_SIGNATURE):
        return True
    if data.startswith(_PNG_SIGNATURE):
        return True
    # WEBP: "RIFF"로 시작하고, 8번째 바이트부터 "WEBP"가 와야 한다.
    if data[0:4] == _WEBP_RIFF and data[8:12] == _WEBP_FORMAT:
        return True
    return False


def validate_image(data: bytes, size_bytes: int | None = None) -> ValidationResult:
    """이미지 바이트에 대해 크기·매직 바이트 검증을 수행한다(Req 5.2, 5.3).

    `size_bytes`가 주어지지 않으면 `data`의 길이를 크기로 사용한다.
    크기 검사를 먼저 수행하고, 통과하면 매직 바이트를 검사한다.
    어느 하나라도 실패하면 즉시 실패 사유와 함께 반환한다(Req 5.4 근거).
    """
    effective_size = len(data) if size_bytes is None else size_bytes

    if not is_size_within_limit(effective_size):
        return ValidationResult(is_valid=False, reason=FailureReason.SIZE_EXCEEDED)

    if not has_valid_magic_bytes(data):
        return ValidationResult(is_valid=False, reason=FailureReason.BAD_MAGIC_BYTES)

    return ValidationResult(is_valid=True)
