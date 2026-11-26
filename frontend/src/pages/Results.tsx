/**
 * RESULTS (`/results`) — 상품 카드 그리드·정렬·필터 화면 (Req 18.1).
 * ResultGrid/ProductCard/SortControls/FilterControls/ErrorNotice(task 22)는
 * 이후 작업에서 이 자리에 끼워 넣는다. 여기서는 그리드 뼈대만 둔다.
 */
function Results() {
  return (
    <section className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-4xl font-bold tracking-tightest md:text-6xl">
          Results
        </h1>
        <p className="max-w-xl text-sm text-text/60 md:text-base">
          검색 결과가 상품 카드 그리드로 표시됩니다.
        </p>
      </header>

      {/*
        플러그인 지점 (이후 작업):
        - task 22.1 ResultGrid / ProductCard
        - task 22.2 TestDataBadge / 구매 버튼 제어
        - task 22.4 SortControls · 22.8 FilterControls
        - task 22.10 ErrorNotice
      */}
      <div
        data-testid="results-grid"
        className="editorial-grid min-h-[16rem] items-center justify-center text-xs uppercase tracking-tightest text-text/40"
      >
        <div className="flex min-h-[8rem] items-center justify-center bg-background p-8">
          No Results Yet
        </div>
      </div>
    </section>
  )
}

export default Results
