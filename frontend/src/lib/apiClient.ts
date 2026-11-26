/**
 * apiClient — 프론트엔드가 우리 백엔드(API Gateway)와 S3에만 이야기하는 타입드
 * API 클라이언트 (task 21.1, Req 4.1, 4.3, 21.5 / design.md "API 클라이언트").
 *
 * 흐름(3단계, design.md 시퀀스 다이어그램 그대로):
 *   1. `POST {VITE_API_BASE_URL}/uploads` {contentType}
 *        → Presigned POST(objectKey, upload{url,fields}, expiresInSeconds) 수신
 *   2. 크롭된 이미지를 S3에 **직접** 업로드(Presigned POST). FormData에 서버가 준
 *      `fields`를 먼저 모두 넣고, **마지막에** `file`을 append 한 뒤 `upload.url`로
 *      POST 한다(S3 규칙: 파일 필드는 반드시 마지막).
 *   3. `POST {VITE_API_BASE_URL}/search` {objectKey} → 검색 결과 수신.
 *
 * [보안 - 외부 API Key 미포함 (Req 21.5)]
 * 이 모듈은 어떤 외부 검색 API Key도 참조/전송하지 않는다. 우리 API Gateway의 두
 * 라우트(`/uploads`, `/search`)와 S3 Presigned POST URL에만 요청한다. 외부 검색
 * (SerpApi)과 그 Key는 전적으로 백엔드(SSM SecureString 런타임 로드)에서만
 * 다뤄진다. IP도 보내지 않는다 — 서버가 requestContext에서만 읽는다(Req 7.8).
 *
 * [베이스 URL]
 * `import.meta.env.VITE_API_BASE_URL`에서 읽는다. 정의되지 않으면 ''(빈 문자열)로
 * 폴백하여 **same-origin 상대 경로**(`/uploads`, `/search`)로 호출한다. 이는 로컬
 * 프록시/동일 출처 배포에서 안전하게 동작하며, 배포 시에는 Amplify 환경변수로
 * API Gateway 엔드포인트를 주입한다(.env.example의 VITE_API_BASE_URL 참조).
 *
 * 네트워크는 전부 `fetch`로 수행한다. 비 2xx 응답은 백엔드 `errorCode`를 담은
 * `ApiError`로 표면화하여, task 22.10 ErrorNotice가 코드별 한국어 메시지로 매핑할
 * 수 있게 한다(Req 17.x). 이 모듈은 UI 상태 머신을 다루지 않는다(그것은 task
 * 21.2) — 21.2/Search가 호출할 깨끗한 함수만 export 한다.
 */

import type {
  ApiErrorBody,
  RequestUploadResponse,
  SearchResponse,
  UploadContentType,
} from './apiTypes'

export type {
  ApiErrorBody,
  ApiErrorCode,
  NormalizedResult,
  PresignedPost,
  RequestUploadResponse,
  SearchResponse,
  UploadContentType,
} from './apiTypes'

/** 우리 API Gateway 라우트 경로(상대). 베이스 URL 뒤에 붙는다. */
export const UPLOADS_PATH = '/uploads'
export const SEARCH_PATH = '/search'

/** S3 Presigned POST FormData에서 파일이 들어갈 필드명(반드시 마지막에 append). */
export const S3_FILE_FIELD = 'file'

/**
 * 네트워크/계약 오류를 표현하는 예외. `errorCode`는 백엔드 오류 코드표의 안정적
 * 코드이며(없으면 'INTERNAL_ERROR'), ErrorNotice(22.10)가 이를 한국어 메시지로
 * 매핑한다. `status`는 HTTP 상태 코드다.
 */
export class ApiError extends Error {
  readonly errorCode: string
  readonly status: number

  constructor(errorCode: string, message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.errorCode = errorCode
    this.status = status
    // Error 상속 시 프로토타입 체인 복원(ES5 타겟 호환).
    Object.setPrototypeOf(this, ApiError.prototype)
  }
}

/**
 * 베이스 URL을 안전하게 해석한다. `VITE_API_BASE_URL`이 없거나 비어 있으면
 * ''(same-origin 상대 경로)로 폴백한다. 끝의 슬래시는 제거해 경로 중복을 막는다.
 */
export function resolveBaseUrl(): string {
  // import.meta.env는 Vite가 빌드 시 주입한다. 테스트/비 Vite 환경에서 안전하게
  // 접근하기 위해 옵셔널 체이닝으로 읽는다.
  const raw = import.meta.env?.VITE_API_BASE_URL
  if (typeof raw !== 'string' || raw.length === 0) {
    return ''
  }
  return raw.replace(/\/+$/, '')
}

/** 베이스 URL과 라우트 경로를 합쳐 완전한 엔드포인트 URL을 만든다. */
function endpoint(path: string): string {
  return `${resolveBaseUrl()}${path}`
}

/**
 * 우리 백엔드 응답(Response)에서 성공 JSON을 파싱하거나, 비 2xx면 백엔드
 * `errorCode`를 담은 `ApiError`를 던진다. 본문이 JSON이 아니어도 안전하게
 * 처리한다(네트워크/게이트웨이 오류 등).
 */
async function parseJsonOrThrow<T>(res: Response): Promise<T> {
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    body = null
  }

  if (!res.ok) {
    const err = body as Partial<ApiErrorBody> | null
    const code =
      err && typeof err.errorCode === 'string' ? err.errorCode : 'INTERNAL_ERROR'
    const message =
      err && typeof err.message === 'string'
        ? err.message
        : '요청을 처리하지 못했습니다.'
    throw new ApiError(code, message, res.status)
  }

  return body as T
}

/**
 * 1단계: `POST /uploads`로 Presigned POST를 요청한다.
 *
 * 본문은 백엔드가 읽는 `{ contentType }`만 보낸다. 성공 시 objectKey와
 * Presigned POST(url, fields), 유효 시간을 반환한다.
 *
 * @param contentType 업로드할 크롭 이미지의 MIME 타입(image/jpeg|png|webp).
 */
export async function requestUpload(
  contentType: UploadContentType,
): Promise<RequestUploadResponse> {
  const res = await fetch(endpoint(UPLOADS_PATH), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ contentType }),
  })
  return parseJsonOrThrow<RequestUploadResponse>(res)
}

/**
 * 2단계: 크롭된 파일을 S3에 **직접** 업로드한다(Presigned POST).
 *
 * S3 Presigned POST 규칙상, 서버가 준 `fields`(key, Content-Type, policy,
 * x-amz-signature 등)를 **먼저** 모두 FormData에 넣고, 파일은 **마지막에** `file`
 * 필드로 append 해야 한다. 순서가 틀리면 S3가 거부한다. 응답이 2xx가 아니면
 * 업로드 실패(`UPLOAD_FAILED`)로 표면화한다(Req 17.1).
 *
 * 이 요청은 우리 API가 아니라 S3로 직접 간다. 외부 검색 API Key는 어디에도
 * 포함되지 않는다.
 *
 * @param presignedPost `requestUpload` 응답의 `upload`(url, fields).
 * @param file 업로드할 크롭 이미지 파일/Blob.
 */
export async function uploadToS3(
  presignedPost: { readonly url: string; readonly fields: Record<string, string> },
  file: Blob,
): Promise<void> {
  const form = new FormData()
  // 1) 서버가 준 서명 필드를 먼저 모두 넣는다.
  for (const [name, value] of Object.entries(presignedPost.fields)) {
    form.append(name, value)
  }
  // 2) 파일은 반드시 마지막에 append 한다(S3 Presigned POST 규칙).
  form.append(S3_FILE_FIELD, file)

  const res = await fetch(presignedPost.url, {
    method: 'POST',
    body: form,
  })

  if (!res.ok) {
    throw new ApiError(
      'UPLOAD_FAILED',
      '이미지 업로드에 실패했습니다.',
      res.status,
    )
  }
}

/**
 * 3단계: `POST /search`로 업로드된 객체 키에 대한 검색을 실행한다.
 *
 * 본문은 `{ objectKey }`만 보낸다. **IP는 보내지 않는다** — 서버가
 * requestContext에서만 읽는다(Req 7.8). 선택적으로 `clientRequestId`를 전달할 수
 * 있으나 서버는 무시한다(design.md 요청 스키마). 비 2xx면 백엔드 errorCode를 담은
 * `ApiError`를 던진다.
 *
 * @param objectKey `requestUpload`가 돌려준 업로드 객체 키.
 * @param clientRequestId (선택) 클라이언트 상관관계용 식별자. 서버는 무시한다.
 */
export async function search(
  objectKey: string,
  clientRequestId?: string,
): Promise<SearchResponse> {
  const body: { objectKey: string; clientRequestId?: string } = { objectKey }
  if (clientRequestId !== undefined) {
    body.clientRequestId = clientRequestId
  }
  const res = await fetch(endpoint(SEARCH_PATH), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return parseJsonOrThrow<SearchResponse>(res)
}

/**
 * 세 단계를 순서대로 조립하는 상위 함수: 업로드 발급 → S3 직접 업로드 → 검색.
 *
 * task 21.2(SearchProgress)/Search 화면이 이 한 함수를 호출해 전체 흐름을 돌릴 수
 * 있다. 단계 간 상태 전이(UI)는 여기서 다루지 않는다 — 각 단계가 끝나면 다음
 * 단계로 넘어갈 뿐이며, 오류는 `ApiError`로 전파되어 상위에서 매핑한다.
 *
 * @param croppedFile 브라우저에서 크롭한 결과 이미지 파일(cropToFile 결과).
 * @param clientRequestId (선택) 검색 요청 상관관계용 식별자.
 */
export async function runSearch(
  croppedFile: File,
  clientRequestId?: string,
): Promise<SearchResponse> {
  const contentType = croppedFile.type as UploadContentType
  const { objectKey, upload } = await requestUpload(contentType)
  await uploadToS3({ url: upload.url, fields: { ...upload.fields } }, croppedFile)
  return search(objectKey, clientRequestId)
}
