import {
  SEARCH_STAGE_LABEL,
  SEARCH_STAGE_ORDER,
  type SearchStage,
} from '../lib/searchProgress'

/**
 * SearchProgress — 검색 진행 상태 4단계를 순서대로 보여주는 프레젠테이션 컴포넌트
 * (task 21.2, Req 13.1 / design.md "진행 상태 머신").
 *
 * 순수 코어(`lib/searchProgress.ts`)가 정의한 스테이지 순서(SEARCH_STAGE_ORDER)
 * 와 라벨(SEARCH_STAGE_LABEL)을 그대로 그린다. 상태 전이·흐름 구동은 하지 않고,
 * 상위(Search)가 넘겨준 현재 스테이지만 받아 "완료 / 활성 / 대기"를 표시한다.
 *   - 현재 스테이지 앞의 항목 → 완료(completed)
 *   - 현재 스테이지 → 활성(active)
 *   - 현재 스테이지 뒤의 항목 → 대기(pending)
 * 이렇게 순수 코어에 UI 를 종속시켜 Req 13.1 "순서 표시" 불변식을 한곳에서 지킨다.
 */
interface SearchProgressProps {
  /** 상위(Search)가 구동 중인 현재 진행 스테이지. */
  readonly stage: SearchStage
}

type StageStatus = 'completed' | 'active' | 'pending'

function statusFor(
  index: number,
  currentIndex: number,
): StageStatus {
  if (index < currentIndex) return 'completed'
  if (index === currentIndex) return 'active'
  return 'pending'
}

function SearchProgress({ stage }: SearchProgressProps) {
  const currentIndex = SEARCH_STAGE_ORDER.indexOf(stage)

  return (
    <section
      data-testid="search-progress"
      aria-label="검색 진행 상태"
      aria-live="polite"
      className="flex flex-col gap-4 border border-surface bg-surface/40 p-4"
    >
      <header className="flex flex-col gap-1">
        <h2 className="text-xs font-bold uppercase tracking-tightest text-text/70">
          Progress · 검색 진행 상태
        </h2>
        {/* 현재 활성 스테이지 라벨을 크게 노출한다(Req 13.1). */}
        <p
          data-testid="search-progress-current"
          className="text-2xl font-bold uppercase tracking-tightest md:text-3xl"
        >
          {SEARCH_STAGE_LABEL[stage]}
        </p>
      </header>

      {/* 순서대로 4단계를 나열하고 완료/활성/대기 마커를 붙인다(Req 13.1). */}
      <ol className="flex flex-col gap-2">
        {SEARCH_STAGE_ORDER.map((s, index) => {
          const status = statusFor(index, currentIndex)
          return (
            <li
              key={s}
              data-testid={`search-progress-stage-${s}`}
              data-status={status}
              aria-current={status === 'active' ? 'step' : undefined}
              className={[
                'flex items-center gap-3 text-xs uppercase tracking-tightest transition-colors duration-300 ease-editorial',
                status === 'completed' ? 'text-text/50' : '',
                status === 'active' ? 'font-bold text-accent' : '',
                status === 'pending' ? 'text-text/30' : '',
              ].join(' ')}
            >
              {/* 상태 마커: 완료는 채움, 활성은 테두리+포인트, 대기는 흐린 테두리. */}
              <span
                aria-hidden="true"
                className={[
                  'flex h-4 w-4 shrink-0 items-center justify-center border text-[0.6rem]',
                  status === 'completed'
                    ? 'border-text/50 bg-text/50 text-background'
                    : '',
                  status === 'active' ? 'border-accent text-accent' : '',
                  status === 'pending' ? 'border-text/30' : '',
                ].join(' ')}
              >
                {status === 'completed' ? '✓' : index + 1}
              </span>
              <span>{SEARCH_STAGE_LABEL[s]}</span>
            </li>
          )
        })}
      </ol>
    </section>
  )
}

export default SearchProgress
export type { SearchProgressProps }
