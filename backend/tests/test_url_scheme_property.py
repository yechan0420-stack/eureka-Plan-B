"""`url_tools.py` 스킴 필터 속성 테스트 (Property 15).

정규화 파이프라인이 결과 링크를 http/https로 제한하는 근거가 되는
`is_http_scheme` 순수 함수를 검증한다. 외부 호출 없이 순수 모듈만 검증한다
(design.md "속성 ↔ 증거" 표의 P15 → url_tools 스킴 필터 매핑 참조).

Property 15: 모든 결과 링크는 http/https (Req 9.8).
스킴이 http 또는 https(대소문자 무관)인 URL만 True이고, 그 외 스킴(ftp·
javascript·data·mailto 등)이나 스킴 없는 URL은 False다. is_http_scheme가 False인
링크는 정규화 파이프라인에서 제외되므로, 살아남는 링크는 항상 http/https다.
"""

from urllib.parse import urlsplit

from hypothesis import given, settings
from hypothesis import strategies as st

from closeller.url_tools import is_http_scheme

# --- 생성기(generator): 스킴 입력 공간을 지능적으로 구성한다 ------------------

# 허용 스킴(http/https). 소문자/대문자/혼합 대소문자를 모두 포함해
# 대소문자 무관 판정(예: "HTTP" -> True)을 명시적으로 탐색한다.
_ALLOWED_SCHEME_BASE = ("http", "https")


@st.composite
def _allowed_scheme(draw: st.DrawFn) -> str:
    """http/https를 임의 대소문자 변형으로 생성한다(예: "Http", "HTTPS")."""
    base = draw(st.sampled_from(_ALLOWED_SCHEME_BASE))
    # 각 글자를 임의로 대/소문자화해 대소문자 무관성을 폭넓게 검증한다.
    flags = draw(st.lists(st.booleans(), min_size=len(base), max_size=len(base)))
    return "".join(ch.upper() if up else ch.lower() for ch, up in zip(base, flags))


# http/https가 아닌 스킴 표본(스킴 자체는 유효 형식이지만 허용 목록 밖).
_DISALLOWED_SCHEMES = (
    "ftp",
    "ftps",
    "javascript",
    "data",
    "mailto",
    "file",
    "tel",
    "ws",
    "wss",
    "sftp",
    "about",
    "chrome",
    "httpx",  # http로 시작하지만 정확히 http/https가 아님
    "shttp",  # https 를 부분 문자열로 포함하지만 일치하지 않음
)


@st.composite
def _disallowed_scheme(draw: st.DrawFn) -> str:
    """http/https가 아닌 스킴을 임의 대소문자 변형으로 생성한다."""
    base = draw(st.sampled_from(_DISALLOWED_SCHEMES))
    flags = draw(st.lists(st.booleans(), min_size=len(base), max_size=len(base)))
    return "".join(ch.upper() if up else ch.lower() for ch, up in zip(base, flags))


# URL의 나머지 부분(호스트/경로/쿼리/프래그먼트)을 적당히 생성한다.
# 스킴 판정에만 의존하도록, 흔한 URL 형태를 구성한다.
_hosts = st.sampled_from(
    (
        "example.com",
        "shop.example.co.kr",
        "www.musinsa.com",
        "localhost",
        "192.168.0.1",
        "a.b.c.d.example.org",
    )
)
_paths = st.sampled_from(("", "/", "/p/123", "/products/item-42/", "/a/b/c"))
_queries = st.sampled_from(("", "?id=1", "?a=1&b=2", "?utm_source=x"))
_fragments = st.sampled_from(("", "#top", "#section-2"))


@st.composite
def _url_with_scheme(draw: st.DrawFn, scheme: str) -> str:
    """주어진 스킴과 임의의 호스트/경로/쿼리/프래그먼트로 URL 문자열을 만든다."""
    host = draw(_hosts)
    path = draw(_paths)
    query = draw(_queries)
    fragment = draw(_fragments)
    return f"{scheme}://{host}{path}{query}{fragment}"


@st.composite
def _http_url(draw: st.DrawFn) -> str:
    """http/https 스킴(대소문자 변형 포함)을 가진 URL을 생성한다."""
    return draw(_url_with_scheme(draw(_allowed_scheme())))


@st.composite
def _non_http_url(draw: st.DrawFn) -> str:
    """http/https가 아닌 스킴을 가진 URL을 생성한다."""
    return draw(_url_with_scheme(draw(_disallowed_scheme())))


# 스킴이 없는 참조(상대 경로·호스트 상대 등). urlsplit 기준 scheme == "".
_schemeless = st.sampled_from(
    (
        "example.com/path",
        "/relative/path",
        "//protocol-relative.example.com/x",
        "path/only",
        "",
        "?query=only",
        "#fragment-only",
    )
)


# Feature: closeller-mvp, Property 15: 모든 결과 링크는 http/https
@settings(max_examples=200)
@given(url=_http_url())
def test_http_https_scheme_is_accepted(url: str) -> None:
    """http/https 스킴(대소문자 무관)을 가진 URL은 항상 True다."""
    assert is_http_scheme(url) is True


# Feature: closeller-mvp, Property 15: 모든 결과 링크는 http/https
@settings(max_examples=200)
@given(url=_non_http_url())
def test_non_http_scheme_is_rejected(url: str) -> None:
    """http/https가 아닌 스킴을 가진 URL은 항상 False다(링크에서 제외)."""
    assert is_http_scheme(url) is False


# Feature: closeller-mvp, Property 15: 모든 결과 링크는 http/https
@settings(max_examples=100)
@given(url=_schemeless)
def test_scheme_missing_is_rejected(url: str) -> None:
    """스킴이 없는 URL은 http/https가 아니므로 False다."""
    assert is_http_scheme(url) is False


# Feature: closeller-mvp, Property 15: 모든 결과 링크는 http/https
@settings(max_examples=200)
@given(
    url=st.one_of(_http_url(), _non_http_url(), _schemeless),
)
def test_accepted_links_survive_only_when_scheme_is_http_or_https(url: str) -> None:
    """파이프라인 의도와의 결속: is_http_scheme가 True인 링크만 살아남으며,
    살아남은 모든 링크의 실제 스킴은 http 또는 https다(Property 15).

    즉, 임의의 혼합 입력에 대해 "통과 여부"는 "스킴이 http/https인지"와 정확히
    일치한다. 통과한 경우 소문자 스킴이 반드시 http 또는 https임을 함께 확인한다.
    """
    survives = is_http_scheme(url)
    actual_scheme = urlsplit(url).scheme.lower()
    expected = actual_scheme in ("http", "https")

    assert survives is expected
    if survives:
        # 살아남은 링크는 http/https로만 구성된다(모든 결과 링크는 http/https).
        assert actual_scheme in ("http", "https")
