// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { ApiErrorCode } from '../lib/apiTypes'
import ErrorNotice, {
  ERROR_MESSAGES,
  messageForErrorCode,
} from './ErrorNotice'

// task 22.10 ErrorNotice (Req 17.1~17.4).
// 각 errorCode 가 서로 구분되는 전용 한국어 메시지로 매핑되는지, 알 수 없는
// 코드는 INTERNAL_ERROR 메시지로 폴백하는지 검증한다. design.md 오류 코드표의
// 문구를 그대로 쓴다(verbatim).

const ALL_CODES: ApiErrorCode[] = [
  'UPLOAD_FAILED',
  'VALIDATION_FAILED',
  'SEARCH_TIMEOUT',
  'NO_RESULTS',
  'RATE_LIMITED',
  'INTERNAL_ERROR',
]

describe('ERROR_MESSAGES 매핑 (task 22.10, Req 17.1~17.4)', () => {
  it('design.md 가 지정한 문구를 그대로 쓴다 (verbatim)', () => {
    expect(ERROR_MESSAGES.UPLOAD_FAILED).toBe(
      '이미지 업로드에 실패했습니다. 잠시 후 다시 시도해 주세요.',
    )
    expect(ERROR_MESSAGES.SEARCH_TIMEOUT).toBe(
      '검색 시간이 초과되었습니다. 다시 시도해 주세요.',
    )
    expect(ERROR_MESSAGES.NO_RESULTS).toBe(
      '검색 결과가 없습니다. 다른 사진이나 다른 크롭 영역으로 시도해 보세요.',
    )
    expect(ERROR_MESSAGES.RATE_LIMITED).toBe(
      '현재 검색 요청이 많아 한도를 초과했습니다. 잠시 후 다시 시도해 주세요.',
    )
    expect(ERROR_MESSAGES.VALIDATION_FAILED).toBe(
      '이미지를 확인할 수 없습니다. JPG/PNG/WEBP, 10MB 이하 파일을 사용해 주세요.',
    )
    expect(ERROR_MESSAGES.INTERNAL_ERROR).toBe(
      '일시적인 오류가 발생했습니다. 다시 시도해 주세요.',
    )
  })

  it('모든 코드가 한국어 메시지를 가지며 서로 구분된다 (Req 17.1~17.4)', () => {
    const messages = ALL_CODES.map((code) => ERROR_MESSAGES[code])
    // 전부 비어 있지 않다.
    for (const msg of messages) {
      expect(msg.length).toBeGreaterThan(0)
    }
    // 서로 중복되지 않는다(각 유형 전용 메시지).
    expect(new Set(messages).size).toBe(messages.length)
    // 영어 코드 문자열이 노출되지 않는다(한국어 전용).
    for (const msg of messages) {
      expect(/[A-Z]{3,}_[A-Z]/.test(msg)).toBe(false)
    }
  })
})

describe('messageForErrorCode 폴백 (task 22.10)', () => {
  it('알 수 없는 코드는 INTERNAL_ERROR 메시지로 폴백한다', () => {
    expect(messageForErrorCode('TOTALLY_UNKNOWN_CODE')).toBe(
      ERROR_MESSAGES.INTERNAL_ERROR,
    )
    expect(messageForErrorCode('')).toBe(ERROR_MESSAGES.INTERNAL_ERROR)
  })

  it('알려진 코드는 해당 메시지를 그대로 돌려준다', () => {
    for (const code of ALL_CODES) {
      expect(messageForErrorCode(code)).toBe(ERROR_MESSAGES[code])
    }
  })
})

describe('ErrorNotice 렌더 (task 22.10, Req 17.1~17.4)', () => {
  afterEach(() => cleanup())

  it('각 errorCode 가 대응하는 한국어 메시지를 렌더한다', () => {
    for (const code of ALL_CODES) {
      render(<ErrorNotice errorCode={code} />)
      const notice = screen.getByTestId('error-notice')
      expect(notice.textContent).toBe(ERROR_MESSAGES[code])
      expect(notice.getAttribute('data-error-code')).toBe(code)
      cleanup()
    }
  })

  it('알 수 없는 코드는 INTERNAL_ERROR 메시지로 폴백 렌더한다', () => {
    render(<ErrorNotice errorCode="SOMETHING_NEW" />)
    const notice = screen.getByTestId('error-notice')
    expect(notice.textContent).toBe(ERROR_MESSAGES.INTERNAL_ERROR)
  })

  it('NO_RESULTS 는 정보성 톤(role=status), 그 외는 오류 톤(role=alert)', () => {
    render(<ErrorNotice errorCode="NO_RESULTS" />)
    expect(screen.getByTestId('error-notice').getAttribute('role')).toBe(
      'status',
    )
    cleanup()

    render(<ErrorNotice errorCode="UPLOAD_FAILED" />)
    expect(screen.getByTestId('error-notice').getAttribute('role')).toBe(
      'alert',
    )
  })
})
