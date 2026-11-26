/**
 * sourceGating — source(결과 출처)에 따른 UI 게이팅 순수 로직 (Req 19.3, 19.4).
 *
 * MOCK(고정 테스트 데이터) 결과와 SERP(실제 검색) 결과를 화면에서 다르게 다룬다:
 *   - source="MOCK": "TEST DATA" 배지를 표시(Req 19.3)하고 구매 버튼을
 *     비활성화한다(Req 19.4).
 *   - source="SERP": 배지 없음 + 구매 버튼 활성화.
 *
 * 이 모듈은 React 를 의존하지 않는 순수 함수만 노출한다. 그래야 렌더를 거치지
 * 않고도 게이팅 규칙을 직접 테스트할 수 있다(task 22.3 Property 25 가 이 함수들을
 * 바로 검증한다). 컴포넌트(TestDataBadge/PurchaseButton)는 이 규칙을 그대로
 * 따른다.
 */
import type { ResultSource } from './apiTypes'

/** 결과가 Mock(테스트) 데이터인지 여부. MOCK 이면 "TEST DATA" 배지를 표시한다. */
export function isTestData(source: ResultSource): boolean {
  return source === 'MOCK'
}

/**
 * 구매 버튼 활성화 여부. MOCK(테스트 데이터)은 실제 구매가 불가하므로 비활성,
 * SERP(실제 결과)만 활성화한다(Req 19.4).
 */
export function isPurchaseEnabled(source: ResultSource): boolean {
  return source === 'SERP'
}
