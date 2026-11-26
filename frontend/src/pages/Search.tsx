import { useCallback, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import ConsentGate from '../components/ConsentGate'
import CropTool from '../components/CropTool'
import ErrorNotice from '../components/ErrorNotice'
import ImagePreview from '../components/ImagePreview'
import SearchProgress from '../components/SearchProgress'
import UploadDropzone from '../components/UploadDropzone'
import { ApiError, runSearch } from '../lib/apiClient'
import { validateImageFile } from '../lib/clientFileValidator'
import type { ResultsHandoff } from '../lib/resultsHandoff'
import {
  SEARCH_STAGE,
  type SearchStage,
} from '../lib/searchProgress'

/**
 * VISUAL SEARCH (`/search`) — 핵심 흐름 화면 (Req 18.1).
 *
 * task 20(업로드·크롭·동의)에 이어 task 21 에서 실제 검색 흐름을 끼워 넣었다:
 *   - 21.1 apiClient.runSearch(croppedFile) 로 업로드→S3→검색을 한 번에 구동.
 *   - 21.2 SearchProgress 상태 머신(lib/searchProgress.ts)으로 진행 스테이지를
 *     UPLOADING IMAGE → SEARCHING MARKETPLACES → MATCHING PRODUCTS → RESULTS
 *     READY 순서로 표시하고(Req 13.1), 성공 시 RESULTS 화면으로 전환한다(Req 13.2).
 *
 * [스테이지 구동 방식 — 정직한 매핑]
 * apiClient.runSearch 는 내부에서 requestUpload→uploadToS3→search 를 순서대로
 * await 하는 단일 호출이라, 프론트에서 각 내부 단계 경계를 관측할 수 없다.
 * 따라서 호출을 "await 구간을 둘러싼 명시적 스테이지 전이"로 표현한다:
 *   1) 호출 직전 UPLOADING IMAGE 로 세팅(업로드 발급+S3 직접 업로드 구간)
 *   2) 한 프레임 뒤 SEARCHING MARKETPLACES(서버가 SerpApi 호출 수행)
 *   3) 응답 수신 직후 MATCHING PRODUCTS(정규화 완료 표시) → 곧바로 RESULTS READY
 *   4) RESULTS READY 가 되면 navigate('/results', { state }) 로 전환
 * 이 매핑은 lib/searchProgress.ts 의 stageForApiStep 주석과 일치한다.
 */
function Search() {
  const navigate = useNavigate()
  // 선택된 '원본' 이미지 한 장을 보관한다(브라우저 내 크롭용). 이 값은 크롭
  // 입력으로만 쓰이며, 업로드/검색(20.5·21)으로는 절대 전달하지 않는다(Req 2.4).
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  // task 20.4: 크롭 확정 결과 File. 이후 동의·검색 단계로 흘러가는 유일한
  // 업로드 대상이다(Req 2.3). 원본(selectedFile)은 여기로 오지 않는다.
  const [croppedFile, setCroppedFile] = useState<File | null>(null)
  // task 20.2: 검증 실패 시 보여줄 거부 메시지 (Req 1.4, 1.5).
  const [rejectionMessage, setRejectionMessage] = useState<string | null>(null)
  // task 20.5: 외부 전송 동의 상태. 동의 전에는 검색 시작을 막는다(Req 3.2).
  const [consented, setConsented] = useState(false)
  // task 21.2: 현재 진행 스테이지. null 이면 아직 검색을 시작하지 않은 상태로,
  // 이때만 업로드/크롭/동의 UI 를 보여준다. 검색이 시작되면 SearchProgress 를
  // 보여주고, 성공 시 RESULTS 로 전환한다(Req 13.1, 13.2).
  const [stage, setStage] = useState<SearchStage | null>(null)
  // task 21.2 → 22.10 플러그인 지점: ApiError 발생 시 crash 없이 errorCode 를
  // 보존한다. 지금은 여기 자리표시 안내만 띄우고, 코드는 RESULTS 로 넘겨
  // 22.10 ErrorNotice 가 한국어 메시지로 렌더하도록 한다(Req 17.x).
  const [errorCode, setErrorCode] = useState<string | null>(null)

  // task 20.2: 이미지 선택 시 클라이언트 검증을 돌린다. 실패하면 거부 메시지를
  // 표시하고 미리보기/선택을 설정하지 않아 이후 단계(크롭·동의·검색)로 넘어가지
  // 않도록 막는다. 성공하면 거부 메시지를 지우고 선택을 반영한다.
  const handleImageSelected = useCallback((file: File) => {
    const result = validateImageFile(file)
    if (!result.ok) {
      setSelectedFile(null)
      setCroppedFile(null)
      setRejectionMessage(result.message)
      return
    }
    setRejectionMessage(null)
    // 새 원본을 고르면 이전 크롭 결과·동의·진행/오류 상태를 모두 무효화한다.
    setCroppedFile(null)
    setConsented(false)
    setStage(null)
    setErrorCode(null)
    setSelectedFile(file)
  }, [])

  // task 20.4: 크롭 확정. CropTool 이 만든 '크롭 결과' File 만 받아 보관한다.
  // 이 File 이 20.5(동의)·21(업로드/검색)로 넘어갈 유일한 대상이며, 원본은
  // 서버로 전송되지 않는다(Req 2.3, 2.4).
  const handleCropComplete = useCallback((cropped: File) => {
    // 새 크롭 결과는 새 업로드 대상이므로 이전 동의·진행/오류를 무효화해 다시 받는다.
    setConsented(false)
    setStage(null)
    setErrorCode(null)
    setCroppedFile(cropped)
  }, [])

  // 선택을 초기화한다(원본·크롭 결과·동의·진행/오류 모두 비움).
  const handleClear = useCallback(() => {
    setSelectedFile(null)
    setCroppedFile(null)
    setConsented(false)
    setStage(null)
    setErrorCode(null)
  }, [])

  // task 20.5 → 21: 동의 후 검색 시작. 21.1 apiClient.runSearch 로 흐름을 구동하고
  // 21.2 SearchProgress 로 스테이지를 전이시킨다(Req 3.3, 13.1, 13.2).
  //
  // runSearch 는 단일 await 호출이므로, await 를 둘러싸고 명시적으로 스테이지를
  // 전이한다(정직한 매핑, 위 컴포넌트 주석 참고). 성공하면 RESULTS READY 로 넘긴
  // 뒤 navigate('/results', { state }) 로 결과를 넘겨 전환한다(Req 13.2). ApiError
  // 는 crash 없이 errorCode 를 보존해 RESULTS 의 22.10 ErrorNotice 로 넘긴다.
  const handleStartSearch = useCallback(() => {
    if (croppedFile === null) return

    // 1) 업로드 스테이지로 진입(발급 + S3 직접 업로드 구간).
    setErrorCode(null)
    setStage(SEARCH_STAGE.UploadingImage)

    void (async () => {
      try {
        // 2) 서버 검색 호출 직전: 마켓플레이스 검색 스테이지.
        //    (runSearch 내부에서 업로드가 먼저 끝난 뒤 search 가 실행된다.)
        setStage(SEARCH_STAGE.SearchingMarketplaces)
        const response = await runSearch(croppedFile)

        // 3) 응답 수신 → 정규화 완료 표시(상품 매칭) → 결과 준비 완료.
        setStage(SEARCH_STAGE.MatchingProducts)
        setStage(SEARCH_STAGE.ResultsReady)

        // 4) RESULTS READY: 결과를 라우터 state 로 넘겨 RESULTS 화면으로 전환.
        const handoff: ResultsHandoff = {
          kind: 'success',
          source: response.source,
          cached: response.cached,
          currencyMixed: response.currencyMixed,
          results: response.results,
        }
        navigate('/results', { state: handoff })
      } catch (err) {
        // ApiError 는 안정적 errorCode 를 보존한다(그 외 예외는 INTERNAL_ERROR).
        const code = err instanceof ApiError ? err.errorCode : 'INTERNAL_ERROR'
        setStage(null)
        setErrorCode(code)
      }
    })()
  }, [croppedFile, navigate])

  return (
    <section className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-4xl font-bold tracking-tightest md:text-6xl">
          Visual Search
        </h1>
        <p className="max-w-xl text-sm text-text/60 md:text-base">
          이미지를 업로드하고 크롭한 뒤 외부 전송에 동의하면 검색이 시작됩니다.
        </p>
      </header>

      {/*
        task 21.2: 검색이 시작되면(stage !== null) 진행 상태 화면으로 전환한다.
        성공 시 RESULTS 로 navigate 하므로, 이 화면에 머무는 동안은 UPLOADING
        IMAGE → SEARCHING MARKETPLACES → MATCHING PRODUCTS → RESULTS READY 를
        순서대로 보여준다(Req 13.1). 진행 중에는 아래 업로드/크롭/동의 UI 를
        감춰 재입력을 막는다.
      */}
      {stage !== null ? (
        <SearchProgress stage={stage} />
      ) : (
      <div
        data-testid="visual-search-flow"
        className="flex flex-col gap-6"
      >
        {/*
          플러그인 지점:
          - task 20.1 UploadDropzone / ImagePreview ← 연결됨
          - task 20.2 ClientFileValidator ← 연결됨
          - task 20.4 CropTool ← 연결됨
          - task 20.5 ConsentGate ← 연결됨
          - task 21.1 API 클라이언트 / 21.2 SearchProgress ← handleStartSearch 에 연결됨
        */}

        {/*
          task 22.10: ApiError 발생 시 crash 없이 여기에 코드별 한국어 메시지를
          렌더한다(Req 17.x). RESULTS 의 error 분기와 동일하게 ErrorNotice 를
          거치므로 NO_RESULTS 등 각 코드의 문구가 양쪽에서 일관된다. 검색 화면에
          머물러 있으므로(stage===null) 아래 업로드/크롭/동의 UI 로 곧바로 재시도할
          수 있다.
        */}
        {errorCode ? <ErrorNotice errorCode={errorCode} /> : null}

        {/* task 20.1 + 20.2: 이미지 선택 → 클라이언트 검증 게이트 */}
        <UploadDropzone onImageSelected={handleImageSelected} />

        {/* task 20.2: 검증 실패 거부 메시지 (Req 1.4 형식 / 1.5 크기) */}
        {rejectionMessage ? (
          <p
            data-testid="file-rejection-message"
            role="alert"
            className="border border-accent/60 bg-surface/40 px-4 py-3 text-sm text-accent"
          >
            {rejectionMessage}
          </p>
        ) : null}

        {/* task 20.1: 선택된 이미지 미리보기 (Req 1.3) — 검증 통과 시에만 표시 */}
        {selectedFile ? (
          <ImagePreview file={selectedFile} onClear={handleClear} />
        ) : null}

        {/*
          task 20.4: CropTool — 선택·검증된 '원본'을 입력으로 받아 브라우저에서
          크롭하고(Req 2.1, 2.2), 확정 시 '크롭 결과' File 만 올려 보낸다(Req 2.3).
          원본(selectedFile)은 CropTool 의 입력일 뿐 아래 동의·검색 단계로는
          넘어가지 않는다 — 오직 croppedFile 만 전달된다(Req 2.4).
        */}
        {selectedFile ? (
          <CropTool file={selectedFile} onCropComplete={handleCropComplete} />
        ) : null}

        {/*
          task 20.5 ConsentGate — 유효한 크롭 결과가 생긴 뒤에만 나타난다(Req 3.1).
          외부 전송 안내와 Consent_Checkbox 를 표시하고, 동의 전에는 검색 시작을
          비활성화한다(Req 3.2). 검색 시작 가능 조건은 "동의됨 AND 크롭 결과 준비됨"
          이다 — 아래로 흘러가는 업로드 대상은 croppedFile 뿐이며 원본 selectedFile
          은 절대 업로드 경로로 전달하지 않는다(Req 2.4).

          task 21.1 / 21.2 API 클라이언트 · SearchProgress 플러그인 지점은
          handleStartSearch 안이다(동의 후 검색 시작, Req 3.3).
        */}
        {croppedFile ? (
          <ConsentGate
            consented={consented}
            onConsentChange={setConsented}
            hasCroppedFile={croppedFile !== null}
            onStartSearch={handleStartSearch}
          />
        ) : null}
      </div>
      )}
    </section>
  )
}

export default Search
