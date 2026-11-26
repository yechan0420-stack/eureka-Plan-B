import { useCallback, useEffect, useRef, useState } from 'react'
import {
  type CropRect,
  clampCropRect,
  cropToFile,
  croppedFileName,
} from '../lib/cropImage'

/**
 * CropTool — 브라우저 내 canvas 기반 크롭 도구 (Req 2.1~2.4, design.md CropTool).
 *
 * 선택·검증된 원본 `File` 을 받아 화면에 그리고, 사용자가 드래그로 옷 영역
 * 사각형을 지정하면(Req 2.1) 그 영역만 떼어 크롭 결과 `File` 을 만든다. 크롭은
 * 전적으로 브라우저에서 수행된다(Req 2.2). "크롭 확정" 시 `onCropComplete` 로
 * 크롭 결과 File 하나만 올려 보내며(Req 2.3), 원본 File 은 이 콜백으로도,
 * 다른 어떤 경로로도 상위에 전달하지 않는다 — 원본은 브라우저를 떠나지
 * 않는다(Req 2.4). 좌표 계산·캔버스 렌더·Blob 변환 로직은 `lib/cropImage.ts`
 * 로 분리해 테스트 가능하게 두었다.
 */
interface CropToolProps {
  /** 크롭할 원본 이미지 파일(선택·검증 완료). 서버로 전송되지 않는다. */
  readonly file: File
  /** 크롭 확정 시 호출. 인자는 '크롭 결과' File 뿐이다(원본 아님). */
  readonly onCropComplete: (croppedFile: File) => void
  /** 크롭 도구를 비활성화한다(예: 검색 진행 중). */
  readonly disabled?: boolean
}

interface DragState {
  readonly startX: number
  readonly startY: number
}

function CropTool({ file, onCropComplete, disabled = false }: CropToolProps) {
  const imgRef = useRef<HTMLImageElement | null>(null)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [objectUrl, setObjectUrl] = useState<string | null>(null)
  const [imageReady, setImageReady] = useState(false)
  const [rect, setRect] = useState<CropRect | null>(null)
  const [drag, setDrag] = useState<DragState | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // 원본 File 로 미리보기 object URL 을 만들고, 언마운트/파일 교체 시 revoke.
  // object URL 은 브라우저 로컬 참조일 뿐 서버로 나가지 않는다(Req 2.4).
  useEffect(() => {
    const url = URL.createObjectURL(file)
    setObjectUrl(url)
    setImageReady(false)
    setRect(null)
    setDrag(null)
    setError(null)
    return () => {
      URL.revokeObjectURL(url)
    }
  }, [file])

  // 포인터 좌표를 이미지 표시 좌표계(좌상단 기준)로 변환한다.
  const toLocalPoint = useCallback((clientX: number, clientY: number) => {
    const el = imgRef.current
    if (!el) return { x: 0, y: 0 }
    const bounds = el.getBoundingClientRect()
    return {
      x: clamp(clientX - bounds.left, 0, bounds.width),
      y: clamp(clientY - bounds.top, 0, bounds.height),
    }
  }, [])

  const handlePointerDown = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      if (disabled || !imageReady) return
      event.preventDefault()
      const { x, y } = toLocalPoint(event.clientX, event.clientY)
      setDrag({ startX: x, startY: y })
      setRect({ x, y, width: 0, height: 0 })
      setError(null)
      event.currentTarget.setPointerCapture?.(event.pointerId)
    },
    [disabled, imageReady, toLocalPoint],
  )

  const handlePointerMove = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      if (!drag || disabled) return
      const { x, y } = toLocalPoint(event.clientX, event.clientY)
      setRect({
        x: drag.startX,
        y: drag.startY,
        width: x - drag.startX,
        height: y - drag.startY,
      })
    },
    [drag, disabled, toLocalPoint],
  )

  const endDrag = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      if (!drag) return
      setDrag(null)
      const el = imgRef.current
      if (el && rect) {
        // 드래그가 끝나면 사각형을 이미지 경계 안으로 보정해 둔다.
        const bounds = el.getBoundingClientRect()
        setRect(clampCropRect(rect, bounds.width, bounds.height))
      }
      event.currentTarget.releasePointerCapture?.(event.pointerId)
    },
    [drag, rect],
  )

  // 크롭 확정: 크롭 결과 File 만 생성해 상위로 올린다(Req 2.3). 원본은 전달 안 함.
  const handleConfirm = useCallback(async () => {
    const img = imgRef.current
    if (disabled || busy || !img || !rect) return
    const bounds = img.getBoundingClientRect()
    setBusy(true)
    setError(null)
    try {
      const croppedFile = await cropToFile(
        img,
        {
          naturalWidth: img.naturalWidth,
          naturalHeight: img.naturalHeight,
          displayWidth: bounds.width,
          displayHeight: bounds.height,
        },
        rect,
        croppedFileName(file.name),
      )
      // onCropComplete 에 넘기는 것은 오직 크롭 결과 File 이다(원본 file 아님).
      onCropComplete(croppedFile)
    } catch (err) {
      setError(err instanceof Error ? err.message : '크롭에 실패했습니다.')
    } finally {
      setBusy(false)
    }
  }, [disabled, busy, rect, file.name, onCropComplete])

  const handleReset = useCallback(() => {
    setRect(null)
    setDrag(null)
    setError(null)
  }, [])

  const hasSelection = rect !== null && Math.abs(rect.width) >= 1 && Math.abs(rect.height) >= 1

  return (
    <section
      data-testid="crop-tool"
      className="flex flex-col gap-3 border border-surface bg-surface/40 p-4"
    >
      <header className="flex items-center justify-between gap-4">
        <h2 className="text-xs font-bold uppercase tracking-tightest text-text/70">
          Crop · 옷 영역 선택
        </h2>
        <span className="text-[0.65rem] uppercase tracking-tightest text-text/40">
          원본은 전송되지 않습니다
        </span>
      </header>

      {/* 크롭 캔버스 영역: 이미지 위에 드래그로 사각형을 그린다 (Req 2.1) */}
      <div
        ref={containerRef}
        data-testid="crop-surface"
        className="relative inline-flex select-none items-center justify-center overflow-hidden bg-background"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        style={{ touchAction: 'none', cursor: disabled ? 'not-allowed' : 'crosshair' }}
      >
        {objectUrl ? (
          <img
            ref={imgRef}
            src={objectUrl}
            alt={file.name || '크롭할 이미지'}
            draggable={false}
            onLoad={() => setImageReady(true)}
            className="pointer-events-none max-h-80 w-auto object-contain"
          />
        ) : null}

        {/* 선택 사각형 오버레이 */}
        {rect && hasSelection ? (
          <div
            data-testid="crop-selection"
            className="pointer-events-none absolute border border-accent bg-accent/10"
            style={normalizedBoxStyle(rect)}
          />
        ) : null}
      </div>

      {error ? (
        <p
          data-testid="crop-error"
          role="alert"
          className="text-xs text-accent"
        >
          {error}
        </p>
      ) : (
        <p className="text-xs text-text/40">
          이미지 위에서 드래그하여 옷 영역을 지정한 뒤 크롭을 확정하세요.
        </p>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          data-testid="crop-confirm"
          disabled={disabled || busy || !hasSelection}
          onClick={handleConfirm}
          className="border border-accent px-5 py-2 text-xs font-bold uppercase tracking-tightest text-accent transition-colors duration-300 ease-editorial hover:bg-accent hover:text-background disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? 'Cropping…' : 'Crop'}
        </button>
        <button
          type="button"
          data-testid="crop-reset"
          disabled={disabled || busy || !hasSelection}
          onClick={handleReset}
          className="border border-surface px-5 py-2 text-xs font-bold uppercase tracking-tightest text-text/70 transition-colors duration-300 ease-editorial hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-40"
        >
          Reset
        </button>
      </div>
    </section>
  )
}

/** 음수 width/height(반대 방향 드래그)를 CSS 박스 좌표로 정규화한다. */
function normalizedBoxStyle(rect: CropRect): React.CSSProperties {
  const left = rect.width < 0 ? rect.x + rect.width : rect.x
  const top = rect.height < 0 ? rect.y + rect.height : rect.y
  return {
    left: `${left}px`,
    top: `${top}px`,
    width: `${Math.abs(rect.width)}px`,
    height: `${Math.abs(rect.height)}px`,
  }
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

export default CropTool
export type { CropToolProps }
