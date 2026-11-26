"""`validation.py` 단위 테스트 (예시 기반).

서버 측 재검증(크기·매직 바이트)에 대한 구체적인 예시·엣지 케이스를 검증한다.
속성 기반 테스트(Property 4)는 `test_validation_property.py`에 별도로 존재하며,
이 파일은 명시적인 정상/위조/크기 초과 사례를 결정적으로 확인한다(Req 5.2, 5.3).
"""

import pytest

from closeller.validation import (
    MAX_IMAGE_SIZE_BYTES,
    FailureReason,
    ValidationResult,
    has_valid_magic_bytes,
    is_size_within_limit,
    validate_image,
)

# --- 실제 파일 시그니처 예시 바이트 ------------------------------------------
# JPG: FF D8 FF + 임의 꼬리.
_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF"
# PNG: 89 50 4E 47 0D 0A 1A 0A + 임의 꼬리.
_PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
# WEBP: "RIFF" + 4바이트 크기 필드 + "WEBP" + 임의 꼬리.
_WEBP_BYTES = b"RIFF\x24\x00\x00\x00WEBPVP8 "


# --- 정상 시그니처: 통과해야 한다 (Req 5.3) ----------------------------------
@pytest.mark.parametrize(
    "data",
    [
        pytest.param(_JPEG_BYTES, id="jpeg"),
        pytest.param(_PNG_BYTES, id="png"),
        pytest.param(_WEBP_BYTES, id="webp"),
    ],
)
def test_valid_signatures_pass(data: bytes) -> None:
    """정상 JPG/PNG/WEBP 시그니처는 통과하고 실패 사유가 없다."""
    result = validate_image(data)
    assert result.is_valid is True
    assert result.reason is None


# --- 위조/스푸핑: 매직 바이트 불일치로 거부되어야 한다 (Req 5.3) ------------
@pytest.mark.parametrize(
    "data",
    [
        pytest.param(b"", id="empty"),
        pytest.param(b"not an image at all", id="plain-text"),
        pytest.param(b"GIF89a\x00\x00", id="gif-header"),
        pytest.param(b"\xff\xd8", id="jpeg-truncated-2byte"),
        pytest.param(b"\xff\xd9\xff", id="jpeg-near-miss"),
        pytest.param(b"\x89PNG", id="png-truncated-prefix"),
        pytest.param(b"\x89PMG\r\n\x1a\n", id="png-near-miss"),
        pytest.param(b"RIFF\x24\x00\x00\x00AVI LIST", id="riff-but-not-webp"),
        pytest.param(b"RIFF", id="riff-only-truncated"),
        pytest.param(b"WEBP\x24\x00\x00\x00RIFF", id="webp-marker-wrong-offset"),
        pytest.param(b"\x00\x00\x00\x00\x00\x00\x00\x00", id="all-zero-bytes"),
    ],
)
def test_forged_or_spoofed_content_is_rejected(data: bytes) -> None:
    """위조·절단·오프셋 불일치 등 비정상 시그니처는 BAD_MAGIC_BYTES로 거부한다."""
    result = validate_image(data)
    assert result.is_valid is False
    assert result.reason is FailureReason.BAD_MAGIC_BYTES


# --- 크기 초과: 정상 시그니처라도 거부되어야 한다 (Req 5.2, 크기 검사 우선) --
def test_oversized_input_rejected_even_with_valid_signature() -> None:
    """크기가 10MB를 초과하면 정상 시그니처라도 SIZE_EXCEEDED로 거부한다."""
    result = validate_image(_JPEG_BYTES, size_bytes=MAX_IMAGE_SIZE_BYTES + 1)
    assert result.is_valid is False
    assert result.reason is FailureReason.SIZE_EXCEEDED


def test_size_checked_before_magic_bytes() -> None:
    """크기 초과이면서 시그니처도 잘못된 경우, 먼저 걸리는 크기 사유가 반환된다."""
    result = validate_image(b"not-an-image", size_bytes=MAX_IMAGE_SIZE_BYTES + 1)
    assert result.is_valid is False
    assert result.reason is FailureReason.SIZE_EXCEEDED


# --- 경계값: 정확히 10MB는 통과, 음수 크기는 거부 ----------------------------
def test_boundary_exact_max_size_with_valid_signature_passes() -> None:
    """크기가 정확히 10MB(경계)이고 시그니처가 정상이면 통과한다."""
    result = validate_image(_PNG_BYTES, size_bytes=MAX_IMAGE_SIZE_BYTES)
    assert result.is_valid is True
    assert result.reason is None


def test_negative_size_is_rejected_as_size_exceeded() -> None:
    """음수 크기는 유효하지 않은 입력으로 보고 SIZE_EXCEEDED로 거부한다."""
    result = validate_image(_WEBP_BYTES, size_bytes=-1)
    assert result.is_valid is False
    assert result.reason is FailureReason.SIZE_EXCEEDED


def test_result_is_immutable() -> None:
    """ValidationResult는 불변(frozen) 데이터클래스다."""
    result = validate_image(_JPEG_BYTES)
    assert isinstance(result, ValidationResult)
    with pytest.raises(Exception):
        result.is_valid = False  # type: ignore[misc]


# --- 헬퍼 함수 직접 검증: is_size_within_limit (Req 5.2) ---------------------
@pytest.mark.parametrize(
    ("size_bytes", "expected"),
    [
        pytest.param(0, True, id="zero"),
        pytest.param(1, True, id="one"),
        pytest.param(MAX_IMAGE_SIZE_BYTES - 1, True, id="just-under-max"),
        pytest.param(MAX_IMAGE_SIZE_BYTES, True, id="exact-max"),
        pytest.param(MAX_IMAGE_SIZE_BYTES + 1, False, id="just-over-max"),
        pytest.param(-1, False, id="negative"),
    ],
)
def test_is_size_within_limit(size_bytes: int, expected: bool) -> None:
    """크기 경계 조건을 직접 확인한다(음수·0·경계·초과)."""
    assert is_size_within_limit(size_bytes) is expected


# --- 헬퍼 함수 직접 검증: has_valid_magic_bytes (Req 5.3) --------------------
@pytest.mark.parametrize(
    ("data", "expected"),
    [
        pytest.param(_JPEG_BYTES, True, id="jpeg-valid"),
        pytest.param(_PNG_BYTES, True, id="png-valid"),
        pytest.param(_WEBP_BYTES, True, id="webp-valid"),
        pytest.param(b"\xff\xd8\xff", True, id="jpeg-minimal-signature"),
        pytest.param(b"\x89PNG\r\n\x1a\n", True, id="png-exact-signature"),
        pytest.param(b"RIFF\x00\x00\x00\x00WEBP", True, id="webp-minimal-signature"),
        pytest.param(b"", False, id="empty"),
        pytest.param(b"\xff\xd8", False, id="jpeg-too-short"),
        pytest.param(b"RIFF\x00\x00\x00\x00AVI ", False, id="riff-non-webp"),
        pytest.param(b"GIF89a", False, id="gif"),
    ],
)
def test_has_valid_magic_bytes(data: bytes, expected: bool) -> None:
    """실제 시그니처만 True를 반환하는지 직접 확인한다."""
    assert has_valid_magic_bytes(data) is expected
