import { useMemo, useState } from 'react'
import { useLocation } from 'react-router-dom'
import ResultGrid from '../components/ResultGrid'
import SortControls from '../components/SortControls'
import FilterControls from '../components/FilterControls'
import TestDataBadge from '../components/TestDataBadge'
import PurchaseButton from '../components/PurchaseButton'
import ErrorNotice from '../components/ErrorNotice'
import { isTestData } from '../lib/sourceGating'
import { isResultsHandoff } from '../lib/resultsHandoff'
import { DEFAULT_SORT, sortResults, type SortOption } from '../lib/sortResults'
import {
  EMPTY_FILTER_STATE,
  derivePlatformOptions,
  filterResults,
  type FilterState,
} from '../lib/filterResults'

/**
 * RESULTS (`/results`) — 상품 카드 그리드·정렬·필터 화면 (Req 18.1, 14.1~14.4).
 *
 * VISUAL SEARCH → RESULTS 핸드오프는 react-router 의 네비게이션 state 로 전달되며
 * (resultsHandoff.ts 계약), 직접 URL 접근·뒤로가기 등으로 state 가 없거나 형태가
 * 다를 수 있다. 따라서 `isResultsHandoff` 로 방어적으로 좁힌 뒤에만 사용하고,
 * 유효하지 않으면 기존 빈 상태를 보여준다.
 *
 * - 성공 핸드오프(kind: 'success'): ResultGrid 로 결과를 카드 그리드로 렌더(22.1).
 * - state 없음/무효(직접 접근): 빈 상태("No Results Yet").
 *
 * 플러그인 지점 — 22.1 이 남긴 심에 끼워 넣는다:
 *   - task 22.2 (완료)  TestDataBadge / 구매 버튼 제어
 *       → ResultGrid 의 `renderBadge` / `renderPurchase` 프롭으로 주입한다.
 *         source=MOCK 이면 "TEST DATA" 배지 + 비활성 구매 버튼, SERP 이면 배지
 *         없음 + 활성 구매 버튼(Req 19.3, 19.4).
 *   - task 22.4 (완료)  SortControls (정렬)
 *       → 선택된 정렬 옵션을 로컬 상태로 보관(기본값 DEFAULT_SORT=일치도 높은순)
 *         하고, sortResults(success.results, option) 로 정렬한 뒤 ResultGrid 에
 *         넘긴다. 통화 혼재 안내는 SortControls 가 currencyMixed 로 표시한다
 *         (Req 15.1~15.7).
 *   - task 22.8 (완료)  FilterControls (필터)
 *       → 결과 → filterResults(…) → sortResults(…) → ResultGrid 순으로 레이어를
 *         쌓는다(합성). baseResults 가 이제 filterResults(success.results, filter)
 *         이고, 정렬은 그 위에 그대로 얹힌다. 플랫폼 옵션은 필터링 **이전**의
 *         전체 결과(success.results)에서 유도해, 필터를 좁혀도 옵션이 사라지지
 *         않게 한다(Req 16.1~16.3).
 *   - task 22.10 (완료)  ErrorNotice (kind: 'error' 핸드오프의 errorCode 매핑)
 *       → 핸드오프가 오류이면 그리드/빈 상태 대신 <ErrorNotice errorCode={…}/> 로
 *         코드별 한국어 메시지를 렌더한다(Req 17.x). 성공 경로는 그대로 둔다.
 */
function Results() {
  const location = useLocation()
  const handoff = isResultsHandoff(location.state) ? location.state : null
  const success = handoff?.kind === 'success' ? handoff : null
  // 22.10: 오류 핸드오프면 errorCode 를 보존해 ErrorNotice 로 넘긴다. 성공/빈
  // 상태와 배타적인 분기다.
  const error = handoff?.kind === 'error' ? handoff : null

  // 22.4: 선택된 정렬 옵션(기본값 일치도 높은순, Req 15.5). 정렬은 순수 코어
  // sortResults 가 수행하며, 이 화면은 선택값만 보관한다.
  const [sortOption, setSortOption] = useState<SortOption>(DEFAULT_SORT)

  // 22.8: 선택된 필터 상태(기본값 = 전체 표시). 필터는 순수 코어 filterResults
  // 가 수행하며, 이 화면은 선택값만 보관한다.
  const [filterState, setFilterState] = useState<FilterState>(EMPTY_FILTER_STATE)

  // 전체 결과(필터링 이전). 핸드오프가 없으면 빈 배열.
  const allResults = success?.results ?? []

  // 플랫폼 옵션은 **필터링 이전**의 전체 결과에서 유도한다. 그래야 플랫폼을
  // 좁혀도 옵션이 사라지지 않는다(Req 16.3).
  const platformOptions = useMemo(
    () => derivePlatformOptions(allResults),
    [allResults],
  )

  // 합성 지점: 결과 → 필터(22.8) → 정렬(22.4) → ResultGrid(22.1). 두 순수 코어
  // 모두 입력을 변형하지 않고 새 배열을 반환하므로 안전하게 합성된다.
  const baseResults = useMemo(
    () => filterResults(allResults, filterState),
    [allResults, filterState],
  )
  const sortedResults = useMemo(
    () => sortResults(baseResults, sortOption),
    [baseResults, sortOption],
  )

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
        22.10: 오류 핸드오프(kind: 'error')면 그리드 대신 코드별 한국어 메시지를
        렌더한다(Req 17.x). NO_RESULTS 는 ErrorNotice 내부에서 정보성 톤으로
        구분된다. 성공 경로(아래)는 그대로 유지한다.
      */}
      {error ? (
        <ErrorNotice errorCode={error.errorCode} />
      ) : success && success.results.length > 0 ? (
        <div className="flex flex-col gap-6">
          {/* 22.8 필터 컨트롤 + 22.4 정렬 컨트롤을 그리드 위에 둔다(Req 16.1~16.3,
              15.1~15.7). 플랫폼 옵션은 필터링 이전 전체 결과에서 유도한다. */}
          <FilterControls
            value={filterState}
            onChange={setFilterState}
            platformOptions={platformOptions}
          />
          <SortControls
            value={sortOption}
            onChange={setSortOption}
            currencyMixed={success.currencyMixed}
          />
          {/*
            22.1 성공 핸드오프 렌더 — 22.8 필터 → 22.4 정렬 적용분을 넘긴다.
            22.2: source 에 따라 배지/구매 버튼을 ResultGrid 의 심으로 주입한다.
          */}
          <ResultGrid
            results={sortedResults}
            renderBadge={(result) =>
              isTestData(result.source) ? <TestDataBadge /> : null
            }
            renderPurchase={(result) => (
              <PurchaseButton source={result.source} link={result.link} />
            )}
          />
        </div>
      ) : (
        // state 없음/무효(직접 접근) 또는 결과 0건 → 빈 상태.
        <div
          data-testid="results-grid"
          className="editorial-grid min-h-[16rem] items-center justify-center text-xs uppercase tracking-tightest text-text/40"
        >
          <div className="flex min-h-[8rem] items-center justify-center bg-background p-8">
            No Results Yet
          </div>
        </div>
      )}
    </section>
  )
}

export default Results
