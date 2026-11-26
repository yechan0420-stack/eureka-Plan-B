"""`validation.py` 속성 테스트 (Property 4).

서버 측 재검증(크기·매직 바이트)에 대한 속성 기반 테스트.
외부 호출 없이 순수 모듈만 검증한다(design.md Property 4 참조).
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from closeller.validation import (
    MAX_IMAGE_SIZE_BYTES,
    FailureReason,
    validate_image,
)

# 매직 바이트(파일 시그니처) 상수 — validation.py와 동일한 정의를 테스트 측에서 독립적으로 재현한다.
_JPEG_SIGNATURE = b"\xff\xd8\xff"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_WEBP_RIFF = b"RIFF"
_WEBP_FORMAT = b"WEBP"


def _reference_has_valid_magic(data: bytes) -> bool:
    """테스트 전용 독립 오라클: 실제 JPG/PNG/WEBP 시그니처 여부.

    피검증 함수와 같은 로직을 중복 구현하지 않기 위해, 사양에 기술된
    시그니처 규칙을 그대로 명시적으로 재현한다(실측 바이트 기준 판정).
    """
    if data.startswith(_JPEG_SIGNATURE):
        return True
    if data.startswith(_PNG_SIGNATURE):
        return True
    if data[0:4] == _WEBP_RIFF and data[8:12] == _WEBP_FORMAT:
        return True
    return False


# --- 생성기(generator): 입력 공간을 지능적으로 구성한다 ----------------------

# 임의의 바이트열(대부분 시그니처 불일치 → 거부 경로를 주로 탐색).
_arbitrary_bytes = st.binary(min_size=0, max_size=64)


@st.composite
def _real_image_bytes(draw: st.DrawFn) -> bytes:
    """실제 JPG/PNG/WEBP 시그니처로 시작하는 유효 크기 바이트열을 생성한다."""
    kind = draw(st.sampled_from(("jpg", "png", "webp")))
    tail = draw(st.binary(min_size=0, max_size=48))
    if kind == "jpg":
        return _JPEG_SIGNATURE + tail
    if kind == "png":
        return _PNG_SIGNATURE + tail
    # webp: 바이트 0~3 "RIFF", 4~7 임의(파일 크기 필드), 8~11 "WEBP"
    middle = draw(st.binary(min_size=4, max_size=4))
    return _WEBP_RIFF + middle + _WEBP_FORMAT + tail


# Feature: closeller-mvp, Property 4: 매직 바이트 검증은 실제 JPG/PNG/WEBP만 통과
@settings(max_examples=300)
@given(data=_arbitrary_bytes)
def test_magic_byte_validation_passes_only_real_image_signatures(data: bytes) -> None:
    """임의 바이트 입력에 대해, 유효 크기이면서 실제 시그니처일 때만 통과한다.

    - 유효 크기(<= 10MB) + 실제 JPG/PNG/WEBP 시그니처  -> is_valid == True
    - 유효 크기 + 시그니처 불일치                       -> BAD_MAGIC_BYTES 거부
    데이터 길이를 크기로 사용하므로 이 생성기는 항상 크기 제한 이내다.
    """
    result = validate_image(data)
    expected_valid = _reference_has_valid_magic(data)

    assert result.is_valid is expected_valid
    if expected_valid:
        assert result.reason is None
    else:
        assert result.reason is FailureReason.BAD_MAGIC_BYTES


# Feature: closeller-mvp, Property 4: 매직 바이트 검증은 실제 JPG/PNG/WEBP만 통과
@settings(max_examples=150)
@given(data=_real_image_bytes())
def test_real_signature_bytes_within_limit_always_pass(data: bytes) -> None:
    """실제 시그니처 + 크기 제한 이내 입력은 항상 통과한다."""
    result = validate_image(data)
    assert result.is_valid is True
    assert result.reason is None


# Feature: closeller-mvp, Property 4: 매직 바이트 검증은 실제 JPG/PNG/WEBP만 통과
@settings(max_examples=150)
@given(data=_real_image_bytes(), overflow=st.integers(min_value=1, max_value=10**9))
def test_oversized_input_is_rejected_even_with_real_signature(
    data: bytes, overflow: int
) -> None:
    """크기 초과 입력은 실제 시그니처를 가졌더라도 거부된다(크기 검사 우선)."""
    oversized = MAX_IMAGE_SIZE_BYTES + overflow
    result = validate_image(data, size_bytes=oversized)
    assert result.is_valid is False
    assert result.reason is FailureReason.SIZE_EXCEEDED


# Feature: closeller-mvp, Property 4: 매직 바이트 검증은 실제 JPG/PNG/WEBP만 통과
@settings(max_examples=150)
@given(data=_arbitrary_bytes, size_bytes=st.integers(min_value=0, max_value=MAX_IMAGE_SIZE_BYTES))
def test_within_limit_result_matches_signature_for_explicit_size(
    data: bytes, size_bytes: int
) -> None:
    """명시적 크기가 제한 이내일 때, 통과 여부는 오직 실제 시그니처로만 결정된다."""
    result = validate_image(data, size_bytes=size_bytes)
    expected_valid = _reference_has_valid_magic(data)
    assert result.is_valid is expected_valid
    if not expected_valid:
        assert result.reason is FailureReason.BAD_MAGIC_BYTES
