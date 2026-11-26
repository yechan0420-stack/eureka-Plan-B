/**
 * apiTypes — 프론트엔드 API 클라이언트가 주고받는 요청/응답의 TypeScript 타입.
 *
 * 이 파일은 백엔드 실제 계약(contract)과 **정확히** 일치하도록 정의한다.
 * 참조한 백엔드 소스:
 *   - backend/src/closeller/upload_handler.py  (POST /uploads)
 *   - backend/src/closeller/handler.py         (POST /search)
 *   - backend/src/closeller/models.py          (NormalizedResult)
 *
 * [중요 - 필드 케이싱 결정]
 * 검색 결과 항목(NormalizedResult)은 백엔드에서 `dataclasses.asdict(...)`로
 * 직렬화되므로, 응답 JSON의 필드명은 Python dataclass 필드명 그대로인
 * **snake_case**(예: image_url, price_sort_value, match_type, match_grade)다.
 * 따라서 이 프론트엔드 타입도 snake_case로 맞춘다(design.md 매핑표의 camelCase가
 * 아니라 실제 직렬화 결과를 따른다). 최상위 응답 래퍼 필드(source/cached/
 * currencyMixed/results)와 업로드 응답(objectKey/upload/expiresInSeconds)은
 * 핸들러가 손수 만드는 camelCase 키이므로 그대로 camelCase로 둔다.
 */

/* -------------------------------------------------------------------------- */
/* POST /uploads                                                              */
/* -------------------------------------------------------------------------- */

/** 업로드 가능한 Content-Type(백엔드 ALLOWED_CONTENT_TYPES와 동일). */
export type UploadContentType = 'image/jpeg' | 'image/png' | 'image/webp'

/** `POST /uploads` 요청 본문 — 핸들러는 `contentType`만 읽는다. */
export interface RequestUploadBody {
  readonly contentType: UploadContentType
}

/**
 * S3 Presigned POST 정보. `fields`를 먼저 FormData에 넣고, 마지막에 파일을
 * `file` 필드로 append 한 뒤 `url`로 POST 해야 한다(S3 규칙: 파일 필드 last).
 */
export interface PresignedPost {
  readonly url: string
  readonly fields: Readonly<Record<string, string>>
}

/** `POST /uploads` 응답(create_presigned_post 반환 형태). */
export interface RequestUploadResponse {
  readonly objectKey: string
  readonly upload: PresignedPost
  readonly expiresInSeconds: number
}

/* -------------------------------------------------------------------------- */
/* POST /search                                                               */
/* -------------------------------------------------------------------------- */

/**
 * `POST /search` 요청 본문. 핸들러는 `objectKey`만 읽는다. `clientRequestId`는
 * design.md 요청 스키마의 선택 필드이며 서버는 무시한다. **IP는 절대 보내지
 * 않는다** — 서버가 requestContext.http.sourceIp에서만 읽는다(Req 7.8).
 */
export interface SearchRequestBody {
  readonly objectKey: string
  readonly clientRequestId?: string
}

/** 결과 출처. */
export type ResultSource = 'SERP' | 'MOCK'

/** 지역 분류(platform_map.py). */
export type ResultRegion = '국내' | '해외' | '미확인'

/** 동일/유사 유형(normalize/match_grade). */
export type ResultMatchType = '동일 상품 후보' | '유사 상품'

/** 일치도 등급(match_grade.py, 3등급). */
export type ResultMatchGrade = '높음' | '보통' | '낮음'

/**
 * 정규화된 단일 상품 결과. 백엔드 `NormalizedResult` dataclass를 asdict로
 * 직렬화한 형태와 1:1 대응한다(snake_case). 응답에 없는 값은 백엔드가
 * 생성·추론하지 않으므로(Req 9.9), currency/price_sort_value/brand는 null일 수
 * 있다(Python의 None → JSON null).
 */
export interface NormalizedResult {
  readonly title: string
  readonly link: string
  readonly image_url: string
  /** 표시용 가격 문자열 또는 "미확인". */
  readonly price: string
  readonly currency: string | null
  readonly price_sort_value: number | null
  readonly platform: string
  readonly region: ResultRegion
  readonly match_type: ResultMatchType
  readonly match_grade: ResultMatchGrade
  readonly source: ResultSource
  readonly brand: string | null
}

/** `POST /search` 성공 응답(handler._success_response). */
export interface SearchResponse {
  readonly source: ResultSource
  readonly cached: boolean
  readonly currencyMixed: boolean
  readonly results: readonly NormalizedResult[]
}

/**
 * 백엔드 오류 응답 본문(handler._error_response). 안정적 `errorCode`로 프론트의
 * ErrorNotice(task 22.10)가 한국어 메시지를 매핑한다(Req 17.x).
 */
export interface ApiErrorBody {
  readonly errorCode: string
  readonly message: string
}

/** 백엔드 오류 코드(design.md 오류 코드표). */
export type ApiErrorCode =
  | 'UPLOAD_FAILED'
  | 'VALIDATION_FAILED'
  | 'SEARCH_TIMEOUT'
  | 'NO_RESULTS'
  | 'RATE_LIMITED'
  | 'INTERNAL_ERROR'
