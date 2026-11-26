"""`hashing.py` 속성 테스트 (Property 6).

이미지 바이트 SHA-256 해시의 결정성·구별성·출력 형태에 대한 속성 기반 테스트.
외부 호출 없이 순수 모듈(`hashing.py`)만 검증한다(design.md Property 6 참조).

Property 6: 임의의 이미지 바이트에 대해 동일 바이트는 항상 동일한 SHA-256 해시를
산출하고, 서로 다른 바이트는 서로 다른 해시를 산출한다(Req 6.1).
"""

import re

from hypothesis import given, settings
from hypothesis import strategies as st

from closeller.hashing import hash_image_bytes, hash_ip

# SHA-256 16진 다이제스트: 소문자 0-9a-f, 정확히 64자.
_SHA256_HEX = re.compile(r"\A[0-9a-f]{64}\Z")

# --- 생성기(generator): 해시 입력 공간을 지능적으로 구성한다 ------------------

# 이미지 바이트는 임의 길이의 바이트열(빈 바이트열 포함)이다.
_image_bytes = st.binary(min_size=0, max_size=256)


# Feature: closeller-mvp, Property 6: SHA-256 해시 결정성
@settings(max_examples=200)
@given(data=_image_bytes)
def test_same_bytes_always_produce_same_hash(data: bytes) -> None:
    """결정성: 동일 바이트를 두 번 해시하면 항상 동일한 다이제스트가 나온다."""
    assert hash_image_bytes(data) == hash_image_bytes(data)


# Feature: closeller-mvp, Property 6: SHA-256 해시 결정성
@settings(max_examples=200)
@given(a=_image_bytes, b=_image_bytes)
def test_different_bytes_produce_different_hashes(a: bytes, b: bytes) -> None:
    """구별성: 서로 다른 바이트 입력은 서로 다른 다이제스트를 산출한다.

    같은 입력이 뽑힌 경우는 결정성 영역이므로 전제에서 제외하고,
    서로 다른 두 입력에 대해서만 해시가 달라야 함을 검증한다
    (SHA-256 충돌 저항성).
    """
    if a == b:
        assert hash_image_bytes(a) == hash_image_bytes(b)
    else:
        assert hash_image_bytes(a) != hash_image_bytes(b)


# Feature: closeller-mvp, Property 6: SHA-256 해시 결정성
@settings(max_examples=200)
@given(data=_image_bytes)
def test_hash_is_lowercase_64_char_hex(data: bytes) -> None:
    """출력 형태: 결과는 소문자 16진 문자열이며 길이가 정확히 64자다."""
    digest = hash_image_bytes(data)
    assert len(digest) == 64
    assert _SHA256_HEX.match(digest) is not None
    assert digest == digest.lower()


# Feature: closeller-mvp, Property 6: SHA-256 해시 결정성
@settings(max_examples=200)
@given(ip=st.text(min_size=0, max_size=64))
def test_ip_hash_is_deterministic_and_well_formed(ip: str) -> None:
    """IP 단방향 해시도 동일 입력에 대해 결정적이며 소문자 64자 16진이다.

    `hash_ip` 역시 SHA-256 결정성을 공유하므로 Property 6 범위에서 함께 검증한다.
    """
    first = hash_ip(ip)
    assert first == hash_ip(ip)
    assert _SHA256_HEX.match(first) is not None
