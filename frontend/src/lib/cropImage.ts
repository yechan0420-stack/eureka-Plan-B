/**
 * cropImage — 브라우저 내 크롭의 순수/분리 가능한 로직 (Req 2.1~2.4,
 * design.md CropTool "크롭 결과만 업로드", 원본 서버 미전송).
 *
 * 크롭은 전적으로 브라우저에서 canvas 로 수행하며(Req 2.2), 결과물인
 * 크롭된 이미지 `File` 하나만 생성한다. 원본 `File`/`Blob` 은 여기서 만들지
 * 않으며, 이후 업로드 단계로 흘려보내지도 않는다(Req 2.4). 호출부는 이 모듈이
 * 돌려준 크롭 결과만 업로드 대상으로 사용해야 한다(Req 2.3).
 *
 * 사각형 선택 → 크롭 캔버스 → Blob/File 로 이어지는 로직을 React/DOM 이벤트와
 * 분리해 두어, 좌표 정규화(clampCropRect)는 환경 의존 없이 단위 테스트할 수
 * 있고, 캔버스 렌더(drawCroppedCanvas)·Blob 변환(canvasToFile)은 canvas 를
 * 쓸 수 있는 환경에서만 동작한다.
 */

/** 이미지(표시) 좌표계에서의 크롭 사각형. 픽셀 단위. */
export interface CropRect {
  readonly x: number
  readonly y: number
  readonly width: number
  readonly height: number
}

/** 크롭 대상 이미지의 자연(원본) 크기와 화면 표시 크기. */
export interface CropSourceSize {
  /** 이미지 원본 픽셀 너비 (naturalWidth). */
  readonly naturalWidth: number
  /** 이미지 원본 픽셀 높이 (naturalHeight). */
  readonly naturalHeight: number
  /** 화면에 표시된 너비 (CSS 픽셀). */
  readonly displayWidth: number
  /** 화면에 표시된 높이 (CSS 픽셀). */
  readonly displayHeight: number
}

/** 크롭 결과 파일 생성 시 사용할 출력 형식 기본값. */
export const DEFAULT_CROP_MIME_TYPE = 'image/png'
export const DEFAULT_CROP_QUALITY = 0.92

/**
 * 표시 좌표계의 크롭 사각형을 이미지 경계 안으로 보정한다.
 *
 * - 음수 width/height(반대 방향 드래그)는 정방향으로 정규화한다.
 * - 이미지 바깥으로 나간 부분은 잘라 경계 안에 들어오게 한다.
 * - 결과 width/height 는 음수가 되지 않는다.
 */
export function clampCropRect(
  rect: CropRect,
  displayWidth: number,
  displayHeight: number,
): CropRect {
  // 반대 방향 드래그를 정방향(좌상단 기준 +width/+height)으로 정규화.
  const rawX = rect.width < 0 ? rect.x + rect.width : rect.x
  const rawY = rect.height < 0 ? rect.y + rect.height : rect.y
  const rawW = Math.abs(rect.width)
  const rawH = Math.abs(rect.height)

  const x = clamp(rawX, 0, displayWidth)
  const y = clamp(rawY, 0, displayHeight)
  // 선택 사각형의 우/하단 끝도 경계 안으로 보정한 뒤 너비/높이를 구한다.
  const right = clamp(rawX + rawW, 0, displayWidth)
  const bottom = clamp(rawY + rawH, 0, displayHeight)

  return {
    x,
    y,
    width: Math.max(0, right - x),
    height: Math.max(0, bottom - y),
  }
}

/**
 * 표시 좌표계의 크롭 사각형을 이미지 원본 픽셀 좌표계로 변환한다.
 * 표시 크기와 원본 크기의 비율로 스케일링한다.
 */
export function toSourceRect(rect: CropRect, size: CropSourceSize): CropRect {
  const scaleX =
    size.displayWidth > 0 ? size.naturalWidth / size.displayWidth : 1
  const scaleY =
    size.displayHeight > 0 ? size.naturalHeight / size.displayHeight : 1
  return {
    x: Math.round(rect.x * scaleX),
    y: Math.round(rect.y * scaleY),
    width: Math.round(rect.width * scaleX),
    height: Math.round(rect.height * scaleY),
  }
}

/** 크롭 사각형이 실제로 유효한 영역(양수 면적)을 가지는지. */
export function isValidCropRect(rect: CropRect): boolean {
  return rect.width >= 1 && rect.height >= 1
}

/**
 * 원본 이미지의 지정 영역만 떼어 새 canvas 에 그린다. 원본 전체가 아니라
 * 크롭 영역만 그려지므로, 이후 toBlob 결과에는 크롭 영역만 담긴다(Req 2.3).
 *
 * 캔버스 2D 컨텍스트를 얻을 수 없으면 null 을 돌려준다.
 */
export function drawCroppedCanvas(
  image: CanvasImageSource,
  sourceRect: CropRect,
): HTMLCanvasElement | null {
  const canvas = document.createElement('canvas')
  canvas.width = Math.max(1, sourceRect.width)
  canvas.height = Math.max(1, sourceRect.height)
  const ctx = canvas.getContext('2d')
  if (!ctx) return null
  ctx.drawImage(
    image,
    sourceRect.x,
    sourceRect.y,
    sourceRect.width,
    sourceRect.height,
    0,
    0,
    sourceRect.width,
    sourceRect.height,
  )
  return canvas
}

/**
 * canvas 를 크롭 결과 `File` 로 변환한다. `canvas.toBlob` 로 만든 Blob 만을
 * 업로드 대상 File 로 승격시킨다 — 원본 File 은 관여하지 않는다(Req 2.3, 2.4).
 */
export function canvasToFile(
  canvas: HTMLCanvasElement,
  fileName: string,
  mimeType: string = DEFAULT_CROP_MIME_TYPE,
  quality: number = DEFAULT_CROP_QUALITY,
): Promise<File> {
  return new Promise<File>((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          reject(new Error('크롭 결과 이미지를 생성하지 못했습니다.'))
          return
        }
        resolve(
          new File([blob], fileName, {
            type: blob.type || mimeType,
            lastModified: Date.now(),
          }),
        )
      },
      mimeType,
      quality,
    )
  })
}

/**
 * 표시 좌표계 사각형 + 이미지 크기 → 크롭된 결과 File.
 *
 * 전 과정을 브라우저에서 수행하며(Req 2.2), 반환하는 유일한 산출물은 크롭된
 * 이미지 File 이다. 원본 File 은 입력으로도 받지 않으므로 이 경로로 원본이
 * 서버로 흘러갈 수 없다(Req 2.4).
 */
export async function cropToFile(
  image: CanvasImageSource,
  size: CropSourceSize,
  displayRect: CropRect,
  fileName: string,
  mimeType: string = DEFAULT_CROP_MIME_TYPE,
  quality: number = DEFAULT_CROP_QUALITY,
): Promise<File> {
  const clamped = clampCropRect(displayRect, size.displayWidth, size.displayHeight)
  if (!isValidCropRect(clamped)) {
    throw new Error('크롭 영역을 지정해 주세요.')
  }
  const sourceRect = toSourceRect(clamped, size)
  if (!isValidCropRect(sourceRect)) {
    throw new Error('크롭 영역이 너무 작습니다.')
  }
  const canvas = drawCroppedCanvas(image, sourceRect)
  if (!canvas) {
    throw new Error('브라우저 크롭을 사용할 수 없습니다.')
  }
  return canvasToFile(canvas, fileName, mimeType, quality)
}

/** 크롭 결과 파일 이름을 생성한다(원본 파일명 기반, 확장자만 교체). */
export function croppedFileName(
  originalName: string,
  mimeType: string = DEFAULT_CROP_MIME_TYPE,
): string {
  const ext = mimeType === 'image/jpeg' ? 'jpg' : mimeType === 'image/webp' ? 'webp' : 'png'
  const base = originalName.replace(/\.[^./\\]+$/, '') || 'image'
  return `${base}-cropped.${ext}`
}

function clamp(value: number, min: number, max: number): number {
  if (Number.isNaN(value)) return min
  return Math.min(Math.max(value, min), max)
}
