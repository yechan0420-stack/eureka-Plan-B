// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ImagePreview from './ImagePreview'
import UploadDropzone from './UploadDropzone'

// task 20.1 UploadDropzone · ImagePreview 예시 테스트.
// 선택 입력(파일/카메라/앨범)과 드롭이 onImageSelected 로 첫 파일을 올리는지,
// ImagePreview 가 object URL 을 만들고 언마운트 시 revoke 하는지 확인한다.
// (형식·크기 검증은 20.2, fast-check 속성 테스트는 20.3 로 분리된다.)

function makeImage(name = 'shirt.png'): File {
  return new File([new Uint8Array([1, 2, 3])], name, { type: 'image/png' })
}

describe('UploadDropzone (task 20.1)', () => {
  afterEach(() => cleanup())

  it('renders dropzone, file/album/camera inputs (Req 1.1, 1.2)', () => {
    render(<UploadDropzone onImageSelected={() => {}} />)
    expect(screen.getByTestId('upload-dropzone')).toBeTruthy()
    expect(screen.getByTestId('upload-input-file')).toBeTruthy()
    expect(screen.getByTestId('upload-input-gallery')).toBeTruthy()

    const camera = screen.getByTestId('upload-input-camera') as HTMLInputElement
    // 모바일 카메라 촬영 입력 (Req 1.2)
    expect(camera.getAttribute('capture')).toBe('environment')
    expect(camera.getAttribute('accept')).toBe('image/*')
  })

  it('calls onImageSelected with the chosen file', () => {
    const onImageSelected = vi.fn()
    render(<UploadDropzone onImageSelected={onImageSelected} />)

    const input = screen.getByTestId('upload-input-file') as HTMLInputElement
    const file = makeImage()
    fireEvent.change(input, { target: { files: [file] } })

    expect(onImageSelected).toHaveBeenCalledTimes(1)
    expect(onImageSelected).toHaveBeenCalledWith(file)
  })

  it('emits the first file on drop', () => {
    const onImageSelected = vi.fn()
    render(<UploadDropzone onImageSelected={onImageSelected} />)

    const file = makeImage('dropped.png')
    fireEvent.drop(screen.getByTestId('upload-dropzone'), {
      dataTransfer: { files: [file] },
    })

    expect(onImageSelected).toHaveBeenCalledWith(file)
  })

  it('does not emit when disabled', () => {
    const onImageSelected = vi.fn()
    render(<UploadDropzone onImageSelected={onImageSelected} disabled />)

    const input = screen.getByTestId('upload-input-file') as HTMLInputElement
    fireEvent.change(input, { target: { files: [makeImage()] } })

    expect(onImageSelected).not.toHaveBeenCalled()
  })
})

describe('ImagePreview (task 20.1, Req 1.3)', () => {
  afterEach(() => cleanup())

  it('creates an object URL for the preview and revokes it on unmount', () => {
    // jsdom 은 URL.createObjectURL/revokeObjectURL 를 구현하지 않으므로 먼저 심어둔다.
    URL.createObjectURL = vi.fn()
    URL.revokeObjectURL = vi.fn()
    const createSpy = vi
      .spyOn(URL, 'createObjectURL')
      .mockReturnValue('blob:preview')
    const revokeSpy = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})

    const { unmount } = render(<ImagePreview file={makeImage('preview.png')} />)

    const img = screen.getByTestId('image-preview').querySelector('img')
    expect(img?.getAttribute('src')).toBe('blob:preview')
    expect(createSpy).toHaveBeenCalledTimes(1)

    unmount()
    expect(revokeSpy).toHaveBeenCalledWith('blob:preview')

    createSpy.mockRestore()
    revokeSpy.mockRestore()
  })
})
