"""IP 단방향 해시 속성 테스트 (Property 10).

요청 IP 주소는 Counter_Table에 SHA-256 단방향 해시로만 저장되며 원본 IP는
저장하지 않는다. 외부 호출 없이 순수 모듈(`hashing.py`)만 검증한다
(design.md Property 10, Req 7.8 참조).

Property 10: 임의의 요청 IP 주소에 대해 Counter_Table에 저장되는 값은 단방향
해시이며 원본 IP 주소를 포함하지 않는다. 해시는 고정 길이(소문자 64자 16진)이고,
동일 IP는 항상 동일한 해시를, 서로 다른 IP는 서로 다른 해시를 산출한다(Req 7.8).
"""

import re

from hypothesis import given, settings
from hypothesis import strategies as st

from closeller.hashing import hash_ip

# SHA-256 16진 다이제스트: 소문자 0-9a-f, 정확히 64자.
_SHA256_HEX = re.compile(r"\A[0-9a-f]{64}\Z")

# --- 생성기(generator): 대표적인 IP 주소 입력 공간을 지능적으로 구성한다 -------

# IPv4 점-십진 표기(dotted-quad). 각 옥텟은 0-255. 항상 '.'을 포함하므로
# 16진 전용 출력에는 결코 부분 문자열로 나타날 수 없다.
_ipv4 = st.builds(
    lambda a, b, c, d: f"{a}.{b}.{c}.{d}",
    *([st.integers(min_value=0, max_value=255)] * 4),
)

# IPv6 축약/완전 표기. 콜론을 포함하며 16진 그룹 사이에 ':'이 들어가므로
# 전체 문자열은 64자 연속 16진 다이제스트의 부분 문자열이 될 수 없다.
_ipv6 = st.builds(
    lambda groups: ":".join(f"{g:x}" for g in groups),
    st.lists(
        st.integers(min_value=0, max_value=0xFFFF),
        min_size=8,
        max_size=8,
    ),
)

# 형태/결정성 검사를 위한 임의 텍스트(비정상·경계 입력 포함).
_arbitrary_text = st.text(min_size=0, max_size=64)

# 대표 IP 주소: IPv4 · IPv6 위주로, 일부 임의 텍스트를 섞어 강인하게 검증한다.
_ip = st.one_of(_ipv4, _ipv6, _arbitrary_text)

# 부분 문자열 비포함(non-containment)을 의미 있게 검사하기 위한 "실제" IP.
# dotted IPv4는 항상 '.'을, IPv6은 항상 ':'을 포함하므로 16진 다이제스트에
# 절대 부분 문자열로 나타날 수 없다.
_realistic_ip = st.one_of(_ipv4, _ipv6)


# Feature: closeller-mvp, Property 10: IP는 단방향 해시로만 저장
@settings(max_examples=200)
@given(ip=_realistic_ip)
def test_hash_does_not_contain_original_ip(ip: str) -> None:
    """단방향성: 산출된 해시에는 원본 IP가 부분 문자열로 포함되지 않는다.

    대표 IP(IPv4 점-십진, IPv6 콜론 표기)는 항상 '.' 또는 ':'을 포함한다.
    SHA-256 16진 다이제스트는 [0-9a-f]만으로 구성되므로 이러한 구분 문자가
    들어간 원본 IP는 결코 다이제스트의 부분 문자열이 될 수 없다. 즉 저장된
    값으로부터 원본 IP를 그대로 읽어낼 수 없음을 보장한다.
    """
    digest = hash_ip(ip)
    assert ip not in digest


# Feature: closeller-mvp, Property 10: IP는 단방향 해시로만 저장
@settings(max_examples=200)
@given(ip=_ip)
def test_hash_is_fixed_size_lowercase_hex(ip: str) -> None:
    """출력 형태: 입력과 무관하게 소문자 16진 64자 고정 길이 해시다.

    저장되는 값은 가변 길이의 원본 IP가 아니라 고정 크기 단방향 해시임을
    확인한다(Counter_Table에 원본 IP를 저장하지 않음).
    """
    digest = hash_ip(ip)
    assert len(digest) == 64
    assert _SHA256_HEX.match(digest) is not None
    assert digest == digest.lower()


# Feature: closeller-mvp, Property 10: IP는 단방향 해시로만 저장
@settings(max_examples=200)
@given(ip=_ip)
def test_hash_is_deterministic(ip: str) -> None:
    """결정성: 동일 IP는 항상 동일한 해시를 산출한다.

    일일 카운터 키 `IP#<hash>#YYYY-MM-DD`가 성립하려면 같은 IP가 같은 해시로
    매핑되어야 한다.
    """
    assert hash_ip(ip) == hash_ip(ip)


# Feature: closeller-mvp, Property 10: IP는 단방향 해시로만 저장
@settings(max_examples=200)
@given(a=_ip, b=_ip)
def test_distinct_ips_produce_distinct_hashes(a: str, b: str) -> None:
    """구별성: 서로 다른 IP 문자열은 서로 다른 해시를 산출한다.

    같은 입력이 뽑힌 경우는 결정성 영역이므로 전제에서 제외하고, 서로 다른
    두 IP에 대해서만 해시가 달라야 함을 검증한다(SHA-256 충돌 저항성).
    """
    if a == b:
        assert hash_ip(a) == hash_ip(b)
    else:
        assert hash_ip(a) != hash_ip(b)
