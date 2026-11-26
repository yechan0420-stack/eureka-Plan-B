/// <reference types="vite/client" />

// 프론트엔드가 사용하는 Vite 환경변수 타입 선언(task 21.1, Req 21.5).
// VITE_API_BASE_URL: 백엔드 API Gateway 베이스 URL. 미정의 시 same-origin 상대 경로.
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
