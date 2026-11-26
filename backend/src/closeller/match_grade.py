"""Match_Grade 산정(순수 모듈).

정규화 파이프라인(normalize.py)이 사용하는 "(결과 유형, 순위) → 일치도 등급" 산정을
담당한다. I/O·외부 의존성(boto3·네트워크·파일)이 없는 순수 함수만 포함하며,
표준 라이브러리만 사용한다(design.md 모듈 분리표 참조).

Match_Grade는 결과 유형(matchType)과 순위(position) 기반 **휴리스틱**이다. 숫자
점수나 확률을 계산하지 않고, 아래 산정표에 따라 "높음" | "보통" | "낮음" 3등급 중
하나만 산정한다(Req 11.5, 11.6). 이 휴리스틱 성격은 ABOUT 화면에도 함께 명시한다
(Req 11.7).

Match_Grade 산정표(design.md 및 Req 11.3, 11.4, 11.5):

| matchType     | position 범위     | Match_Grade |
|---------------|-------------------|-------------|
| 동일 상품 후보 | 1~3               | 높음        |
| 동일 상품 후보 | 4~10              | 보통        |
| 동일 상품 후보 | ≥11               | 낮음        |
| 유사 상품      | 1~3               | 보통        |
| 유사 상품      | ≥4                | 낮음        |
| (모든 유형)    | 순위 없음/무효     | 낮음        |

순위 "무효"는 None, 정수가 아닌 값(bool 포함), 1 미만(≤0)인 경우를 말하며 모두
"낮음"으로 떨어진다(Req 11.5). 미지의 matchType도 안전하게 "낮음"으로 처리한다.

등급 문자열은 models.py `NormalizedResult.match_grade`와 일치하도록 정확히
"높음" | "보통" | "낮음"만, 유형 문자열은 `NormalizedResult.match_type`와 일치하도록
"동일 상품 후보" | "유사 상품"만 사용한다.

동일 입력에 대해 항상 동일한 결과를 반환하는 결정적 함수다(Property 17).
"""

from typing import Optional

__all__ = [
    "MATCH_TYPE_IDENTICAL",
    "MATCH_TYPE_SIMILAR",
    "GRADE_HIGH",
    "GRADE_MEDIUM",
    "GRADE_LOW",
    "compute_match_grade",
]

# 결과 유형 문자열. models.py NormalizedResult.match_type과 반드시 일치시킨다.
MATCH_TYPE_IDENTICAL: str = "동일 상품 후보"
MATCH_TYPE_SIMILAR: str = "유사 상품"

# 일치도 등급 문자열. models.py NormalizedResult.match_grade와 반드시 일치시킨다.
# 숫자 점수는 쓰지 않고 아래 3등급만 산정한다(Req 11.5, 11.6).
GRADE_HIGH: str = "높음"
GRADE_MEDIUM: str = "보통"
GRADE_LOW: str = "낮음"


def _normalize_position(position: object) -> Optional[int]:
    """순위 값을 유효한 1 이상의 정수로 정규화한다(내부 헬퍼).

    유효하지 않으면(None·정수 아님·bool·1 미만) None을 반환한다. bool은 int의
    하위 타입이라 True/False가 1/0으로 새어들 수 있으므로 명시적으로 배제한다.
    이렇게 걸러낸 None은 호출부에서 "낮음"으로 처리된다(Req 11.5).
    """
    if isinstance(position, bool):
        return None
    if not isinstance(position, int):
        return None
    if position < 1:
        return None
    return position


def compute_match_grade(match_type: str, position: object) -> str:
    """(결과 유형, 순위)로 Match_Grade를 산정한다(휴리스틱).

    주의: 이것은 숫자 점수가 아니라 결과 유형과 순위에 기반한 휴리스틱 등급이다
    (Req 11.7). 반환값은 항상 "높음" | "보통" | "낮음" 중 하나다(Req 11.6).

    매개변수:
      match_type: "동일 상품 후보" | "유사 상품". 그 외 값은 "낮음"으로 처리한다.
      position: 1 기반 결과 순위. None·정수 아님·bool·1 미만은 무효로 보고 "낮음".

    산정 규칙(Req 11.3, 11.4, 11.5):
      - 순위 없음/무효: "낮음".
      - 동일 상품 후보: 1~3 → "높음", 4~10 → "보통", ≥11 → "낮음".
      - 유사 상품: 1~3 → "보통", ≥4 → "낮음".

    결정적 함수이므로 동일 입력은 항상 동일한 결과를 반환한다(Property 17).
    """
    rank = _normalize_position(position)
    if rank is None:
        return GRADE_LOW

    if match_type == MATCH_TYPE_IDENTICAL:
        if rank <= 3:
            return GRADE_HIGH
        if rank <= 10:
            return GRADE_MEDIUM
        return GRADE_LOW

    if match_type == MATCH_TYPE_SIMILAR:
        if rank <= 3:
            return GRADE_MEDIUM
        return GRADE_LOW

    # 알 수 없는 유형은 보수적으로 "낮음"으로 처리한다.
    return GRADE_LOW
