import { useEffect, useState } from 'react'

/**
 * ImagePreview — 선택된 이미지 미리보기 표시 (Req 1.3).
 *
 * 선택된 `File`을 받아 object URL 로 미리보기를 렌더한다.
 * 파일이 바뀌거나 언마운트될 때 이전 object URL 을 반드시 revoke 하여
 * 메모리 누수를 막는다. 검증/크롭/동의는 여기서 다루지 않는다(각각 20.2/20.4/20.5).
 */
interface ImagePreviewProps {
  /** 미리보기로 표시할 선택된 이미지 파일 */
  readonly file: File
  /** 미리보기 제거(선택 취소) 요청 콜백 */
  readonly onClear?: () => void
}

function ImagePreview({ file, onClear }: ImagePreviewProps) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null)

  useEffect(() => {
    // 파일마다 새 object URL 을 만들고, cleanup 에서 반드시 해제한다(누수 방지).
    const url = URL.createObjectURL(file)
    setObjectUrl(url)
    return () => {
      URL.revokeObjectURL(url)
    }
  }, [file])

  return (
    <figure
      data-testid="image-preview"
      className="flex flex-col gap-3 border border-surface bg-surface/40 p-4"
    >
      <div className="flex items-center justify-center overflow-hidden bg-background">
        {objectUrl ? (
          <img
            src={objectUrl}
            alt={file.name || '선택된 이미지 미리보기'}
            className="max-h-80 w-auto object-contain"
          />
        ) : null}
      </div>

      <figcaption className="flex items-center justify-between gap-4 text-xs uppercase tracking-tightest text-text/50">
        <span className="truncate" title={file.name}>
          {file.name || 'IMAGE'}
        </span>
        {onClear ? (
          <button
            type="button"
            onClick={onClear}
            className="shrink-0 border border-surface px-3 py-1 font-bold text-text/70 transition-colors duration-300 ease-editorial hover:border-accent hover:text-accent"
          >
            Change
          </button>
        ) : null}
      </figcaption>
    </figure>
  )
}

export default ImagePreview
export type { ImagePreviewProps }
