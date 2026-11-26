"""중복 판정 기준 URL 정규화 속성 테스트 (Property 14 — url_tools 부분).

`url_tools.normalize_url`은 중복 판정의 기준값을 만든다(Req 9.6). 같은 상품을
가리키는 URL이 스킴·호스트 대소문자, 끝 슬래시, 프래그먼트, 추적 파라미터, 쿼리
순서 차이로 달라 보여도 하나의 정규화 값으로 수렴해야 하며(그래서 같은 그룹으로
묶여 중복 제거된다), 경로나 비추적 쿼리 키가 실제로 다르면 서로 다른 값이어야 한다.

design.md "속성 ↔ 증거" 표는 P14를 `test_dedup.py`(대상 `url_tools.py`+`normalize.py`)에
연결한다. 본 파일은 그 중 `url_tools` 정규화 부분을 다룬다(normalize 통합 부분은 9.5).
외부 호출 없이 순수 모듈(`url_tools.py`)만 검증한다.

Property 14: 중복 제거 후 정규화 URL 유일, 그룹당 첫 1건.
"""

from urllib.parse import parse_qsl, urlsplit

from hypothesis import given, settings
from hypothesis import strategies as st

from closeller.url_tools import normalize_url

# --- 생성기(generator): 정규화 입력 공간을 지능적으로 구성한다 ----------------

# 호스트 레이블(ASCII 소문자/숫자). 호스트는 실무상 ASCII이며, 유니코드 대소문자
# 접힘(예: 'ı'↔'I'→'i')의 비왕복성은 호스트 정규화와 무관한 생성기 잡음이므로 배제한다.
_host_label = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
    min_size=1,
    max_size=8,
)

# 경로 세그먼트: 슬래시·물음표·샵·퍼센트 없는 안전 ASCII 문자만 사용(정규화 규칙 격리).
_path_segment = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_",
    min_size=1,
    max_size=8,
)

# 비추적 쿼리 키: utm_ 접두사·알려진 추적 키와 겹치지 않도록 소문자 영문으로 제한.
# (추적 키 집합과의 우연한 충돌을 피하려고 접두사 "q"를 붙인다.)
_nontracking_key = st.builds(
    lambda s: "q" + s,
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=6),
)
_query_value = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    min_size=0,
    max_size=6,
)

# 제거 대상 추적 파라미터 이름(utm_* 접두사 + 문서화된 집합).
_tracking_name = st.one_of(
    st.builds(lambda s: "utm_" + s, st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=6)),
    st.sampled_from(
        [
            "gclid",
            "fbclid",
            "msclkid",
            "yclid",
            "igshid",
            "mc_eid",
            "mc_cid",
            "ref",
            "referrer",
            "spm",
        ]
    ),
)


@st.composite
def _base_url(draw: st.DrawFn) -> str:
    """스킴·호스트·경로로만 이루어진 결정적 기준 URL(쿼리·프래그먼트 없음)."""
    scheme = draw(st.sampled_from(("http", "https")))
    host = draw(_host_label) + "." + draw(st.sampled_from(("com", "co", "net", "io")))
    segments = draw(st.lists(_path_segment, min_size=0, max_size=3))
    path = "".join("/" + seg for seg in segments)
    return f"{scheme}://{host}{path}"


def _swap_case(text: str) -> str:
    """각 문자의 대소문자를 뒤집는다(스킴·호스트 대소문자 불변성 검사용)."""
    return text.swapcase()


# Feature: closeller-mvp, Property 14: 중복 제거 후 정규화 URL 유일, 그룹당 첫 1건
@settings(max_examples=200)
@given(url=_base_url())
def test_normalize_is_idempotent(url: str) -> None:
    """멱등성: 정규화 결과를 다시 정규화해도 값이 바뀌지 않는다.

    정규화 값이 중복 판정 기준이 되려면 안정점(fixed point)이어야 한다.
    """
    once = normalize_url(url)
    assert normalize_url(once) == once


# Feature: closeller-mvp, Property 14: 중복 제거 후 정규화 URL 유일, 그룹당 첫 1건
@settings(max_examples=200)
@given(url=_base_url(), fragment=st.text(max_size=12))
def test_fragment_does_not_affect_normalization(url: str, fragment: str) -> None:
    """프래그먼트(`#...`)만 다른 URL은 같은 정규화 값으로 수렴한다 → 중복으로 묶인다."""
    with_fragment = url + "#" + fragment
    assert normalize_url(with_fragment) == normalize_url(url)


# Feature: closeller-mvp, Property 14: 중복 제거 후 정규화 URL 유일, 그룹당 첫 1건
@settings(max_examples=200)
@given(url=_base_url())
def test_scheme_host_case_is_invariant(url: str) -> None:
    """스킴·호스트의 대소문자 차이만 있는 URL은 같은 정규화 값으로 수렴한다.

    경로는 대소문자를 보존해야 하므로 스킴+호스트 구간만 대소문자를 뒤집는다.
    """
    parts = urlsplit(url)
    # "scheme://host" 접두 구간의 대소문자만 뒤집고 경로는 그대로 둔다.
    prefix = f"{parts.scheme}://{parts.netloc}"
    swapped = _swap_case(prefix) + parts.path
    assert normalize_url(swapped) == normalize_url(url)


# Feature: closeller-mvp, Property 14: 중복 제거 후 정규화 URL 유일, 그룹당 첫 1건
@settings(max_examples=200)
@given(url=_base_url())
def test_trailing_slash_is_invariant(url: str) -> None:
    """경로 끝 슬래시 유무만 다른 URL은 같은 정규화 값으로 수렴한다."""
    assert normalize_url(url + "/") == normalize_url(url)


# Feature: closeller-mvp, Property 14: 중복 제거 후 정규화 URL 유일, 그룹당 첫 1건
@settings(max_examples=200)
@given(
    url=_base_url(),
    tracking=st.lists(st.tuples(_tracking_name, _query_value), min_size=1, max_size=4),
)
def test_tracking_params_are_removed(url: str, tracking: list) -> None:
    """추적 파라미터만 추가된 URL은 추적 파라미터가 없는 URL과 같은 값으로 수렴한다."""
    from urllib.parse import urlencode

    tracked = url + "?" + urlencode(tracking)
    assert normalize_url(tracked) == normalize_url(url)
    # 정규화 결과 쿼리에는 어떤 추적 키도 남지 않는다.
    normalized_query = urlsplit(normalize_url(tracked)).query
    for key, _ in parse_qsl(normalized_query, keep_blank_values=True):
        lowered = key.lower()
        assert not lowered.startswith("utm_")
        assert lowered not in {
            "gclid",
            "fbclid",
            "msclkid",
            "yclid",
            "igshid",
            "mc_eid",
            "mc_cid",
            "ref",
            "referrer",
            "spm",
        }


@st.composite
def _distinct_query(draw: st.DrawFn) -> list:
    """키가 서로 다른 비추적 쿼리 쌍 목록(순서 뒤섞기 검사용)."""
    keys = draw(
        st.lists(_nontracking_key, min_size=1, max_size=5, unique=True)
    )
    return [(k, draw(_query_value)) for k in keys]


# Feature: closeller-mvp, Property 14: 중복 제거 후 정규화 URL 유일, 그룹당 첫 1건
@settings(max_examples=200)
@given(url=_base_url(), query=_distinct_query(), data=st.randoms(use_true_random=False))
def test_query_param_ordering_is_invariant(url: str, query: list, data) -> None:
    """비추적 쿼리 키의 나열 순서만 다른 URL은 같은 정규화 값으로 수렴한다.

    남은 쿼리는 키 기준으로 정렬되므로 입력 순서에 영향받지 않아야 한다.
    """
    from urllib.parse import urlencode

    shuffled = list(query)
    data.shuffle(shuffled)
    a = url + "?" + urlencode(query)
    b = url + "?" + urlencode(shuffled)
    assert normalize_url(a) == normalize_url(b)


# Feature: closeller-mvp, Property 14: 중복 제거 후 정규화 URL 유일, 그룹당 첫 1건
@settings(max_examples=200)
@given(
    base=_base_url(),
    extra=_path_segment,
)
def test_distinct_path_normalizes_differently(base: str, extra: str) -> None:
    """경로가 실제로 다른 두 URL은 서로 다른 값으로 정규화된다 → 중복으로 묶이지 않는다."""
    longer = base + "/" + extra
    assert normalize_url(longer) != normalize_url(base)


# Feature: closeller-mvp, Property 14: 중복 제거 후 정규화 URL 유일, 그룹당 첫 1건
@settings(max_examples=200)
@given(url=_base_url(), key=_nontracking_key, value=_query_value)
def test_distinct_nontracking_query_normalizes_differently(
    url: str, key: str, value: str
) -> None:
    """비추적 쿼리 키 하나만 추가해도 쿼리 없는 URL과 다른 값으로 정규화된다."""
    with_query = url + "?" + key + "=" + value
    assert normalize_url(with_query) != normalize_url(url)


def _dedup_keep_first(links: list) -> list:
    """정규화 URL 기준으로 그룹의 첫 1건만 남기는 참조 중복 제거(테스트용 오라클).

    Property 14가 요구하는 "그룹당 첫 1건" 의미를 url_tools 수준에서 재현한다.
    """
    seen: set[str] = set()
    kept: list[str] = []
    for link in links:
        norm = normalize_url(link)
        if norm not in seen:
            seen.add(norm)
            kept.append(link)
    return kept


# Feature: closeller-mvp, Property 14: 중복 제거 후 정규화 URL 유일, 그룹당 첫 1건
@settings(max_examples=200)
@given(
    base=_base_url(),
    fragments=st.lists(st.text(max_size=6), min_size=1, max_size=4),
)
def test_dedup_by_normalized_url_keeps_first_and_is_unique(
    base: str, fragments: list
) -> None:
    """프래그먼트만 다른 변형들(= 같은 그룹)을 모으면, 정규화 기준 중복 제거 결과는
    정규화 URL이 유일하고 각 그룹의 첫 번째 항목만 남는다(Property 14 핵심).
    """
    # base 와, 프래그먼트만 다른 여러 변형(모두 같은 정규화 값)을 섞어 넣는다.
    variants = [base] + [base + "#" + frag for frag in fragments]
    kept = _dedup_keep_first(variants)

    # 같은 그룹이므로 정확히 1건만 남고, 그것은 첫 번째 항목(base)이다.
    assert kept == [base]

    # 정규화 값의 유일성: 남은 항목들의 정규화 URL에 중복이 없다.
    normalized = [normalize_url(link) for link in kept]
    assert len(normalized) == len(set(normalized))
