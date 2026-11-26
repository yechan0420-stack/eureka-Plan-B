/**
 * mockApi — 로컬 데모 전용 Mock API 어댑터.
 *
 * [목적] AWS 배포가 조직 SCP로 차단된 상황에서, 백엔드(S3/DynamoDB/Lambda) 없이
 * 프론트엔드만으로 업로드→크롭→동의→결과까지 전체 흐름을 로컬에서 시연하기 위한
 * 어댑터다. `VITE_USE_MOCK=true`일 때만 apiClient가 이 모듈을 사용한다.
 *
 * [데이터 정직성 규칙 준수 — steering]
 *   - 모든 결과는 source="MOCK"이며, 화면에 "TEST DATA" 배지가 붙고 구매 버튼이
 *     비활성화되는 대상이다(백엔드 mock.py와 동일 의도, Req 19.1·19.2).
 *   - 모든 link·image_url은 실제 상점처럼 보이는 가짜 링크를 쓰지 않고 안전한 예시
 *     도메인(example.com)만 사용한다(Req 19.5).
 *   - 아래 MOCK_RESULTS는 backend/src/closeller/mock.py의 MOCK_RESULTS와 1:1로
 *     일치한다(동일 5개 항목, 동일 값). 백엔드가 바뀌면 함께 갱신한다.
 *
 * 이 모듈은 네트워크를 전혀 사용하지 않는다. 실제 S3 업로드 단계는 no-op으로
 * 성공 처리한다(로컬에 S3가 없으므로).
 */

import type {
  NormalizedResult,
  RequestUploadResponse,
  SearchResponse,
  UploadContentType,
} from './apiTypes'

/** 백엔드 mock.py의 MOCK_RESULTS와 동일한 고정 데이터셋(5개). */
export const MOCK_RESULTS: readonly NormalizedResult[] = [
  {
    title: '테스트 니트 가디건 (MOCK)',
    link: 'https://example.com/products/mock-1',
    image_url: 'https://example.com/images/mock-1.jpg',
    price: '89,000원',
    currency: 'KRW',
    price_sort_value: 89000,
    platform: '테스트 마켓 A',
    region: '국내',
    match_type: '동일 상품 후보',
    match_grade: '높음',
    source: 'MOCK',
    brand: null,
  },
  {
    title: '테스트 울 코트 (MOCK)',
    link: 'https://example.com/products/mock-2',
    image_url: 'https://example.com/images/mock-2.jpg',
    price: '$120.00',
    currency: 'USD',
    price_sort_value: 120,
    platform: '테스트 마켓 B',
    region: '해외',
    match_type: '유사 상품',
    match_grade: '보통',
    source: 'MOCK',
    brand: null,
  },
  {
    title: '테스트 데님 자켓 (MOCK)',
    link: 'https://example.com/products/mock-3',
    image_url: 'https://example.com/images/mock-3.jpg',
    price: '미확인',
    currency: null,
    price_sort_value: null,
    platform: '테스트 마켓 C',
    region: '미확인',
    match_type: '유사 상품',
    match_grade: '낮음',
    source: 'MOCK',
    brand: null,
  },
  {
    title: '테스트 레더 스니커즈 (MOCK)',
    link: 'https://example.com/products/mock-4',
    image_url: 'https://example.com/images/mock-4.jpg',
    price: '€95.00',
    currency: 'EUR',
    price_sort_value: 95,
    platform: '테스트 마켓 D',
    region: '해외',
    match_type: '동일 상품 후보',
    match_grade: '보통',
    source: 'MOCK',
    brand: 'TEST BRAND',
  },
  {
    title: '테스트 크로스백 (MOCK)',
    link: 'https://example.com/products/mock-5',
    image_url: 'https://example.com/images/mock-5.jpg',
    price: '45,000원',
    currency: 'KRW',
    price_sort_value: 45000,
    platform: '테스트 마켓 E',
    region: '국내',
    match_type: '동일 상품 후보',
    match_grade: '낮음',
    source: 'MOCK',
    brand: null,
  },
]

/** VITE_USE_MOCK 플래그가 켜져 있는지 여부. */
export function isMockEnabled(): boolean {
  return import.meta.env?.VITE_USE_MOCK === 'true'
}

/** 짧은 지연으로 실제 네트워크 왕복을 흉내 내 로딩 상태를 시연한다. */
function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/** Mock: /uploads 응답. 실제 S3 없이 로컬 더미 Presigned POST를 돌려준다. */
export async function mockRequestUpload(
  contentType: UploadContentType,
): Promise<RequestUploadResponse> {
  await delay(200)
  return {
    objectKey: `uploads/mock-${Date.now()}`,
    upload: {
      url: 'https://example.com/mock-upload',
      fields: { 'Content-Type': contentType, key: 'uploads/mock' },
    },
    expiresInSeconds: 300,
  }
}

/** Mock: S3 직접 업로드 단계. 로컬에는 S3가 없으므로 no-op 성공 처리. */
export async function mockUploadToS3(): Promise<void> {
  await delay(200)
}

/** 통화가 둘 이상 섞여 있으면 true(백엔드 compute_currency_mixed와 동일 의도). */
function computeCurrencyMixed(results: readonly NormalizedResult[]): boolean {
  const currencies = new Set(
    results.map((r) => r.currency).filter((c): c is string => c !== null),
  )
  return currencies.size > 1
}

/** Mock: /search 응답. 고정 MOCK 결과를 SearchResponse로 반환한다. */
export async function mockSearch(): Promise<SearchResponse> {
  await delay(500)
  const results = [...MOCK_RESULTS]
  return {
    source: 'MOCK',
    cached: false,
    currencyMixed: computeCurrencyMixed(results),
    results,
  }
}
