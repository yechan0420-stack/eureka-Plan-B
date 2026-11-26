import {
  MATCH_TYPE_OPTIONS,
  REGION_OPTIONS,
  hasActiveFilter,
  toggleValue,
  type FilterState,
} from '../lib/filterResults'

/**
 * FilterControls — RESULTS 화면의 필터 선택 프레젠테이션 컴포넌트
 * (task 22.8, Req 16.1~16.3 / design.md "FilterControls: 국내·해외 / 동일·유사 /
 * 플랫폼").
 *
 * 필터 "로직"은 전혀 들고 있지 않다(controlled). 순수 코어(`lib/filterResults.ts`)
 * 가 정의한 옵션(REGION_OPTIONS / MATCH_TYPE_OPTIONS)과, 상위(Results)가 현재
 * 결과에서 유도해 넘겨준 플랫폼 옵션(platformOptions)을 그대로 그린다. 현재
 * 필터 상태(value)와 변경 콜백(onChange)만 받아 선택을 상위로 끌어올린다. 실제
 * 필터링은 Results 가 filterResults(results, value) 로 수행한다.
 *
 * [토글 의미] 각 칩은 on/off 토글이다. 선택을 켜면 그 값이 패싯 선택 집합에
 * 더해지고(패싯 내 OR), 모두 끄면 그 패싯은 필터하지 않는다(= 전체 표시). 패싯
 * 간은 AND 로 합성된다(filterResults.ts 주석 참조).
 *
 * 스타일: SortControls 와 동일한 포인트/보조배경 기반 작은 볼드 모노톤 —
 * 네온/그라데이션/과한 그림자 금지(Req 18.3)를 따른다.
 */

interface FilterControlsProps {
  /** 현재 필터 상태(controlled). */
  readonly value: FilterState
  /** 필터 상태 변경 콜백. 상위가 상태를 보관한다. */
  readonly onChange: (next: FilterState) => void
  /**
   * 현재 결과에서 유도된 플랫폼 옵션(derivePlatformOptions). 상위는 필터링
   * 이전의 전체 결과에서 유도해 넘겨, 필터를 좁혀도 옵션이 사라지지 않게 한다.
   */
  readonly platformOptions: readonly string[]
}

/** 토글 칩 하나. aria-pressed 로 선택 상태를 노출한다(SortControls 와 동일 톤). */
function FilterChip({
  label,
  selected,
  testId,
  onToggle,
}: {
  readonly label: string
  readonly selected: boolean
  readonly testId: string
  readonly onToggle: () => void
}) {
  return (
    <button
      type="button"
      data-testid={testId}
      aria-pressed={selected}
      onClick={onToggle}
      className={[
        'border px-3 py-1 text-xs uppercase tracking-tightest transition-colors duration-200 ease-editorial',
        selected
          ? 'border-accent bg-accent font-bold text-background'
          : 'border-text/30 text-text/70 hover:border-text/60',
      ].join(' ')}
    >
      {label}
    </button>
  )
}

function FilterControls({
  value,
  onChange,
  platformOptions,
}: FilterControlsProps) {
  return (
    <section
      data-testid="filter-controls"
      aria-label="필터"
      className="flex flex-col gap-3"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-bold uppercase tracking-tightest text-text/70">
          Filter · 필터
        </span>
        {hasActiveFilter(value) ? (
          <span
            data-testid="filter-active-indicator"
            className="text-xs tracking-tightest text-accent"
          >
            필터 적용 중
          </span>
        ) : null}
      </div>

      {/* 지역 패싯(국내/해외/미확인, Req 16.1). */}
      <div
        role="group"
        aria-label="지역 필터"
        className="flex flex-wrap items-center gap-2"
      >
        <span className="w-16 text-xs uppercase tracking-tightest text-text/50">
          국내·해외
        </span>
        {REGION_OPTIONS.map((region) => (
          <FilterChip
            key={region}
            label={region}
            testId={`filter-region-${region}`}
            selected={value.regions.includes(region)}
            onToggle={() =>
              onChange({ ...value, regions: toggleValue(value.regions, region) })
            }
          />
        ))}
      </div>

      {/* 유형 패싯(동일/유사, Req 16.2). */}
      <div
        role="group"
        aria-label="유형 필터"
        className="flex flex-wrap items-center gap-2"
      >
        <span className="w-16 text-xs uppercase tracking-tightest text-text/50">
          동일·유사
        </span>
        {MATCH_TYPE_OPTIONS.map((matchType) => (
          <FilterChip
            key={matchType}
            label={matchType}
            testId={`filter-match-type-${matchType}`}
            selected={value.matchTypes.includes(matchType)}
            onToggle={() =>
              onChange({
                ...value,
                matchTypes: toggleValue(value.matchTypes, matchType),
              })
            }
          />
        ))}
      </div>

      {/* 플랫폼 패싯(결과에서 유도, Req 16.3). 옵션이 없으면 그룹을 숨긴다. */}
      {platformOptions.length > 0 ? (
        <div
          role="group"
          aria-label="플랫폼 필터"
          className="flex flex-wrap items-center gap-2"
        >
          <span className="w-16 text-xs uppercase tracking-tightest text-text/50">
            플랫폼
          </span>
          {platformOptions.map((platform) => (
            <FilterChip
              key={platform}
              label={platform}
              testId={`filter-platform-${platform}`}
              selected={value.platforms.includes(platform)}
              onToggle={() =>
                onChange({
                  ...value,
                  platforms: toggleValue(value.platforms, platform),
                })
              }
            />
          ))}
        </div>
      ) : null}
    </section>
  )
}

export default FilterControls
export type { FilterControlsProps }
