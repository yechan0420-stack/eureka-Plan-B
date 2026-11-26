import { useId } from 'react'

/**
 * ConsentGate — 외부 전송 안내 문구 + Consent_Checkbox (Req 3.1, 3.2, 3.3).
 *
 * 크롭이 확정된 뒤(크롭 결과 File 준비 완료) 이 자리에 나타나며, 사진이 외부
 * 검색 서비스(Google Lens, SerpApi)로 전송된다는 사실을 안내하고(Req 3.1)
 * 사용자 동의를 받는다. Consent_Checkbox 가 선택되지 않은 상태에서는 "검색
 * 시작" 동작을 비활성화하고(Req 3.2), 선택되고 사용자가 검색을 시작하면
 * `onStartSearch` 로 진행을 위임한다(Req 3.3).
 *
 * 동의 상태(consented)는 상위에서 소유하고 `onConsentChange` 로 끌어올린다.
 * "검색 시작 가능 여부"는 순수 함수 {@link canStartSearch} 로 분리해, 동의
 * 상태와 업로드 대상(크롭 결과) 준비 여부만으로 결정되도록 해 두었다. 버튼의
 * `disabled` 는 이 함수의 결과를 그대로 반영하므로 "동의 상태와 검색 시작 가능
 * 여부 일치"(design.md Property 26)를 테스트하기 쉽다.
 */

/** 외부 전송 안내 문구 — Req 3.1 에 명시된 문구를 그대로 사용한다. */
export const EXTERNAL_TRANSFER_NOTICE =
  '사진이 외부 검색 서비스(Google Lens, SerpApi)로 전송됩니다'

/**
 * 검색 시작 동작이 가능한지(활성) 여부를 결정하는 순수 함수.
 *
 * 동의하지 않았으면 언제나 false 다(Req 3.2). 동의했더라도 외부로 보낼 크롭
 * 결과가 준비되지 않았으면 시작할 수 없다. 두 조건이 모두 참일 때만 true.
 */
export function canStartSearch(consented: boolean, hasCroppedFile: boolean): boolean {
  return consented && hasCroppedFile
}

interface ConsentGateProps {
  /** Consent_Checkbox 가 선택된 상태인지(동의 여부). 상위가 소유한다. */
  readonly consented: boolean
  /** 동의 상태가 바뀔 때 호출한다(상위로 끌어올림). */
  readonly onConsentChange: (value: boolean) => void
  /** 외부로 전송할 크롭 결과 File 이 준비되었는지. 검색 시작 가능 조건의 일부. */
  readonly hasCroppedFile: boolean
  /** 동의 후 검색을 시작할 때 호출(실제 업로드/검색 흐름은 task 21). */
  readonly onStartSearch: () => void
  /** 상위 흐름(예: 검색 진행 중)에서 전체 게이트를 비활성화한다. */
  readonly disabled?: boolean
}

function ConsentGate({
  consented,
  onConsentChange,
  hasCroppedFile,
  onStartSearch,
  disabled = false,
}: ConsentGateProps) {
  const checkboxId = useId()
  // 검색 시작 가능 여부는 순수 함수로 산정한다. 버튼 disabled 는 그 부정을
  // 그대로 반영하므로, 동의 상태와 활성 여부가 정확히 일치한다(Req 3.2).
  const startEnabled = !disabled && canStartSearch(consented, hasCroppedFile)

  const handleStart = () => {
    if (!startEnabled) return
    onStartSearch()
  }

  return (
    <section
      data-testid="consent-gate"
      className="flex flex-col gap-4 border border-surface bg-surface/40 p-4"
    >
      <header className="flex flex-col gap-1">
        <h2 className="text-xs font-bold uppercase tracking-tightest text-text/70">
          Consent · 외부 전송 동의
        </h2>
        {/* 외부 전송 안내 문구 (Req 3.1) */}
        <p data-testid="external-transfer-notice" className="text-sm text-text/80">
          {EXTERNAL_TRANSFER_NOTICE}
        </p>
      </header>

      {/* Consent_Checkbox (Req 3.1) */}
      <label
        htmlFor={checkboxId}
        className={[
          'flex items-start gap-3 text-sm',
          disabled ? 'cursor-not-allowed text-text/40' : 'cursor-pointer text-text/80',
        ].join(' ')}
      >
        <input
          id={checkboxId}
          data-testid="consent-checkbox"
          type="checkbox"
          checked={consented}
          disabled={disabled}
          onChange={(event) => onConsentChange(event.target.checked)}
          className="mt-0.5 h-4 w-4 shrink-0 accent-accent disabled:cursor-not-allowed"
        />
        <span>
          위 안내를 확인했으며, 크롭한 이미지가 외부 검색 서비스로 전송되는 것에
          동의합니다.
        </span>
      </label>

      <div className="flex flex-wrap items-center gap-3">
        {/* 검색 시작: 미동의 시 비활성화 (Req 3.2) / 동의 시 진행 (Req 3.3) */}
        <button
          type="button"
          data-testid="start-search"
          disabled={!startEnabled}
          aria-disabled={!startEnabled}
          onClick={handleStart}
          className="border border-accent px-5 py-2 text-xs font-bold uppercase tracking-tightest text-accent transition-colors duration-300 ease-editorial hover:bg-accent hover:text-background disabled:cursor-not-allowed disabled:opacity-40"
        >
          Start Search
        </button>
        {!consented ? (
          <span className="text-[0.65rem] uppercase tracking-tightest text-text/40">
            동의 후 검색을 시작할 수 있습니다
          </span>
        ) : null}
      </div>
    </section>
  )
}

export default ConsentGate
export type { ConsentGateProps }
