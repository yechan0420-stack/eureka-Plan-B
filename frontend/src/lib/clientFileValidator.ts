/**
 * ClientFileValidator — 선택된 파일의 형식(JPG/PNG/WEBP)과 크기(10MB)를
 * 클라이언트에서 검증하고, 실패 시 사용자에게 보여줄 거부 메시지를 돌려주는
 * 순수(pure) 모듈 (Req 1.4, 1.5 / design.md ClientFileValidator).
 *
 * 이 모듈은 React 나 DOM 에 의존하지 않는 순수 로직이라, task 20.3 의
 * fast-check 속성 테스트(Property 3)가 로직을 직접 검증할 수 있다.
 *
 * - 허용 형식은 Presigned POST 허용 Content-Type 목록과 동일하게 맞춘다
 *   (image/jpeg, image/png, image/webp — Req 4.2, 4.8).
 * - 최대 크기는 백엔드/업로드 정책과 동일한 10MB(10,485,760 바이트)로 맞춘다
 *   (Req 1.5, 4.2, 5.2).
 */

/** 허용 이미지 MIME 타입 (Presigned POST 허용 Content-Type 과 동일). */
export const ALLOWED_IMAGE_MIME_TYPES = [
  'image/jpeg',
  'image/png',
  'image/webp',
] as const

/** 허용 MIME 타입의 리터럴 유니온. */
export type AllowedImageMimeType = (typeof ALLOWED_IMAGE_MIME_TYPES)[number]

/** 최대 허용 파일 크기: 10MB (백엔드 content-length-range 와 동일한 바이트 수). */
export const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024 // 10,485,760

/** 검증 실패 사유 코드. */
export type FileRejectionReason = 'format' | 'size'

/** 거부(실패) 사유별 사용자 안내 메시지 (한국어 전용). */
export const REJECTION_MESSAGES: Record<FileRejectionReason, string> = {
  // Req 1.4: 지원 형식 안내 메시지
  format: '지원하지 않는 형식입니다. JPG, PNG, WEBP 파일만 업로드할 수 있습니다.',
  // Req 1.5: 크기 초과 안내 메시지
  size: '파일 크기가 너무 큽니다. 10MB 이하의 이미지를 사용해 주세요.',
}

/** 검증 결과 타입. 성공이면 ok=true, 실패면 사유와 메시지를 담는다. */
export type FileValidationResult =
  | { readonly ok: true }
  | { readonly ok: false; readonly reason: FileRejectionReason; readonly message: string }

/** 주어진 MIME 타입이 허용 목록에 포함되는지 (형식 검증만, Property 3). */
export function isAllowedImageType(type: string): type is AllowedImageMimeType {
  return (ALLOWED_IMAGE_MIME_TYPES as readonly string[]).includes(type)
}

/** 주어진 바이트 크기가 허용 범위(10MB 이하)인지 (크기 검증만). */
export function isAllowedFileSize(size: number): boolean {
  return Number.isFinite(size) && size >= 0 && size <= MAX_FILE_SIZE_BYTES
}

/**
 * 파일을 검증한다. 형식을 먼저 확인하고, 그다음 크기를 확인한다.
 *
 * `File` 전체 대신 `{ type, size }` 만 받는 가벼운 입력을 허용하여
 * 순수 로직을 환경에 의존하지 않고 테스트할 수 있게 한다.
 */
export function validateImageFile(
  file: Pick<File, 'type' | 'size'>,
): FileValidationResult {
  if (!isAllowedImageType(file.type)) {
    return { ok: false, reason: 'format', message: REJECTION_MESSAGES.format }
  }
  if (!isAllowedFileSize(file.size)) {
    return { ok: false, reason: 'size', message: REJECTION_MESSAGES.size }
  }
  return { ok: true }
}
