/**
 * TestDataBadge — source="MOCK" 결과에만 표시하는 "TEST DATA" 배지 (Req 19.3).
 *
 * 이 배지는 결과가 실제 검색(SERP)이 아니라 고정 테스트 데이터(MOCK)임을
 * 사용자에게 분명히 알리기 위한 표식이다. 표시 문구는 design.md 가 지정한
 * 정확한 라벨 "TEST DATA" 를 그대로 쓴다.
 *
 * 렌더 여부(언제 보일지)는 이 컴포넌트가 결정하지 않는다. 호출 측(Results.tsx)이
 * `isTestData(source)` 규칙에 따라 MOCK 일 때만 렌더하며, 이 컴포넌트는 항상
 * 배지를 그린다. 이렇게 하면 "언제 보이는가"(게이팅)와 "어떻게 보이는가"(표시)가
 * 분리된다.
 *
 * 스타일: 포인트 컬러(accent) 바탕의 작은 볼드 모노톤 라벨 — 네온/그라데이션/과한
 * 그림자 금지(Req 18.3)를 따른다.
 */
function TestDataBadge() {
  return (
    <span
      data-testid="test-data-badge"
      className="inline-flex items-center bg-accent px-2 py-0.5 text-[0.6rem] font-bold uppercase tracking-tightest text-background"
    >
      TEST DATA
    </span>
  )
}

export default TestDataBadge
