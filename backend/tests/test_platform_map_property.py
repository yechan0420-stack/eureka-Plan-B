"""도메인 분류 속성 테스트 (Property 16).

판매 페이지 링크의 호스트를 Platform_Map과 대조해 (플랫폼명, 국내/해외 구분)으로
분류하는 `classify_platform` 순수 함수를 검증한다. 외부 호출 없이 순수 모듈
(`platform_map.py`)만 검증한다(design.md "속성 ↔ 증거" 표의 P16 →
platform_map 분류 매핑 참조).

Property 16: 도메인 분류는 결정적이며, Platform_Map에 정의된 도메인은 해당
플랫폼과 국내/해외 구분으로, 매핑되지 않고 분류 근거가 없는 도메인은 "기타"·
국내/해외 "미확인"으로 분류된다(Req 10.1, 10.3, 10.4, 10.5).

기대값은 Platform_Map 자체에서 파생한다(중복 표를 하드코딩하지 않음). 이렇게 해야
단일 출처(Req 10.6)와 테스트가 항상 동기화된다.
"""

from urllib.parse import urlsplit

from hypothesis import given, settings
from hypothesis import strategies as st

from closeller.platform_map import (
    PLATFORM_MAP,
    PLATFORM_OTHER,
    REGION_DOMESTIC,
    REGION_OVERSEAS,
    REGION_UNKNOWN,
    classify_platform,
)

# 허용되는 국내/해외 구분 값 집합. region 불변식 검사에 쓴다.
_VALID_REGIONS = frozenset({REGION_DOMESTIC, REGION_OVERSEAS, REGION_UNKNOWN})

# Platform_Map의 매핑 도메인 목록(단일 출처에서 파생).
_MAPPED_DOMAINS = tuple(PLATFORM_MAP.keys())


# --- 생성기(generator): 분류 입력 공간을 지능적으로 구성한다 -----------------

# URL 구성 요소. 스킴 판정·경로/쿼리/프래그먼트는 분류 결과에 영향을 주지 않아야
# 하므로 다양하게 섞어 호스트만으로 결정됨을 폭넓게 검증한다.
_schemes = st.sampled_from(("http", "https"))
_subdomain_labels = st.sampled_from(("m", "shop", "www2", "store", "en", "kr", "api"))
_paths = st.sampled_from(("", "/", "/p/123", "/products/item-42/", "/a/b/c"))
_queries = st.sampled_from(("", "?id=1", "?a=1&b=2", "?utm_source=x"))
_fragments = st.sampled_from(("", "#top", "#section-2"))


def _random_case(draw: st.DrawFn, text: str) -> str:
    """문자열의 각 글자를 임의로 대/소문자화한다(호스트 소문자 정규화 검증용)."""
    flags = draw(st.lists(st.booleans(), min_size=len(text), max_size=len(text)))
    return "".join(ch.upper() if up else ch for ch, up in zip(text, flags))


@st.composite
def _mapped_link(draw: st.DrawFn) -> tuple[str, tuple[str, str]]:
    """Platform_Map에 적중하는 링크와 그 기대 분류값을 함께 생성한다.

    매핑 도메인에서 출발해 스킴·`www.` 접두·하위 도메인·경로/쿼리/프래그먼트·
    호스트 대소문자를 임의로 변형한다. 기대값은 PLATFORM_MAP에서 직접 파생한다.
    """
    domain = draw(st.sampled_from(_MAPPED_DOMAINS))
    expected = PLATFORM_MAP[domain]

    host = domain
    # 임의의 하위 도메인(들)을 점 경계로 붙인다. 하위 도메인도 같은 플랫폼이어야 한다.
    sub_labels = draw(st.lists(_subdomain_labels, min_size=0, max_size=2))
    for label in reversed(sub_labels):
        host = f"{label}.{host}"
    # 선택적 `www.` 접두(제거되어야 함).
    if draw(st.booleans()):
        host = f"www.{host}"

    # 호스트 대소문자를 임의로 뒤섞어 소문자 정규화를 검증한다.
    host = _random_case(draw, host)

    scheme = draw(_schemes)
    path = draw(_paths)
    query = draw(_queries)
    fragment = draw(_fragments)
    link = f"{scheme}://{host}{path}{query}{fragment}"
    return link, expected


# 매핑 도메인도, 그 하위 도메인도 아닌 "근거 없는" 호스트 표본.
# 유사(lookalike) 도메인(예: notbunjang.co.kr)을 포함해 점 경계 오탐을 배제한다.
_UNMAPPED_HOSTS = (
    "example.com",
    "example.org",
    "shop.example.co.kr",
    "localhost",
    "some-random-store.net",
    "naver.com",
    "google.com",
    # 유사 도메인: 매핑 도메인을 부분 문자열로 포함하지만 점 경계가 아니므로 미적중.
    "notbunjang.co.kr",
    "bunjang.co.kr.evil.com",
    "mybunjang.co.kr",
    "musinsa.com.attacker.net",
    "fakemusinsa.com",
    "ebay.com.phish.io",
    "notebay.com",
    "kream.co.kr.evil.org",
    "grailed.community",
    "vestiairecollective.com.evil.net",
)


def _is_mapped(host: str) -> bool:
    """호스트가 매핑 도메인이거나 그 하위 도메인이면 True(기대값 파생용 헬퍼)."""
    host = host.lower()
    if host.startswith("www."):
        host = host[len("www.") :]
    for domain in _MAPPED_DOMAINS:
        if host == domain or host.endswith("." + domain):
            return True
    return False


@st.composite
def _unmapped_link(draw: st.DrawFn) -> str:
    """매핑되지 않은(하위 도메인도 아닌) 호스트로 링크를 생성한다.

    표본 호스트가 실수로 매핑 도메인과 겹치지 않음을 `_is_mapped`로 재확인한다.
    brand=None과 함께 쓰여 "근거 없음 → 기타·미확인" 경로를 검증한다.
    """
    host = draw(st.sampled_from(_UNMAPPED_HOSTS))
    # 방어적 전제: 표본이 정말로 미적중인지 보장한다(유사 도메인 오탐 방지).
    assert not _is_mapped(host)

    host = _random_case(draw, host)
    scheme = draw(_schemes)
    path = draw(_paths)
    query = draw(_queries)
    fragment = draw(_fragments)
    return f"{scheme}://{host}{path}{query}{fragment}"


# 결정성·region 불변식 검사용: 매핑/미적중을 모두 아우르는 임의 링크.
@st.composite
def _any_link(draw: st.DrawFn) -> str:
    """매핑 링크 또는 미적중 링크 중 하나를 생성한다(혼합 입력)."""
    if draw(st.booleans()):
        link, _ = draw(_mapped_link())
        return link
    return draw(_unmapped_link())


# --- 속성 테스트 -------------------------------------------------------------


# Feature: closeller-mvp, Property 16: 도메인 분류는 플랫폼·국내/해외 일관 결정, 미적중·근거없음→기타·미확인
@settings(max_examples=200)
@given(data=_mapped_link())
def test_mapped_domain_classifies_to_expected_platform_and_region(
    data: tuple[str, tuple[str, str]],
) -> None:
    """Platform_Map 적중: 매핑된 도메인(및 하위 도메인)은 정확히 정의된
    (플랫폼명, 국내/해외)로 분류된다(Req 10.1, 10.4).

    스킴·`www.` 접두·하위 도메인·경로/쿼리/프래그먼트·호스트 대소문자를 바꿔도
    결과는 PLATFORM_MAP에 정의된 값과 정확히 일치해야 한다. 기대값은
    PLATFORM_MAP에서 직접 파생하므로 단일 출처와 항상 동기화된다.
    """
    link, expected = data
    assert classify_platform(link) == expected
    # 국내/해외 구분은 매핑 적중 시 반드시 "국내" 또는 "해외"다(미확인 아님).
    assert expected[1] in (REGION_DOMESTIC, REGION_OVERSEAS)


# Feature: closeller-mvp, Property 16: 도메인 분류는 플랫폼·국내/해외 일관 결정, 미적중·근거없음→기타·미확인
@settings(max_examples=200)
@given(link=_unmapped_link())
def test_unmapped_without_evidence_classifies_to_other_unknown(link: str) -> None:
    """미적중 + 근거 없음(brand=None): 항상 ("기타", "미확인")으로 분류된다
    (Req 10.3, 10.5).

    유사(lookalike) 도메인(예: notbunjang.co.kr)도 점 경계 매칭이 아니므로
    매핑 플랫폼으로 오탐되지 않고 "기타"로 분류되어야 한다.
    """
    assert classify_platform(link, brand=None) == (PLATFORM_OTHER, REGION_UNKNOWN)


# Feature: closeller-mvp, Property 16: 도메인 분류는 플랫폼·국내/해외 일관 결정, 미적중·근거없음→기타·미확인
@settings(max_examples=200)
@given(link=_any_link())
def test_classification_is_deterministic(link: str) -> None:
    """결정성: 동일 링크를 두 번 분류하면 항상 동일한 결과를 반환한다
    (Property 16 결정적 함수).
    """
    assert classify_platform(link) == classify_platform(link)


# Feature: closeller-mvp, Property 16: 도메인 분류는 플랫폼·국내/해외 일관 결정, 미적중·근거없음→기타·미확인
@settings(max_examples=200)
@given(link=_any_link())
def test_region_is_always_a_valid_value(link: str) -> None:
    """region 불변식: 어떤 링크든 구분 값은 항상 {"국내","해외","미확인"} 중
    하나다(models.py NormalizedResult.region과 일치, Req 10.4, 10.5).
    """
    _, region = classify_platform(link)
    assert region in _VALID_REGIONS


# Feature: closeller-mvp, Property 16: 도메인 분류는 플랫폼·국내/해외 일관 결정, 미적중·근거없음→기타·미확인
@settings(max_examples=200)
@given(link=_any_link())
def test_classification_agrees_with_platform_map_lookup(link: str) -> None:
    """파이프라인 의도와의 결속: 분류 결과는 Platform_Map 조회와 정확히 일치한다.

    링크의 호스트를 소문자화·`www.` 제거 후 점 경계 접미사 매칭으로 조회한 기대값
    (PLATFORM_MAP에서 직접 파생)과, classify_platform(brand=None)의 결과가 같아야
    한다. 적중이면 정의된 (플랫폼, 구분), 미적중이면 ("기타", "미확인")이다.
    """
    host = urlsplit(link).hostname or ""
    host = host.lower()
    if host.startswith("www."):
        host = host[len("www.") :]

    expected = (PLATFORM_OTHER, REGION_UNKNOWN)
    for domain, info in PLATFORM_MAP.items():
        if host == domain or host.endswith("." + domain):
            expected = info
            break

    assert classify_platform(link, brand=None) == expected
