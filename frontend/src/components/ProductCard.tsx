import type { ReactNode } from 'react'
import type { NormalizedResult } from '../lib/apiTypes'

/**
 * ProductCard — RESULTS 화면의 단일 상품 카드 (Req 14.1, 14.2, 14.3, 14.4).
 *
 * 카드는 하나의 정규화 결과(NormalizedResult, snake_case)를 받아 다음을 표시한다:
 *   - 상품 이미지(image_url)
 *   - 상품명(title)
 *   - 판매 플랫폼(platform) · 브랜드가 있으면 함께 표시(Req 14.3)
 *   - 가격+통화 또는 "미확인"(Req 14.2) — price 문자열을 그대로 쓰고(이미 포맷된
 *     가격이거나 "미확인"), currency 가 있으면 옆에 덧붙인다.
 *   - 동일/유사 배지(match_type) · Match_Grade 배지(match_grade) — 단순 표시
 *   - 원본 판매 페이지 이동 버튼 — 새 탭(target="_blank", rel="noopener
 *     noreferrer")으로 link 를 연다(Req 14.4).
 *
 * [이후 작업(task 22.2)을 위한 심(seam)]
 * source=MOCK 의 "TEST DATA" 배지와 구매 버튼 활성/비활성 제어는 task 22.2 의
 * 책임이다. 여기서는 그 책임을 떠안지 않되, 22.2 가 ProductCard 를 수정하지 않고
 * 끼워 넣을 수 있도록 선택적 프롭 두 개로 명시적 심을 남긴다:
 *   - `badgeSlot`: source 배지(예: TEST DATA)를 넣을 자리. 미지정 시 아무것도
 *     렌더하지 않는다.
 *   - `purchaseSlot`: 구매 버튼 등 추가 액션을 넣을 자리. "원본 이동" 버튼과
 *     나란히 렌더된다. 미지정 시 원본 이동 버튼만 보인다.
 * 이렇게 하면 22.2 는 `result.source` 를 보고 두 슬롯을 채우기만 하면 된다.
 */

interface ProductCardProps {
  /** 표시할 정규화 결과(백엔드 snake_case 그대로). */
  readonly result: NormalizedResult
  /**
   * source 배지 자리(task 22.2 TestDataBadge). 미지정 시 배지 없음.
   * 22.1 범위에서는 채우지 않는다.
   */
  readonly badgeSlot?: ReactNode
  /**
   * 추가 액션(구매 버튼 등, task 22.2) 자리. "원본 이동" 버튼과 함께 렌더된다.
   * 22.1 범위에서는 채우지 않는다.
   */
  readonly purchaseSlot?: ReactNode
}

/** 동일/유사 배지의 표시 문구는 match_type 값을 그대로 쓴다(단순 표시). */
function MatchTypeBadge({ matchType }: { matchType: NormalizedResult['match_type'] }) {
  return (
    <span
      data-testid="match-type-badge"
      className="inline-flex items-center border border-text/30 px-2 py-0.5 text-[0.65rem] font-bold uppercase tracking-tightest text-text/80"
    >
      {matchType}
    </span>
  )
}

/** Match_Grade 배지(높음/보통/낮음). 숫자 점수 없이 등급 문자열만 표시한다. */
function MatchGradeBadge({ matchGrade }: { matchGrade: NormalizedResult['match_grade'] }) {
  return (
    <span
      data-testid="match-grade-badge"
      className="inline-flex items-center border border-accent/60 px-2 py-0.5 text-[0.65rem] font-bold uppercase tracking-tightest text-accent"
    >
      {matchGrade}
    </span>
  )
}

/**
 * 가격 표시. price 는 이미 포맷된 가격 문자열이거나 "미확인" 이므로 그대로
 * 노출하고(Req 14.2, 9.5), currency 가 있을 때만 옆에 덧붙인다. currency 가
 * null 이어도 레이아웃이 깨지지 않도록 한다.
 */
function PriceLine({ price, currency }: { price: string; currency: string | null }) {
  return (
    <p data-testid="product-price" className="text-sm font-bold text-text">
      <span data-testid="product-price-value">{price}</span>
      {currency ? (
        <span data-testid="product-currency" className="ml-1 text-text/60">
          {currency}
        </span>
      ) : null}
    </p>
  )
}

function ProductCard({ result, badgeSlot, purchaseSlot }: ProductCardProps) {
  return (
    <article
      data-testid="product-card"
      className="flex flex-col bg-background"
    >
      {/* 상품 이미지 (Req 14.2) */}
      <div className="relative aspect-square overflow-hidden bg-surface">
        <img
          data-testid="product-image"
          src={result.image_url}
          alt={result.title}
          loading="lazy"
          className="h-full w-full object-cover"
        />
        {/* source 배지 자리 (task 22.2). 미지정 시 아무것도 렌더하지 않는다. */}
        {badgeSlot ? (
          <div data-testid="product-badge-slot" className="absolute left-2 top-2">
            {badgeSlot}
          </div>
        ) : null}
      </div>

      <div className="flex flex-1 flex-col gap-3 p-3">
        {/* 플랫폼 · 브랜드(있을 때만, Req 14.3) */}
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[0.65rem] uppercase tracking-tightest text-text/50">
          <span data-testid="product-platform">{result.platform}</span>
          {result.brand ? (
            <>
              <span aria-hidden="true">·</span>
              <span data-testid="product-brand">{result.brand}</span>
            </>
          ) : null}
        </div>

        {/* 상품명 (Req 14.2) */}
        <h3
          data-testid="product-title"
          className="line-clamp-2 text-sm font-bold normal-case tracking-normal text-text"
        >
          {result.title}
        </h3>

        {/* 가격 + 통화 또는 "미확인" (Req 14.2) */}
        <PriceLine price={result.price} currency={result.currency} />

        {/* 동일/유사 배지 · Match_Grade 배지 (Req 14.2) */}
        <div className="flex flex-wrap items-center gap-2">
          <MatchTypeBadge matchType={result.match_type} />
          <MatchGradeBadge matchGrade={result.match_grade} />
        </div>

        {/* 액션: 원본 이동(새 탭) + 추가 액션 자리(task 22.2) */}
        <div className="mt-auto flex flex-wrap items-center gap-2 pt-1">
          {/* 원본 판매 페이지 이동 — 새 탭 (Req 14.4) */}
          <a
            data-testid="product-original-link"
            href={result.link}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center border border-accent px-3 py-1.5 text-[0.65rem] font-bold uppercase tracking-tightest text-accent transition-colors duration-300 ease-editorial hover:bg-accent hover:text-background"
          >
            원본 이동
          </a>
          {/* 구매 버튼 등 (task 22.2). 미지정 시 아무것도 렌더하지 않는다. */}
          {purchaseSlot ? (
            <div data-testid="product-purchase-slot">{purchaseSlot}</div>
          ) : null}
        </div>
      </div>
    </article>
  )
}

export default ProductCard
export type { ProductCardProps }
