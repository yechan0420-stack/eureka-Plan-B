import { isPurchaseEnabled } from '../lib/sourceGating'
import type { NormalizedResult, ResultSource } from '../lib/apiTypes'

/**
 * PurchaseButton — 결과의 커머스 액션(구매) 버튼 (Req 19.4).
 *
 * [구매 버튼 vs 원본 이동 링크]
 * ProductCard 에는 이미 "원본 이동"(open original) 링크가 있다(task 22.1, Req
 * 14.4). 그 링크는 원본 판매 페이지를 새 탭으로 여는 탐색 수단으로 source 와
 * 무관하게 항상 유지된다. 반면 이 PurchaseButton 은 design.md 가 TestDataBadge
 * 항목에서 별도로 규정한 "구매 버튼"이며, source 에 따라 게이팅되는 커머스
 * 액션이다(Req 19.4). 둘은 역할이 다르므로 서로 대체하지 않고 공존한다.
 *
 * [게이팅 규칙]
 *   - source="MOCK": 테스트 데이터이므로 실제 구매가 불가 → 버튼 비활성화.
 *   - source="SERP": 실제 결과 → 버튼 활성화, 클릭 시 원본 판매 페이지를 새 탭으로
 *     연다(link).
 * 활성/비활성 판단은 순수 함수 `isPurchaseEnabled(source)` 에 위임해 로직을 UI 와
 * 분리한다(task 22.3 Property 25 가 그 함수를 직접 검증).
 *
 * [접근성/표시]
 * 비활성 시 네이티브 `disabled` 와 `aria-disabled="true"` 를 함께 두고, 클릭을
 * 막는다(비활성 버튼은 기본적으로 클릭 이벤트가 발생하지 않지만 방어적으로
 * onClick 에서도 차단). 비활성 상태는 흐리게 표시하고 포인터 커서를 끈다.
 */

interface PurchaseButtonProps {
  /** 결과 출처. 활성/비활성을 결정한다(Req 19.4). */
  readonly source: ResultSource
  /** 활성 시 구매로 이동할 원본 판매 페이지 URL. */
  readonly link: NormalizedResult['link']
}

function PurchaseButton({ source, link }: PurchaseButtonProps) {
  const enabled = isPurchaseEnabled(source)

  const handleClick = () => {
    // 비활성 상태에서는 어떤 동작도 하지 않는다(방어적 차단).
    if (!enabled) return
    window.open(link, '_blank', 'noopener,noreferrer')
  }

  return (
    <button
      type="button"
      data-testid="purchase-button"
      disabled={!enabled}
      aria-disabled={!enabled}
      onClick={handleClick}
      className={[
        'inline-flex items-center px-3 py-1.5 text-[0.65rem] font-bold uppercase tracking-tightest transition-colors duration-300 ease-editorial',
        enabled
          ? 'bg-accent text-background hover:bg-accent/80'
          : 'cursor-not-allowed border border-text/20 text-text/30',
      ].join(' ')}
    >
      구매
    </button>
  )
}

export default PurchaseButton
export type { PurchaseButtonProps }
