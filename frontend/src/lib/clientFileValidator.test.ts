import { describe, expect, it } from 'vitest'
import {
  ALLOWED_IMAGE_MIME_TYPES,
  MAX_FILE_SIZE_BYTES,
  REJECTION_MESSAGES,
  validateImageFile,
} from './clientFileValidator'

// task 20.2 ClientFileValidator 단위 테스트 — 형식(Req 1.4)·크기(Req 1.5) 검증과
// 거부 메시지의 대표 예시·경계값을 확인한다.
// (전 입력 공간을 다루는 fast-check 속성 테스트 Property 3 은 task 20.3 로 분리.)

function fileLike(type: string, size: number): Pick<File, 'type' | 'size'> {
  return { type, size }
}

describe('validateImageFile — 형식 검증 (Req 1.4)', () => {
  it('허용 MIME 타입(jpeg/png/webp)은 통과한다', () => {
    for (const type of ALLOWED_IMAGE_MIME_TYPES) {
      expect(validateImageFile(fileLike(type, 1024))).toEqual({ ok: true })
    }
  })

  it('허용 목록 밖 형식은 format 사유로 거부한다', () => {
    for (const type of ['image/gif', 'application/pdf', 'text/plain', '', 'image/jpg']) {
      const result = validateImageFile(fileLike(type, 1024))
      expect(result.ok).toBe(false)
      if (!result.ok) {
        expect(result.reason).toBe('format')
        expect(result.message).toBe(REJECTION_MESSAGES.format)
      }
    }
  })
})

describe('validateImageFile — 크기 검증 (Req 1.5)', () => {
  it('정확히 10MB 경계는 통과한다', () => {
    expect(validateImageFile(fileLike('image/png', MAX_FILE_SIZE_BYTES))).toEqual({
      ok: true,
    })
  })

  it('10MB를 1바이트라도 초과하면 size 사유로 거부한다', () => {
    const result = validateImageFile(fileLike('image/png', MAX_FILE_SIZE_BYTES + 1))
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.reason).toBe('size')
      expect(result.message).toBe(REJECTION_MESSAGES.size)
    }
  })

  it('10MB 상수는 백엔드 정책과 동일한 10,485,760 바이트다', () => {
    expect(MAX_FILE_SIZE_BYTES).toBe(10485760)
  })
})

describe('validateImageFile — 사유 우선순위', () => {
  it('형식과 크기가 모두 틀리면 형식 사유를 먼저 보고한다', () => {
    const result = validateImageFile(fileLike('image/gif', MAX_FILE_SIZE_BYTES + 1))
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.reason).toBe('format')
  })
})
