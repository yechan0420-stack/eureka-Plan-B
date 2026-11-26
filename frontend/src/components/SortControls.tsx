import {
  SORT_OPTION_LABEL,
  SORT_OPTION_ORDER,
  type SortOption,
} from '../lib/sortResults'

/**
 * SortControls — RESULTS 화면의 정렬 옵션 선택 프레젠테이션 컴포넌트
 * (task 22.4, Req 15.1~15.7 / design.md "SortControls").
 *
 * 정렬 "로직"은 전혀 들고 있지 않다. 순수 코어(`lib/sortResults.ts`)가 정의한
 * 옵션 목록(SORT_OPTION_ORDER)과 라벨(SORT_OPTION_LABEL)을 그대로 그리고,
 * 현재 선택값(value)과 변경 콜백(onChange)만 받아 상위(Results)로 선택을
 * 끌어올린다(controlled). 실제 정렬은 Results 가 sortResults(results, value)로
 * 수행한다. 이렇게 "어떤 순서인가"(로직)와 "무엇을 고르게 하는가"(UI)를 분리한다.
 *
 * [통화 혼재 안내 — Req 15.4, 15.7]
 * 서로 다른 통화가 섞였을 때(currencyMixed=true) 환율 변환 없이 숫자값으로만
 * 정렬하므로, 사용자가 통화가 섞여 있음을 알 수 있도록 상단 안내 문구를 함께
 * 보여준다. currencyMixed=false 이면 안내를 렌더하지 않는다.
 *
 * 스타일: 포인트/보조배경 기반 작은 볼드 모노톤 — 네온/그라데이션/과한 그림자
 * 금지(Req 18.3)를 따른다.
 */

/** 통화 혼재 시 상단에 노출하는 안내 문구(Req 15.4, 15.7). */
export const CURRENCY_MIXED_NOTICE =
  '검색 결과에 서로 다른 통화가 섞여 있습니다. 환율 변환 없이 가격 숫자값 그대로 정렬합니다.'

interface SortControlsProps {
  /** 현재 선택된 정렬 옵션(controlled). */
  readonly value: SortOption
  /** 정렬 옵션 변경 콜백. 상위가 상태를 보관한다. */
  readonly onChange: (option: SortOption) => void
  /** 통화 혼재 여부. true 이면 상단 안내 문구를 표시한다(Req 15.4, 15.7). */
  readonly currencyMixed: boolean
}

function SortControls({ value, onChange, currencyMixed }: SortControlsProps) {
  return (
    <section
      data-testid="sort-controls"
      aria-label="정렬"
      className="flex flex-col gap-3"
    >
      {/* 통화 혼재 안내(Req 15.4, 15.7). 혼재가 아니면 렌더하지 않는다. */}
      {currencyMixed ? (
        <p
          data-testid="currency-mixed-notice"
          role="note"
          className="border border-accent/40 bg-surface/40 px-3 py-2 text-xs tracking-tightest text-text/70"
        >
          {CURRENCY_MIXED_NOTICE}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-bold uppercase tracking-tightest text-text/70">
          Sort · 정렬
        </span>
        {/* 각 정렬 옵션을 토글 버튼으로 노출한다(순수 코어의 나열 순서 그대로). */}
        <div
          role="group"
          aria-label="정렬 기준"
          className="flex flex-wrap gap-2"
        >
          {SORT_OPTION_ORDER.map((option) => {
            const selected = option === value
            return (
              <button
                key={option}
                type="button"
                data-testid={`sort-option-${option}`}
                aria-pressed={selected}
                onClick={() => onChange(option)}
                className={[
                  'border px-3 py-1 text-xs uppercase tracking-tightest transition-colors duration-200 ease-editorial',
                  selected
                    ? 'border-accent bg-accent font-bold text-background'
                    : 'border-text/30 text-text/70 hover:border-text/60',
                ].join(' ')}
              >
                {SORT_OPTION_LABEL[option]}
              </button>
            )
          })}
        </div>
      </div>
    </section>
  )
}

export default SortControls
export type { SortControlsProps }
