/**
 * ErrorNotice — 백엔드 errorCode 를 한국어 전용 메시지로 매핑해 표시한다
 * (Req 17.1~17.4).
 *
 * [역할 분리]
 * 백엔드는 안정적인 `errorCode`(design.md 오류 코드표)만 반환하고, 화면에 보일
 * 문구는 프론트가 결정한다. 이 컴포넌트는 코드→메시지 매핑 한 곳(ERROR_MESSAGES)
 * 만을 바라보며, 각 오류 유형을 **서로 구분되는 전용 메시지**로 렌더한다
 * (업로드 실패 / 시간 초과 / 결과 없음 / 한도 초과 등, Req 17.1~17.4).
 *
 * [매핑 소스]
 * 문구는 design.md "Error Handling" 의 errorCode→한국어 메시지 표를 그대로
 * 옮긴 것이다(verbatim). 코드가 새로 추가되거나 알 수 없는 값이 오면
 * INTERNAL_ERROR 문구로 폴백해, 사용자에게 빈 화면이나 영어 코드가 노출되지
 * 않게 한다.
 *
 * [NO_RESULTS 톤]
 * NO_RESULTS 는 "실패"라기보다 정보성 안내다(백엔드가 일부 흐름에서 HTTP 200 으로
 * 다루기도 한다). 따라서 겁주는 오류가 아니라 "다른 사진/크롭으로 시도" 를
 * 권하는 차분한 안내 문구를 쓴다. 다만 표시 자리(배선)는 Results 의 error 분기와
 * Search 의 in-page 오류 모두에서 동일하게 이 컴포넌트를 거치게 해 메시지를
 * 일관되게 유지한다.
 */
import type { ApiErrorCode } from '../lib/apiTypes'

/**
 * errorCode → 한국어 메시지 매핑. design.md 오류 코드표의 문구를 그대로 쓴다.
 * 테스트가 직접 참조할 수 있도록 export 한다. 각 코드는 서로 다른 전용 문구를
 * 가진다(Req 17.1~17.4).
 */
export const ERROR_MESSAGES: Record<ApiErrorCode, string> = {
  UPLOAD_FAILED: '이미지 업로드에 실패했습니다. 잠시 후 다시 시도해 주세요.',
  SEARCH_TIMEOUT: '검색 시간이 초과되었습니다. 다시 시도해 주세요.',
  NO_RESULTS:
    '검색 결과가 없습니다. 다른 사진이나 다른 크롭 영역으로 시도해 보세요.',
  RATE_LIMITED:
    '현재 검색 요청이 많아 한도를 초과했습니다. 잠시 후 다시 시도해 주세요.',
  VALIDATION_FAILED:
    '이미지를 확인할 수 없습니다. JPG/PNG/WEBP, 10MB 이하 파일을 사용해 주세요.',
  INTERNAL_ERROR: '일시적인 오류가 발생했습니다. 다시 시도해 주세요.',
}

/**
 * 알 수 없는/신규 코드를 위한 폴백 코드. 매핑에 없으면 INTERNAL_ERROR 문구를
 * 보여준다(Req: 사용자에게 영어 코드·빈 화면을 노출하지 않는다).
 */
const FALLBACK_CODE: ApiErrorCode = 'INTERNAL_ERROR'

/**
 * errorCode 를 받아 대응하는 한국어 메시지를 돌려준다. 매핑에 없는 임의 문자열은
 * INTERNAL_ERROR 메시지로 폴백한다. 순수 함수라 컴포넌트 렌더 없이도 테스트할 수
 * 있다.
 */
export function messageForErrorCode(errorCode: string): string {
  if (errorCode in ERROR_MESSAGES) {
    return ERROR_MESSAGES[errorCode as ApiErrorCode]
  }
  return ERROR_MESSAGES[FALLBACK_CODE]
}

/**
 * NO_RESULTS 는 겁주는 오류가 아니라 정보성 안내다. 톤에 따라 스타일을 분기할 수
 * 있도록 판별만 분리한다(표시 자리는 Results/Search 모두 이 컴포넌트를 거친다).
 */
function isInformational(errorCode: string): boolean {
  return errorCode === 'NO_RESULTS'
}

export interface ErrorNoticeProps {
  /** 백엔드 오류 코드(알 수 없으면 INTERNAL_ERROR 로 폴백). */
  readonly errorCode: string
}

/**
 * 코드에 매핑된 한국어 메시지를 렌더한다. 정보성(NO_RESULTS)은 중립 톤으로,
 * 그 외 오류는 포인트(accent) 톤으로 구분한다 — 네온/그라데이션/과한 그림자
 * 금지(Req 18.3)를 따른다.
 */
function ErrorNotice({ errorCode }: ErrorNoticeProps) {
  const message = messageForErrorCode(errorCode)
  const informational = isInformational(errorCode)

  const tone = informational
    ? 'border-text/20 bg-surface/40 text-text/80'
    : 'border-accent/60 bg-surface/40 text-accent'

  return (
    <p
      data-testid="error-notice"
      data-error-code={errorCode}
      role={informational ? 'status' : 'alert'}
      className={`border px-4 py-3 text-sm ${tone}`}
    >
      {message}
    </p>
  )
}

export default ErrorNotice
