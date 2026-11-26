/**
 * filterResults — RESULTS 화면의 필터 순수 로직 (task 22.8, Req 16.1~16.3).
 *
 * 이 모듈은 React 를 의존하지 않는 순수 함수만 노출한다. 그래야 렌더를 거치지
 * 않고도 필터 규칙을 직접 테스트할 수 있다(task 22.9 Property 23 "필터 결과는
 * 정확한 부분집합" 이 이 함수를 그대로 검증한다). 컴포넌트(FilterControls)와
 * 화면(Results)은 이 규칙을 그대로 따른다.
 *
 * [필터 패싯(facet)] — design.md "FilterControls: 국내·해외 / 동일·유사 / 플랫폼"
 *   - region    : 국내 / 해외 / 미확인   (NormalizedResult.region, Req 16.1)
 *   - matchType : 동일 상품 후보 / 유사 상품 (NormalizedResult.match_type, Req 16.2)
 *   - platform  : 결과에 존재하는 플랫폼 문자열 (NormalizedResult.platform, Req 16.3)
 *
 * [필터 의미(semantics) — 명확히 결정·문서화]
 *   - **패싯 내부(within a facet)**: 여러 값을 선택하면 OR 로 묶는다. 예) region
 *     에 '국내'와 '해외'를 함께 고르면 둘 중 하나라도 맞으면 통과한다.
 *   - **패싯 간(across facets)**: AND 로 묶는다. 예) region='국내' 이면서
 *     matchType='동일 상품 후보' 인 결과만 통과한다.
 *   - **빈 선택(empty selection)**: 해당 패싯은 필터하지 않는다(= 전부 통과).
 *     세 패싯 모두 비면 입력 전체가 그대로 남는다.
 *   - **부분집합 보장**: 결과는 입력의 **정확한 부분집합**이다. 원소를 추가하거나
 *     변형하지 않고 "제거"만 하며, 남은 원소의 **상대 순서(입력 순서)를 보존**한다
 *     (Req 16.1~16.3 / Property 23). 항상 **새 배열**을 반환하고 입력은 변형하지
 *     않는다.
 *
 * [region '미확인' 처리 — 설계 결정]
 *   요구사항 16.1 은 "국내 또는 해외" 를 예로 들지만, 데이터 모델의 region 은
 *   '국내' | '해외' | '미확인' 세 값을 가진다(platform_map.py, design.md 데이터
 *   모델). 데이터 정직성 규칙상 '미확인' 은 숨기거나 임의로 국내/해외로 끼워
 *   넣지 않는다. 따라서 '미확인' 을 **독립된 선택 옵션**으로 제공한다. region
 *   선택이 비어 있으면(기본) 미확인을 포함한 모든 결과가 보이고, 사용자가
 *   '국내'/'해외' 만 고르면 자연히 미확인은 걸러진다(필요하면 '미확인'도 함께
 *   선택 가능).
 */
import type {
  NormalizedResult,
  ResultMatchType,
  ResultRegion,
} from './apiTypes'

/**
 * 필터 상태. 각 패싯은 "선택된 값의 집합"이다. 빈 배열 = 그 패싯은 필터하지
 * 않음(전부 통과). 불변(readonly) 배열로 받아 순수성을 지킨다.
 */
export interface FilterState {
  /** 선택된 지역 구분(국내/해외/미확인). 빈 배열이면 지역 필터 없음. */
  readonly regions: readonly ResultRegion[]
  /** 선택된 유형(동일 상품 후보/유사 상품). 빈 배열이면 유형 필터 없음. */
  readonly matchTypes: readonly ResultMatchType[]
  /** 선택된 플랫폼명. 빈 배열이면 플랫폼 필터 없음. */
  readonly platforms: readonly string[]
}

/** 아무 것도 선택하지 않은 기본 필터 상태(= 전체 표시). */
export const EMPTY_FILTER_STATE: FilterState = {
  regions: [],
  matchTypes: [],
  platforms: [],
}

/**
 * 선택 가능한 지역 옵션(고정). region 은 데이터 모델상 이 세 값만 가진다.
 * UI(FilterControls)가 지역 토글을 그릴 때 이 나열 순서를 그대로 쓴다.
 */
export const REGION_OPTIONS: readonly ResultRegion[] = ['국내', '해외', '미확인']

/**
 * 선택 가능한 유형 옵션(고정). match_type 은 이 두 값만 가진다.
 * UI(FilterControls)가 유형 토글을 그릴 때 이 나열 순서를 그대로 쓴다.
 */
export const MATCH_TYPE_OPTIONS: readonly ResultMatchType[] = [
  '동일 상품 후보',
  '유사 상품',
]

/**
 * 현재 결과 목록에 **실제로 존재하는** 플랫폼 옵션을 유도한다. 플랫폼은 고정
 * 목록이 아니라 결과에 나타난 값에서 파생되므로(기타/공식 홈페이지 후보 등
 * 포함), 결과가 바뀌면 옵션도 바뀐다.
 *
 * - 입력 순서대로 **처음 등장한 순서**를 보존하며 중복을 제거한다(안정적·결정적).
 * - 호출부(Results)는 필터링 이전의 **전체 결과**에서 옵션을 유도해야 한다.
 *   그래야 필터를 좁혀도 옵션이 사라지지 않는다.
 *
 * 입력은 변형하지 않고 항상 새 배열을 반환한다.
 */
export function derivePlatformOptions(
  results: readonly NormalizedResult[],
): string[] {
  const seen = new Set<string>()
  const options: string[] = []
  for (const result of results) {
    if (!seen.has(result.platform)) {
      seen.add(result.platform)
      options.push(result.platform)
    }
  }
  return options
}

/**
 * 단일 패싯 통과 여부. 선택이 비어 있으면(필터 없음) 항상 통과(true), 아니면
 * 결과 값이 선택 집합에 포함될 때만 통과(within-facet OR).
 */
function passesFacet<T>(value: T, selected: readonly T[]): boolean {
  if (selected.length === 0) return true
  return selected.includes(value)
}

/**
 * 결과 목록을 필터 상태로 거른 **새 배열**을 반환한다. 입력의 정확한 부분집합이며
 * (원소 추가·변형 없음, 제거만), 남은 원소의 입력 순서를 보존한다(Property 23).
 *
 * 패싯 간 AND, 패싯 내 OR, 빈 선택 = 그 패싯 무필터(위 모듈 주석 참조).
 */
export function filterResults(
  results: readonly NormalizedResult[],
  filterState: FilterState,
): NormalizedResult[] {
  return results.filter(
    (result) =>
      passesFacet(result.region, filterState.regions) &&
      passesFacet(result.match_type, filterState.matchTypes) &&
      passesFacet(result.platform, filterState.platforms),
  )
}

/** 필터 상태에 활성화된(선택된) 패싯이 하나라도 있는지. UI 안내·초기화용. */
export function hasActiveFilter(filterState: FilterState): boolean {
  return (
    filterState.regions.length > 0 ||
    filterState.matchTypes.length > 0 ||
    filterState.platforms.length > 0
  )
}

/**
 * 토글 헬퍼. 주어진 값이 선택 배열에 있으면 제거, 없으면 추가한 **새 배열**을
 * 반환한다(순수). FilterControls 가 칩/체크박스 토글에 쓴다.
 */
export function toggleValue<T>(selected: readonly T[], value: T): T[] {
  return selected.includes(value)
    ? selected.filter((v) => v !== value)
    : [...selected, value]
}
