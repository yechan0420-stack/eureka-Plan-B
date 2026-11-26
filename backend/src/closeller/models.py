"""CLOSELLER 백엔드 데이터 모델.

순수 데이터 구조만 정의한다(I/O·외부 의존성 없음).
`NormalizedResult`는 정규화 파이프라인(normalize.py)의 출력 단위이며,
SerpApi `visual_matches` 또는 Mock 데이터를 공식 필드만으로 변환한 결과다
(design.md Data Models, Req 9.1 참조).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class NormalizedResult:
    """정규화된 단일 상품 결과(불변).

    SerpApi 응답에 없는 값은 생성·추론하지 않는다(Req 9.9).
    """

    title: str                       # 상품명 (필수)
    link: str                        # 판매 페이지 URL (필수, http/https)
    image_url: str                   # 상품 이미지 URL (필수)
    price: str                       # 표시용 가격 문자열 또는 "미확인"
    currency: Optional[str]          # 통화 코드, 없으면 None
    price_sort_value: Optional[float]  # 정렬용 숫자값, 없으면 None
    platform: str                    # 판매 플랫폼명
    region: str                      # "국내" | "해외" | "미확인"
    match_type: str                  # "동일 상품 후보" | "유사 상품"
    match_grade: str                 # "높음" | "보통" | "낮음"
    source: str                      # "SERP" | "MOCK"
    brand: Optional[str] = None      # 브랜드, 기본 미포함(전용 필드 없음)
