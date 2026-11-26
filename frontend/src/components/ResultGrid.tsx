import type { ReactNode } from 'react'
import type { NormalizedResult } from '../lib/apiTypes'
import ProductCard from './ProductCard'

/**
 * ResultGrid — 정규화된 상품 결과 목록을 상품 카드 그리드로 렌더한다
 * (Req 14.1: 각 결과를 Product_Card 로 표시).
 *
 * 레이아웃은 전역 `editorial-grid` 클래스(index.css, Req 18.4)를 재사용해
 * 모바일 2열 / md 3열 / lg 4열 반응형 그리드를 만든다.
 *
 * [이후 작업(task 22.2)을 위한 심(seam)]
 * source=MOCK 배지·구매 버튼 제어(22.2)는 카드별로 슬롯을 통해 주입한다.
 * ResultGrid 는 선택적 렌더 함수 두 개(`renderBadge`, `renderPurchase`)를 받아
 * 각 결과마다 호출하고 그 결과를 ProductCard 의 badgeSlot/purchaseSlot 으로
 * 넘긴다. 22.1 범위에서는 둘 다 넘기지 않으므로 카드에는 "원본 이동" 버튼만
 * 보인다. 22.2 는 ResultGrid 를 수정하지 않고 이 두 프롭만 채우면 된다.
 */

interface ResultGridProps {
  /** 렌더할 정규화 결과 목록. */
  readonly results: readonly NormalizedResult[]
  /** 각 결과의 source 배지(task 22.2 TestDataBadge). 미지정 시 배지 없음. */
  readonly renderBadge?: (result: NormalizedResult) => ReactNode
  /** 각 결과의 구매 버튼 등 추가 액션(task 22.2). 미지정 시 없음. */
  readonly renderPurchase?: (result: NormalizedResult) => ReactNode
}

function ResultGrid({ results, renderBadge, renderPurchase }: ResultGridProps) {
  return (
    <div data-testid="results-grid" className="editorial-grid">
      {results.map((result, index) => (
        // link 는 정규화 단계에서 정규화 URL 기준 중복이 제거되어 유일하므로
        // 안정적인 key 로 쓸 수 있다. 혹시 모를 중복에 대비해 index 를 보조로 붙인다.
        <ProductCard
          key={`${result.link}#${index}`}
          result={result}
          badgeSlot={renderBadge?.(result)}
          purchaseSlot={renderPurchase?.(result)}
        />
      ))}
    </div>
  )
}

export default ResultGrid
export type { ResultGridProps }
