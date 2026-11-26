/// <reference types="vite/client" />

// 프론트엔드가 사용하는 Vite 환경변수 타입 선언(task 21.1, Req 21.5).
// VITE_API_BASE_URL: 백엔드 API Gateway 베이스 URL. 미정의 시 same-origin 상대 경로.
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  // VITE_USE_MOCK: 'true'면 백엔드 대신 로컬 Mock 응답 사용(로컬 데모 전용).
  readonly VITE_USE_MOCK?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
