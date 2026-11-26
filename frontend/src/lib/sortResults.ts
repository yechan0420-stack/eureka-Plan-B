/**
 * sortResults — RESULTS 화면의 정렬 순수 로직 (task 22.4, Req 15.1~15.7).
 *
 * 이 모듈은 React 를 의존하지 않는 순수 함수만 노출한다. 그래야 렌더를 거치지
 * 않고도 정렬 규칙을 직접 테스트할 수 있다(task 22.5 Property 20 가격, task 22.6
 * Property 21 일치도 가 이 함수를 그대로 검증한다). 컴포넌트(SortControls)와
 * 화면(Results)은 이 규칙을 그대로 따른다.
 *
 * [정렬 규칙]
 *   - 가격 낮은순/높은순(PRICE_ASC/PRICE_DESC): price_sort_value 가 null("미확인")
 *     인 결과는 **방향과 무관하게 항상 뒤**에 둔다(Req 15.3). 숫자값이 있는 결과만
 *     오름/내림차순으로 정렬한다(Req 15.1, 15.2). 동률과 "모두 미확인"은 입력
 *     순서를 유지한다(안정 정렬, Req 15.6).
 *   - 일치도 높은순(MATCH_GRADE_DESC): 높음 > 보통 > 낮음 순으로 배치하고(Req 15.5),
 *     같은 등급은 입력 순서를 유지한다(안정 정렬, Req 15.6).
 *   - 기본 정렬(DEFAULT_SORT)은 일치도 높은순이다(Req 15.5 / design.md).
 *
 * [통화 혼재(currencyMixed)]
 *   서로 다른 통화가 섞여 있어도 환율 변환을 하지 않는다. 가격 정렬은 통화를
 *   무시하고 순수하게 price_sort_value 숫자값만으로 정렬한다(Req 15.4, 15.7).
 *   혼재 안내 문구는 UI(SortControls/Results)가 currencyMixed 플래그로 표시하며,
 *   이 정렬 로직 자체는 통화를 변환·비교하지 않는다. 따라서 통화 혼재 여부는 이
 *   함수의 동작을 바꾸지 않는다(항상 숫자값 기준).
 *
 * [안정성 보장 방식 — decorate-sort-undecorate]
 *   최신 JS 엔진의 Array.prototype.sort 는 안정 정렬이지만, 속성 테스트가
 *   결정적으로 통과하도록 **원래 인덱스를 명시적 타이브레이커**로 사용한다.
 *   각 원소를 { result, index } 로 감싸(decorate) 정렬하고, 비교자가 0 을
 *   반환하는(동률) 경우 원래 index 오름차순으로 비교해 입력 순서를 보존한다.
 *   입력 배열은 변형하지 않고 항상 **새 배열**을 반환한다.
 */
import type { NormalizedResult, ResultMatchGrade } from './apiTypes'

/** 정렬 옵션 식별자. UI 라벨과 분리된 안정적 내부 값이다. */
export const SORT_OPTION = {
  /** 가격 낮은순(오름차순). 미확인은 항상 뒤. */
  PriceAsc: 'PRICE_ASC',
  /** 가격 높은순(내림차순). 미확인은 항상 뒤. */
  PriceDesc: 'PRICE_DESC',
  /** 일치도 높은순(높음>보통>낮음). */
  MatchGradeDesc: 'MATCH_GRADE_DESC',
} as const

/** 정렬 옵션 유니온 타입. */
export type SortOption = (typeof SORT_OPTION)[keyof typeof SORT_OPTION]

/** 기본 정렬: 일치도 높은순(Req 15.5 / design.md). */
export const DEFAULT_SORT: SortOption = SORT_OPTION.MatchGradeDesc

/** 정렬 옵션의 화면 표시 라벨(한국어, design.md "가격 낮은순/높은순/일치도 높은순"). */
export const SORT_OPTION_LABEL: Readonly<Record<SortOption, string>> = {
  [SORT_OPTION.PriceAsc]: '가격 낮은순',
  [SORT_OPTION.PriceDesc]: '가격 높은순',
  [SORT_OPTION.MatchGradeDesc]: '일치도 높은순',
}

/** UI 가 드롭다운·토글을 그릴 때 쓰는 정렬 옵션 나열 순서. */
export const SORT_OPTION_ORDER: readonly SortOption[] = [
  SORT_OPTION.MatchGradeDesc,
  SORT_OPTION.PriceAsc,
  SORT_OPTION.PriceDesc,
]

/**
 * 일치도 등급 → 랭크. 높을수록 앞(높은순). 높음(2) > 보통(1) > 낮음(0).
 * 숫자 점수를 결과에 노출하지 않고 정렬 내부에서만 순서 비교에 사용한다
 * (match_grade 는 3등급 문자열 그대로 유지).
 */
const MATCH_GRADE_RANK: Readonly<Record<ResultMatchGrade, number>> = {
  높음: 2,
  보통: 1,
  낮음: 0,
}

/** 임의의 state 가 유효한 SortOption 인지 좁힌다(라우터·저장값 방어용). */
export function isSortOption(value: unknown): value is SortOption {
  return (
    value === SORT_OPTION.PriceAsc ||
    value === SORT_OPTION.PriceDesc ||
    value === SORT_OPTION.MatchGradeDesc
  )
}

/**
 * 가격 비교자. price_sort_value 가 null("미확인")인 결과는 방향과 무관하게 항상
 * 뒤로 보낸다(Req 15.3). 둘 다 알려진 값이면 방향(dir: +1 오름 / -1 내림)에 따라
 * 숫자 비교한다. 동률·둘 다 미확인은 0(안정 타이브레이커가 입력 순서 보존).
 */
function comparePrice(
  a: NormalizedResult,
  b: NormalizedResult,
  dir: 1 | -1,
): number {
  const av = a.price_sort_value
  const bv = b.price_sort_value
  const aUnknown = av === null
  const bUnknown = bv === null

  // 미확인은 항상 뒤 — 오름/내림 모두 동일(Req 15.3).
  if (aUnknown && bUnknown) return 0
  if (aUnknown) return 1
  if (bUnknown) return -1

  // 둘 다 알려진 숫자값: 방향에 따라 비교(Req 15.1, 15.2).
  if (av < bv) return -1 * dir
  if (av > bv) return 1 * dir
  return 0
}

/**
 * 일치도 비교자. 높음>보통>낮음 순(내림, 랭크 큰 값이 앞). 같은 등급은 0
 * (안정 타이브레이커가 입력 순서 보존, Req 15.5, 15.6).
 */
function compareMatchGrade(a: NormalizedResult, b: NormalizedResult): number {
  return MATCH_GRADE_RANK[b.match_grade] - MATCH_GRADE_RANK[a.match_grade]
}

/** 선택한 정렬 옵션에 해당하는 결과 비교자를 돌려준다. */
function comparatorFor(
  option: SortOption,
): (a: NormalizedResult, b: NormalizedResult) => number {
  switch (option) {
    case SORT_OPTION.PriceAsc:
      return (a, b) => comparePrice(a, b, 1)
    case SORT_OPTION.PriceDesc:
      return (a, b) => comparePrice(a, b, -1)
    case SORT_OPTION.MatchGradeDesc:
      return compareMatchGrade
    default: {
      // 타입상 도달 불가. 방어적으로 입력 순서를 유지한다.
      const _exhaustive: never = option
      void _exhaustive
      return () => 0
    }
  }
}

/**
 * 결과 목록을 주어진 정렬 옵션으로 정렬한 **새 배열**을 반환한다. 입력 배열은
 * 변형하지 않으며(순수), 동률은 입력 순서를 보존하는 안정 정렬이다.
 *
 * 안정성은 decorate-sort-undecorate 로 명시적으로 보장한다: 각 원소에 원래
 * 인덱스를 붙이고, 비교자가 0(동률)을 반환하면 원래 인덱스 오름차순으로 결정해
 * 입력 순서를 유지한다.
 */
export function sortResults(
  results: readonly NormalizedResult[],
  option: SortOption,
): NormalizedResult[] {
  const compare = comparatorFor(option)
  return results
    .map((result, index) => ({ result, index }))
    .sort((a, b) => {
      const primary = compare(a.result, b.result)
      if (primary !== 0) return primary
      // 동률 → 원래 입력 순서 유지(안정 정렬, Req 15.6).
      return a.index - b.index
    })
    .map((decorated) => decorated.result)
}
