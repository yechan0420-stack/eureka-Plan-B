// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ConsentGate, {
  EXTERNAL_TRANSFER_NOTICE,
  canStartSearch,
} from './ConsentGate'

// task 20.5 ConsentGate 예시 테스트.
// 외부 전송 안내 문구·Consent_Checkbox 표시(Req 3.1), 미동의 시 검색 시작
// 비활성화(Req 3.2), 동의 후 검색 시작 진행(Req 3.3)을 확인한다.
// (fast-check 속성 테스트 Property 26 은 task 20.6 으로 분리된다.)

describe('canStartSearch (task 20.5)', () => {
  it('requires both consent and a ready cropped file', () => {
    expect(canStartSearch(false, false)).toBe(false)
    expect(canStartSearch(false, true)).toBe(false)
    expect(canStartSearch(true, false)).toBe(false)
    expect(canStartSearch(true, true)).toBe(true)
  })
})

describe('ConsentGate (task 20.5)', () => {
  afterEach(() => cleanup())

  it('shows the external-transfer notice and a consent checkbox (Req 3.1)', () => {
    render(
      <ConsentGate
        consented={false}
        onConsentChange={() => {}}
        hasCroppedFile
        onStartSearch={() => {}}
      />,
    )
    expect(screen.getByTestId('external-transfer-notice').textContent).toBe(
      EXTERNAL_TRANSFER_NOTICE,
    )
    const checkbox = screen.getByTestId('consent-checkbox') as HTMLInputElement
    expect(checkbox.type).toBe('checkbox')
    expect(checkbox.checked).toBe(false)
  })

  it('disables start search while not consented (Req 3.2)', () => {
    const onStartSearch = vi.fn()
    render(
      <ConsentGate
        consented={false}
        onConsentChange={() => {}}
        hasCroppedFile
        onStartSearch={onStartSearch}
      />,
    )
    const start = screen.getByTestId('start-search') as HTMLButtonElement
    expect(start.disabled).toBe(true)
    fireEvent.click(start)
    expect(onStartSearch).not.toHaveBeenCalled()
  })

  it('keeps start disabled when consented but no cropped file is ready', () => {
    render(
      <ConsentGate
        consented
        onConsentChange={() => {}}
        hasCroppedFile={false}
        onStartSearch={() => {}}
      />,
    )
    expect((screen.getByTestId('start-search') as HTMLButtonElement).disabled).toBe(
      true,
    )
  })

  it('enables start and proceeds when consented and cropped file ready (Req 3.3)', () => {
    const onStartSearch = vi.fn()
    render(
      <ConsentGate
        consented
        onConsentChange={() => {}}
        hasCroppedFile
        onStartSearch={onStartSearch}
      />,
    )
    const start = screen.getByTestId('start-search') as HTMLButtonElement
    expect(start.disabled).toBe(false)
    fireEvent.click(start)
    expect(onStartSearch).toHaveBeenCalledTimes(1)
  })

  it('raises consent changes to the parent via onConsentChange', () => {
    const onConsentChange = vi.fn()
    render(
      <ConsentGate
        consented={false}
        onConsentChange={onConsentChange}
        hasCroppedFile
        onStartSearch={() => {}}
      />,
    )
    fireEvent.click(screen.getByTestId('consent-checkbox'))
    expect(onConsentChange).toHaveBeenCalledWith(true)
  })
})
