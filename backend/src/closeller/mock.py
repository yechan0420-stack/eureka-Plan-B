"""고정 MOCK 데이터 제공(순수 모듈).

테스트 모드(`USE_MOCK_SEARCH=true`)에서 Search_Lambda가 SerpApi_Service를 호출하지
않고 반환할 고정 테스트 데이터를 제공한다(Req 19.1). I/O·외부 의존성(boto3·네트워크·
파일)이 없는 순수 모듈로, 다른 순수 모듈(models·platform_map·match_grade 등)과 동일한
설계를 따른다(design.md 모듈 분리표의 `mock.py` 행: "고정 MOCK 데이터(example.com)
생성", Req 19.1·19.2·19.5).

규칙:
  - 모든 항목은 `source="MOCK"`을 포함한다(Req 19.2).
  - 모든 `link`·`image_url`은 실제 상점처럼 보이는 가짜 링크를 쓰지 않고 안전한 예시
    도메인(`example.com`)만 사용한다(Req 19.5). 후루츠패밀리·번개장터·무신사·KREAM·
    eBay·Grailed·Vestiaire Collective 등 실제 상점과 유사한 도메인은 쓰지 않는다.
  - 데이터는 고정(결정적)이다. `NormalizedResult`가 frozen 불변 dataclass이므로
    모듈 수준 고정 인스턴스를 그대로 돌려줘도 안전하다.

다운스트림(정렬·필터)이 Mock 모드에서도 시연될 수 있도록 다음을 의도적으로 섞는다.
  - 가격이 있는 항목과, 가격 "미확인"·`price_sort_value=None`인 항목(가격 없음 경로).
  - 통화 혼재(KRW·USD·EUR)로 통화 혼재 안내 경로.
  - `match_type`("동일 상품 후보"/"유사 상품")·`match_grade`("높음"/"보통"/"낮음")·
    `region`("국내"/"해외"/"미확인")을 항목마다 달리하여 정렬·필터 시연이 가능하도록 한다.

주의: 여기 `platform` 값은 어디까지나 테스트용 표시 문자열이며, 실제 상점 도메인과
연결되지 않는다. 모든 링크는 `example.com`을 가리킨다(Req 19.5).
"""

from .match_grade import (
    GRADE_HIGH,
    GRADE_LOW,
    GRADE_MEDIUM,
    MATCH_TYPE_IDENTICAL,
    MATCH_TYPE_SIMILAR,
)
from .models import NormalizedResult
from .platform_map import REGION_DOMESTIC, REGION_OVERSEAS, REGION_UNKNOWN

__all__ = ["MOCK_SOURCE", "MOCK_RESULTS", "get_mock_results"]

# source 값. models.py NormalizedResult.source의 "MOCK"과 반드시 일치시킨다(Req 19.2).
MOCK_SOURCE: str = "MOCK"

# 고정 MOCK 데이터셋. 모든 링크·이미지는 example.com 예시 도메인만 사용한다(Req 19.5).
# NormalizedResult는 frozen 불변이라 모듈 수준 고정 인스턴스를 재사용해도 안전하다.
MOCK_RESULTS: tuple[NormalizedResult, ...] = (
    # 가격 있음(KRW) · 국내 · 동일 상품 후보 · 높음
    NormalizedResult(
        title="테스트 니트 가디건 (MOCK)",
        link="https://example.com/products/mock-1",
        image_url="https://example.com/images/mock-1.jpg",
        price="89,000원",
        currency="KRW",
        price_sort_value=89000.0,
        platform="테스트 마켓 A",
        region=REGION_DOMESTIC,
        match_type=MATCH_TYPE_IDENTICAL,
        match_grade=GRADE_HIGH,
        source=MOCK_SOURCE,
    ),
    # 가격 있음(USD) · 해외 · 유사 상품 · 보통
    NormalizedResult(
        title="테스트 울 코트 (MOCK)",
        link="https://example.com/products/mock-2",
        image_url="https://example.com/images/mock-2.jpg",
        price="$120.00",
        currency="USD",
        price_sort_value=120.0,
        platform="테스트 마켓 B",
        region=REGION_OVERSEAS,
        match_type=MATCH_TYPE_SIMILAR,
        match_grade=GRADE_MEDIUM,
        source=MOCK_SOURCE,
    ),
    # 가격 미확인 · 미확인 지역 · 유사 상품 · 낮음 (가격 없음 경로 시연)
    NormalizedResult(
        title="테스트 데님 자켓 (MOCK)",
        link="https://example.com/products/mock-3",
        image_url="https://example.com/images/mock-3.jpg",
        price="미확인",
        currency=None,
        price_sort_value=None,
        platform="테스트 마켓 C",
        region=REGION_UNKNOWN,
        match_type=MATCH_TYPE_SIMILAR,
        match_grade=GRADE_LOW,
        source=MOCK_SOURCE,
    ),
    # 가격 있음(EUR, 통화 혼재 시연) · 해외 · 동일 상품 후보 · 보통 · 브랜드 포함
    NormalizedResult(
        title="테스트 레더 스니커즈 (MOCK)",
        link="https://example.com/products/mock-4",
        image_url="https://example.com/images/mock-4.jpg",
        price="€95.00",
        currency="EUR",
        price_sort_value=95.0,
        platform="테스트 마켓 D",
        region=REGION_OVERSEAS,
        match_type=MATCH_TYPE_IDENTICAL,
        match_grade=GRADE_MEDIUM,
        source=MOCK_SOURCE,
        brand="TEST BRAND",
    ),
    # 가격 있음(KRW) · 국내 · 동일 상품 후보 · 낮음
    NormalizedResult(
        title="테스트 크로스백 (MOCK)",
        link="https://example.com/products/mock-5",
        image_url="https://example.com/images/mock-5.jpg",
        price="45,000원",
        currency="KRW",
        price_sort_value=45000.0,
        platform="테스트 마켓 E",
        region=REGION_DOMESTIC,
        match_type=MATCH_TYPE_IDENTICAL,
        match_grade=GRADE_LOW,
        source=MOCK_SOURCE,
    ),
)


def get_mock_results() -> list[NormalizedResult]:
    """고정 MOCK 데이터셋을 리스트로 반환한다(Req 19.1).

    모든 항목은 `source="MOCK"`이며(Req 19.2), 모든 링크·이미지는 안전한 예시
    도메인(example.com)만 사용한다(Req 19.5). 외부 호출·I/O 없이 고정 데이터만
    돌려주는 결정적 함수다.

    `NormalizedResult`는 frozen 불변이라 고정 인스턴스를 공유해도 안전하지만,
    호출부가 리스트를 자유롭게 재정렬·필터링할 수 있도록 매 호출마다 새 리스트를
    만들어 반환한다(원본 `MOCK_RESULTS` 튜플은 변형되지 않는다).
    """
    return list(MOCK_RESULTS)
