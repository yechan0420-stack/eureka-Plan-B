/**
 * resultsHandoff — VISUAL SEARCH → RESULTS 화면으로 검색 결과를 넘겨주는
 * **타입드 핸드오프 계약** (task 21.2 → task 22.x).
 *
 * [핸드오프 메커니즘 결정]
 * 전역 스토어·컨텍스트를 새로 들이지 않고, react-router 의 네비게이션 상태
 * (`navigate('/results', { state })`)로 넘긴다. 이유:
 *   - 검색 결과는 "한 번의 검색"에 종속된 휘발성 데이터이고, 새로고침 시
 *     되살아날 필요가 없다(URL 공유 대상이 아님). 따라서 라우터 state 가 가장
 *     단순하고 결합도가 낮은 선택이다.
 *   - 결과를 추가 전역 상태로 만들면 Search/Results 양쪽에 수명 관리 부담이
 *     생긴다. 라우터 state 는 전환과 함께 전달되고 전환이 끝나면 사라진다.
 *
 * RESULTS(Results.tsx, task 22.x)는 `useLocation().state` 를 이 타입으로 읽어
 * 그리드·정렬·필터·배지(22.1/22.2/22.4/22.8)와 오류 안내(22.10)를 렌더한다.
 * Search.tsx 는 성공 시 SearchResponse 의 네 필드(source/cached/currencyMixed/
 * results)를 그대로, 실패 시 errorCode 를 담아 넘긴다.
 *
 * state 는 신뢰할 수 없는 입력처럼 다룬다(직접 입력된 URL·뒤로가기 등으로 state
 * 가 없을 수 있다). 따라서 Results 는 `isResultsHandoff` 로 방어적으로 좁힌 뒤
 * 사용해야 하며, state 가 없으면 빈 상태를 보여준다.
 */

import type {
  NormalizedResult,
  ResultSource,
} from './apiTypes'

/**
 * 검색 성공 시 RESULTS 로 넘기는 결과 묶음. SearchResponse 의 네 필드를 그대로
 * 담아(task 22.x 가 가공 없이 렌더할 수 있도록) 전달한다.
 */
export interface ResultsHandoffSuccess {
  readonly kind: 'success'
  /** 결과 출처(SERP/MOCK). 22.2 TestDataBadge 가 MOCK 배지·구매 비활성에 쓴다. */
  readonly source: ResultSource
  /** 캐시 적중 여부(표시·디버깅용). */
  readonly cached: boolean
  /** 통화 혼재 여부. 22.4 SortControls 상단 안내 문구에 쓴다. */
  readonly currencyMixed: boolean
  /** 정규화된 상품 결과 목록. 22.1 ResultGrid 가 카드로 렌더한다. */
  readonly results: readonly NormalizedResult[]
}

/**
 * 검색 실패 시 RESULTS 로 넘기는 오류 묶음. 안정적 errorCode 를 보존해 22.10
 * ErrorNotice 가 한국어 메시지로 매핑한다(Req 17.x). 여기서 문구를 만들지 않고
 * 코드만 넘긴다.
 */
export interface ResultsHandoffError {
  readonly kind: 'error'
  /** 백엔드 오류 코드(없으면 'INTERNAL_ERROR'). ErrorNotice 매핑 키. */
  readonly errorCode: string
}

/** RESULTS 화면이 라우터 state 로 받는 핸드오프 유니온. */
export type ResultsHandoff = ResultsHandoffSuccess | ResultsHandoffError

/**
 * 임의의 라우터 state 가 유효한 핸드오프인지 방어적으로 좁힌다. Results(22.x)는
 * 직접 URL 접근·뒤로가기 등으로 state 가 없거나 형태가 다를 수 있으므로, 이
 * 가드를 통과한 값만 사용한다.
 */
export function isResultsHandoff(state: unknown): state is ResultsHandoff {
  if (typeof state !== 'object' || state === null) return false
  const kind = (state as { kind?: unknown }).kind
  if (kind === 'success') {
    const s = state as Partial<ResultsHandoffSuccess>
    return (
      (s.source === 'SERP' || s.source === 'MOCK') &&
      typeof s.cached === 'boolean' &&
      typeof s.currencyMixed === 'boolean' &&
      Array.isArray(s.results)
    )
  }
  if (kind === 'error') {
    return typeof (state as { errorCode?: unknown }).errorCode === 'string'
  }
  return false
}
