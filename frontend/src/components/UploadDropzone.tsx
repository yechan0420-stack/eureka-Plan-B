import { useCallback, useId, useRef, useState } from 'react'

/**
 * UploadDropzone — 드래그앤드롭 영역 + 파일 선택 버튼 (Req 1.1),
 * 모바일 카메라(`capture`) 촬영 및 앨범/갤러리 선택 입력 (Req 1.2).
 *
 * 책임은 "이미지 선택"까지로 한정한다. 선택이 끝나면 `onImageSelected(file)`
 * 콜백으로 선택된 `File` 하나를 상위에 올려 보내고, 이후 작업(형식·크기 검증 20.2,
 * 크롭 20.4, 동의 20.5)이 이 콜백에 끼어든다. 여기서는 검증을 하지 않는다.
 */
interface UploadDropzoneProps {
  /** 사용자가 파일을 드롭/선택/촬영했을 때 호출되는 콜백 */
  readonly onImageSelected: (file: File) => void
  /** 드롭존을 비활성화한다(예: 검색 진행 중) */
  readonly disabled?: boolean
}

function UploadDropzone({ onImageSelected, disabled = false }: UploadDropzoneProps) {
  const [isDragOver, setIsDragOver] = useState(false)
  // 파일 선택 버튼이 눌렀을 때 열 숨겨진 입력들에 대한 참조.
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const cameraInputRef = useRef<HTMLInputElement | null>(null)
  const galleryInputRef = useRef<HTMLInputElement | null>(null)
  const fileInputId = useId()

  // 입력/드롭 어느 경로든 첫 번째 파일만 상위로 올린다.
  const emitFirstFile = useCallback(
    (files: FileList | null | undefined) => {
      if (disabled) return
      const file = files?.[0]
      if (file) {
        onImageSelected(file)
      }
    },
    [disabled, onImageSelected],
  )

  const handleDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault()
      setIsDragOver(false)
      if (disabled) return
      emitFirstFile(event.dataTransfer?.files)
    },
    [disabled, emitFirstFile],
  )

  const handleDragOver = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault()
      if (!disabled) setIsDragOver(true)
    },
    [disabled],
  )

  const handleDragLeave = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault()
      setIsDragOver(false)
    },
    [],
  )

  // 같은 파일을 다시 선택해도 change 가 발생하도록 value 를 비운다.
  const handleInputChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      emitFirstFile(event.target.files)
      event.target.value = ''
    },
    [emitFirstFile],
  )

  return (
    <div className="flex flex-col gap-3">
      {/* 드래그앤드롭 영역 (Req 1.1) */}
      <div
        data-testid="upload-dropzone"
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-disabled={disabled}
        aria-label="이미지 드래그앤드롭 또는 파일 선택"
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => {
          if (!disabled) fileInputRef.current?.click()
        }}
        onKeyDown={(event) => {
          if (disabled) return
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            fileInputRef.current?.click()
          }
        }}
        className={[
          'flex min-h-[16rem] flex-col items-center justify-center gap-4 border border-dashed p-8 text-center transition-colors duration-300 ease-editorial',
          disabled
            ? 'cursor-not-allowed border-surface text-text/30'
            : 'cursor-pointer text-text/60 hover:border-accent hover:text-text',
          isDragOver ? 'border-accent text-text' : 'border-surface',
        ].join(' ')}
      >
        <p className="text-sm font-bold uppercase tracking-tightest md:text-base">
          Drop Image Here
        </p>
        <p className="text-xs uppercase tracking-tightest text-text/40">
          JPG · PNG · WEBP
        </p>

        <div className="flex flex-wrap items-center justify-center gap-3">
          {/* 파일 선택 버튼 (Req 1.1) */}
          <button
            type="button"
            disabled={disabled}
            onClick={(event) => {
              event.stopPropagation()
              fileInputRef.current?.click()
            }}
            className="border border-accent px-5 py-3 text-xs font-bold uppercase tracking-tightest text-accent transition-colors duration-300 ease-editorial hover:bg-accent hover:text-background disabled:cursor-not-allowed disabled:opacity-40"
          >
            Select File
          </button>

          {/* 모바일 앨범/갤러리 선택 (Req 1.2) */}
          <button
            type="button"
            disabled={disabled}
            onClick={(event) => {
              event.stopPropagation()
              galleryInputRef.current?.click()
            }}
            className="border border-surface px-5 py-3 text-xs font-bold uppercase tracking-tightest text-text/70 transition-colors duration-300 ease-editorial hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-40"
          >
            Album
          </button>

          {/* 모바일 카메라 촬영 (Req 1.2) */}
          <button
            type="button"
            disabled={disabled}
            onClick={(event) => {
              event.stopPropagation()
              cameraInputRef.current?.click()
            }}
            className="border border-surface px-5 py-3 text-xs font-bold uppercase tracking-tightest text-text/70 transition-colors duration-300 ease-editorial hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-40"
          >
            Camera
          </button>
        </div>
      </div>

      {/* 숨겨진 입력들: 기본 파일 선택 / 앨범 / 카메라(capture) */}
      <input
        ref={fileInputRef}
        id={fileInputId}
        data-testid="upload-input-file"
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="sr-only"
        onChange={handleInputChange}
        disabled={disabled}
      />
      <input
        ref={galleryInputRef}
        data-testid="upload-input-gallery"
        type="file"
        accept="image/*"
        className="sr-only"
        onChange={handleInputChange}
        disabled={disabled}
      />
      <input
        ref={cameraInputRef}
        data-testid="upload-input-camera"
        type="file"
        accept="image/*"
        capture="environment"
        className="sr-only"
        onChange={handleInputChange}
        disabled={disabled}
      />
    </div>
  )
}

export default UploadDropzone
export type { UploadDropzoneProps }
