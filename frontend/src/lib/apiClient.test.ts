import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  ApiError,
  requestUpload,
  runSearch,
  search,
  uploadToS3,
} from './apiClient'

// 이 테스트는 실제 fetch 네트워크 경로(/uploads → S3 → /search)를 검증한다.
// frontend/.env 의 VITE_USE_MOCK=true(로컬 데모용)가 apiClient 의 Mock 분기를
// 켜면 fetch 가 호출되지 않으므로, 여기서는 isMockEnabled 를 false 로 고정해
// 실제 네트워크 경로를 타게 한다(앱 코드·.env 는 변경하지 않는다).
vi.mock('./mockApi', async () => {
  const actual = await vi.importActual<typeof import('./mockApi')>('./mockApi')
  return { ...actual, isMockEnabled: () => false }
})
// task 21.1 API 클라이언트 단위 테스트 — fetch 를 모킹하여 3단계 흐름을 검증한다
// (Req 4.1, 4.3, 21.5 / design.md "API 클라이언트").
// 확인 항목:
//  1. POST /uploads → S3 직접 업로드 → POST /search 를 순서대로 호출한다.
//  2. S3 FormData 는 서버가 준 fields 뒤에 파일을 **마지막**으로 append 한다.
//  3. /search 본문에 objectKey 를 보낸다(IP 는 보내지 않는다 — 서버가 읽음).
//  4. 어떤 요청에도 외부 검색 API Key 가 포함되지 않는다(Req 21.5).

interface RecordedCall {
  readonly url: string
  readonly init: RequestInit | undefined
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const PRESIGN = {
  objectKey: 'uploads/11111111-1111-4111-8111-111111111111',
  upload: {
    url: 'https://example-bucket.s3.ap-northeast-2.amazonaws.com/',
    fields: {
      key: 'uploads/11111111-1111-4111-8111-111111111111',
      'Content-Type': 'image/png',
      policy: 'base64-policy-doc',
      'x-amz-signature': 'deadbeef',
    },
  },
  expiresInSeconds: 300,
}

const SEARCH_OK = {
  source: 'MOCK',
  cached: false,
  currencyMixed: false,
  results: [],
}

describe('apiClient 3단계 흐름 (task 21.1)', () => {
  let calls: RecordedCall[]

  beforeEach(() => {
    calls = []
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  function stubFetchSequence(responses: Response[]): void {
    let i = 0
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
        calls.push({ url: String(input), init })
        const res = responses[i] ?? jsonResponse(200, {})
        i += 1
        return res
      },
    )
    vi.stubGlobal('fetch', fetchMock)
  }

  it('runSearch 는 /uploads → S3 → /search 순서로 호출한다', async () => {
    stubFetchSequence([
      jsonResponse(200, PRESIGN),
      new Response(null, { status: 204 }), // S3 는 본문 없는 204 로 성공 응답
      jsonResponse(200, SEARCH_OK),
    ])

    const file = new File([new Uint8Array([1, 2, 3])], 'cropped.png', {
      type: 'image/png',
    })
    const result = await runSearch(file)

    // 호출 순서: /uploads → S3 presigned url → /search
    expect(calls).toHaveLength(3)
    expect(calls[0].url).toMatch(/\/uploads$/)
    expect(calls[1].url).toBe(PRESIGN.upload.url)
    expect(calls[2].url).toMatch(/\/search$/)

    expect(result).toEqual(SEARCH_OK)
  })

  it('S3 업로드 FormData 는 서버 fields 뒤에 파일을 마지막으로 append 한다', async () => {
    stubFetchSequence([new Response(null, { status: 204 })])

    const file = new File([new Uint8Array([9, 9, 9])], 'cropped.png', {
      type: 'image/png',
    })
    await uploadToS3(
      { url: PRESIGN.upload.url, fields: { ...PRESIGN.upload.fields } },
      file,
    )

    const body = calls[0].init?.body
    expect(body).toBeInstanceOf(FormData)
    const form = body as FormData

    // FormData 는 삽입 순서를 보존한다. 키 순서를 확인해 file 이 마지막인지 본다.
    const keys = [...form.keys()]
    expect(keys[keys.length - 1]).toBe('file')
    // 서버가 준 모든 fields 가 file 앞에 존재해야 한다.
    for (const name of Object.keys(PRESIGN.upload.fields)) {
      expect(form.has(name)).toBe(true)
      expect(keys.indexOf(name)).toBeLessThan(keys.indexOf('file'))
    }
    // 업로드되는 파일이 우리가 넘긴 크롭 파일인지 확인.
    expect(form.get('file')).toBe(file)
  })

  it('/search 본문에 objectKey 를 보내고 IP 는 보내지 않는다', async () => {
    stubFetchSequence([jsonResponse(200, SEARCH_OK)])

    await search(PRESIGN.objectKey)

    const sent = JSON.parse(String(calls[0].init?.body)) as Record<string, unknown>
    expect(sent.objectKey).toBe(PRESIGN.objectKey)
    // 클라이언트는 IP 관련 필드를 절대 보내지 않는다(Req 7.8).
    expect(sent).not.toHaveProperty('ip')
    expect(sent).not.toHaveProperty('sourceIp')
  })

  it('어떤 요청에도 외부 검색 API Key 가 포함되지 않는다 (Req 21.5)', async () => {
    stubFetchSequence([
      jsonResponse(200, PRESIGN),
      new Response(null, { status: 204 }),
      jsonResponse(200, SEARCH_OK),
    ])

    const file = new File([new Uint8Array([1])], 'cropped.png', { type: 'image/png' })
    await runSearch(file)

    // 모든 호출의 URL + 헤더 + (문자열) 본문을 한데 모아 Key 흔적이 없는지 확인.
    for (const call of calls) {
      const url = call.url.toLowerCase()
      const headers = JSON.stringify(call.init?.headers ?? {}).toLowerCase()
      const bodyStr =
        typeof call.init?.body === 'string' ? call.init.body.toLowerCase() : ''
      const haystack = `${url} ${headers} ${bodyStr}`
      expect(haystack).not.toContain('api_key')
      expect(haystack).not.toContain('apikey')
      expect(haystack).not.toContain('api-key')
      expect(haystack).not.toContain('serpapi')
      expect(haystack).not.toContain('x-api-key')
      expect(haystack).not.toContain('authorization')
    }
  })

  it('requestUpload 는 contentType 만 본문으로 보낸다', async () => {
    stubFetchSequence([jsonResponse(200, PRESIGN)])

    const res = await requestUpload('image/jpeg')

    const sent = JSON.parse(String(calls[0].init?.body)) as Record<string, unknown>
    expect(sent).toEqual({ contentType: 'image/jpeg' })
    expect(res.objectKey).toBe(PRESIGN.objectKey)
    expect(res.upload.url).toBe(PRESIGN.upload.url)
  })

  it('비 2xx 응답은 백엔드 errorCode 를 담은 ApiError 로 표면화한다', async () => {
    stubFetchSequence([
      jsonResponse(429, { errorCode: 'RATE_LIMITED', message: '한도 초과' }),
    ])

    await expect(search(PRESIGN.objectKey)).rejects.toMatchObject({
      name: 'ApiError',
      errorCode: 'RATE_LIMITED',
      status: 429,
    })
  })

  it('S3 업로드 실패는 UPLOAD_FAILED ApiError 로 표면화한다', async () => {
    stubFetchSequence([new Response('<Error/>', { status: 403 })])

    const file = new File([new Uint8Array([1])], 'cropped.png', { type: 'image/png' })
    await expect(
      uploadToS3(
        { url: PRESIGN.upload.url, fields: { ...PRESIGN.upload.fields } },
        file,
      ),
    ).rejects.toBeInstanceOf(ApiError)
  })
})
