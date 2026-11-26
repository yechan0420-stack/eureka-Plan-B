"""`platform_map.py` 단위 테스트 (예시 기반).

도메인 → (플랫폼명, 국내/해외) 분류에 대한 구체적인 예시·엣지 케이스를 검증한다.
속성 기반 테스트(Property 16)는 `test_platform_map_property.py`에 별도로 존재하며,
이 파일은 design.md Platform_Map에 정의된 7개 플랫폼 각각의 분류 예시와
정규화(www. 제거·소문자·하위 도메인) 규칙을 결정적으로 확인한다(Req 10.1, 10.6).
"""

import pytest

from closeller.platform_map import (
    PLATFORM_MAP,
    PLATFORM_OFFICIAL_CANDIDATE,
    PLATFORM_OTHER,
    REGION_DOMESTIC,
    REGION_OVERSEAS,
    REGION_UNKNOWN,
    classify_platform,
)


# --- 7개 플랫폼 각각의 도메인 분류 예시 (Req 10.1, 10.6) ---------------------
# design.md Platform_Map 표의 7개 항목을 실제 전체 URL(스킴·경로·쿼리 포함)로 확인한다.
@pytest.mark.parametrize(
    ("link", "expected"),
    [
        pytest.param(
            "https://fruitsfamily.com/product/12345?ref=share",
            ("후루츠패밀리", REGION_DOMESTIC),
            id="fruitsfamily-domestic",
        ),
        pytest.param(
            "https://bunjang.co.kr/products/987654321",
            ("번개장터", REGION_DOMESTIC),
            id="bunjang-domestic",
        ),
        pytest.param(
            "https://m.bunjang.co.kr/products/987654321?q=nike",
            ("번개장터", REGION_DOMESTIC),
            id="bunjang-mobile-subdomain",
        ),
        pytest.param(
            "https://musinsa.com/app/goods/1234567",
            ("무신사", REGION_DOMESTIC),
            id="musinsa-domestic",
        ),
        pytest.param(
            "https://kream.co.kr/products/4567?tab=sell",
            ("KREAM", REGION_DOMESTIC),
            id="kream-domestic",
        ),
        pytest.param(
            "https://ebay.com/itm/123456789012?hash=item1a",
            ("eBay", REGION_OVERSEAS),
            id="ebay-overseas",
        ),
        pytest.param(
            "https://grailed.com/listings/123456-nike-dunk",
            ("Grailed", REGION_OVERSEAS),
            id="grailed-overseas",
        ),
        pytest.param(
            "https://vestiairecollective.com/men-clothing/jackets/1234.shtml",
            ("Vestiaire Collective", REGION_OVERSEAS),
            id="vestiaire-overseas",
        ),
    ],
)
def test_defined_platforms_classified(link: str, expected: tuple[str, str]) -> None:
    """정의된 7개 플랫폼 도메인은 Platform_Map대로 (플랫폼명, 국내/해외)로 분류된다."""
    assert classify_platform(link) == expected


def test_all_seven_platform_map_entries_covered() -> None:
    """Platform_Map에 정확히 7개 항목이 등록돼 있고 구분 문자열이 국내/해외뿐이다."""
    assert len(PLATFORM_MAP) == 7
    regions = {region for _, region in PLATFORM_MAP.values()}
    assert regions == {REGION_DOMESTIC, REGION_OVERSEAS}


# --- 정규화: 선행 www. 제거 (Req 10.1) --------------------------------------
@pytest.mark.parametrize(
    ("link", "expected"),
    [
        pytest.param(
            "https://www.musinsa.com/app/goods/7654321",
            ("무신사", REGION_DOMESTIC),
            id="www-musinsa",
        ),
        pytest.param(
            "https://www.ebay.com/itm/555555555555",
            ("eBay", REGION_OVERSEAS),
            id="www-ebay",
        ),
    ],
)
def test_www_prefix_stripped(link: str, expected: tuple[str, str]) -> None:
    """선행 `www.`는 제거 후 대표 도메인으로 조회되어 같은 플랫폼으로 분류된다."""
    assert classify_platform(link) == expected


# --- 정규화: 하위 도메인은 같은 플랫폼 (Req 10.1) ----------------------------
@pytest.mark.parametrize(
    ("link", "expected"),
    [
        pytest.param(
            "https://shop.musinsa.com/app/goods/1111111",
            ("무신사", REGION_DOMESTIC),
            id="subdomain-shop-musinsa",
        ),
        pytest.param(
            "https://m.bunjang.co.kr/products/222",
            ("번개장터", REGION_DOMESTIC),
            id="subdomain-m-bunjang",
        ),
    ],
)
def test_subdomain_classified_same_platform(
    link: str, expected: tuple[str, str]
) -> None:
    """매핑된 도메인의 하위 도메인도 접미사 매칭으로 같은 플랫폼으로 분류된다."""
    assert classify_platform(link) == expected


# --- 정규화: 호스트 대문자 입력도 소문자화되어 적중 (Req 10.1) ---------------
def test_uppercase_host_lowercased_before_lookup() -> None:
    """호스트에 대문자가 섞여 있어도 소문자화 후 Platform_Map에 적중한다."""
    assert classify_platform("https://KREAM.CO.KR/products/9") == (
        "KREAM",
        REGION_DOMESTIC,
    )


# --- 미적중: 매핑 없음 + 브랜드 없음 → ("기타", "미확인") (Req 10.3, 10.5) ---
def test_unmapped_domain_without_brand_is_other() -> None:
    """매핑되지 않은 도메인은 브랜드 힌트가 없으면 ("기타", "미확인")이다."""
    assert classify_platform("https://some-random-shop.example/item/1") == (
        PLATFORM_OTHER,
        REGION_UNKNOWN,
    )


# --- 유사 도메인 오탐 방지: notbunjang.co.kr 은 매칭되면 안 된다 (Req 10.3) --
@pytest.mark.parametrize(
    "link",
    [
        pytest.param("https://notbunjang.co.kr/x", id="lookalike-notbunjang"),
        pytest.param("https://fakemusinsa.com/app/goods/1", id="lookalike-fakemusinsa"),
        pytest.param("https://ebay.com.evil.example/itm/1", id="lookalike-ebay-suffix"),
    ],
)
def test_lookalike_domains_do_not_match(link: str) -> None:
    """점 경계 밖에서 도메인 문자열을 포함하는 유사 도메인은 오탐하지 않는다."""
    assert classify_platform(link) == (PLATFORM_OTHER, REGION_UNKNOWN)


# --- 공식 홈페이지 후보: 미적중 + 브랜드 힌트 일치 (Req 10.2, 10.5) ----------
def test_official_homepage_candidate_with_matching_brand_hint() -> None:
    """미적중 도메인이라도 브랜드 힌트가 호스트 라벨과 일치하면 공식 홈페이지 후보다."""
    assert classify_platform(
        "https://acnestudios.com/collection/jackets", brand="Acne Studios"
    ) == (PLATFORM_OFFICIAL_CANDIDATE, REGION_UNKNOWN)


def test_official_homepage_candidate_requires_brand_match() -> None:
    """브랜드 힌트가 호스트 라벨과 무관하면 공식 홈페이지 후보가 아니라 기타다."""
    assert classify_platform(
        "https://acnestudios.com/collection/jackets", brand="Nike"
    ) == (PLATFORM_OTHER, REGION_UNKNOWN)
