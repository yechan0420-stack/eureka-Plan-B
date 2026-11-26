import { useCallback, useState } from 'react'
import CropTool from '../components/CropTool'
import ImagePreview from '../components/ImagePreview'
import UploadDropzone from '../components/UploadDropzone'
import { validateImageFile } from '../lib/clientFileValidator'

/**
 * VISUAL SEARCH (`/search`) — 핵심 흐름 화면 (Req 18.1).
 * 미리보기·크롭·동의·검색 시작·진행 상태(task 20, 21)는 이후 작업에서
 * 이 자리에 끼워 넣는다. task 20.1 은 이미지 선택(UploadDropzone)과
 * 미리보기(ImagePreview)를, task 20.2 는 형식·크기 클라이언트 검증을 연결한다.
 */
function Search() {
  // 선택된 '원본' 이미지 한 장을 보관한다(브라우저 내 크롭용). 이 값은 크롭
  // 입력으로만 쓰이며, 업로드/검색(20.5·21)으로는 절대 전달하지 않는다(Req 2.4).
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  // task 20.4: 크롭 확정 결과 File. 이후 동의·검색 단계로 흘러가는 유일한
  // 업로드 대상이다(Req 2.3). 원본(selectedFile)은 여기로 오지 않는다.
  const [croppedFile, setCroppedFile] = useState<File | null>(null)
  // task 20.2: 검증 실패 시 보여줄 거부 메시지 (Req 1.4, 1.5).
  const [rejectionMessage, setRejectionMessage] = useState<string | null>(null)

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
    // 새 원본을 고르면 이전 크롭 결과는 무효화한다.
    setCroppedFile(null)
    setSelectedFile(file)
  }, [])

  // task 20.4: 크롭 확정. CropTool 이 만든 '크롭 결과' File 만 받아 보관한다.
  // 이 File 이 20.5(동의)·21(업로드/검색)로 넘어갈 유일한 대상이며, 원본은
  // 서버로 전송되지 않는다(Req 2.3, 2.4).
  const handleCropComplete = useCallback((cropped: File) => {
    setCroppedFile(cropped)
  }, [])

  // 선택을 초기화한다(원본·크롭 결과 모두 비움).
  const handleClear = useCallback(() => {
    setSelectedFile(null)
    setCroppedFile(null)
  }, [])

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

      <div
        data-testid="visual-search-flow"
        className="flex flex-col gap-6"
      >
        {/*
          플러그인 지점 (이후 작업):
          - task 20.1 UploadDropzone / ImagePreview ← 연결됨
          - task 20.2 ClientFileValidator ← 연결됨
          - task 20.4 CropTool ← 이번 작업에서 연결
          - task 20.5 ConsentGate
          - task 21.1 API 클라이언트 / 21.2 SearchProgress
        */}

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
          task 20.5 ConsentGate 플러그인 지점
          task 21.1 / 21.2 API 클라이언트 · SearchProgress 플러그인 지점

          ↓ 아래 단계로 흘러가는 업로드 대상은 croppedFile(크롭 결과)뿐이다.
            원본 selectedFile 은 절대 업로드 경로로 전달하지 않는다(Req 2.4).
            (ConsentGate/검색 시작이 붙기 전까지 크롭 완료 상태만 표시한다.)
        */}
        {croppedFile ? (
          <p
            data-testid="crop-complete-notice"
            className="border border-accent/40 bg-surface/40 px-4 py-3 text-sm text-text/70"
          >
            크롭이 완료되었습니다. 외부 전송 동의 후 검색을 시작할 수 있습니다.
          </p>
        ) : null}
      </div>
    </section>
  )
}

export default Search
