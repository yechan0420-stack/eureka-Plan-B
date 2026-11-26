// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'
import App from './App'

// task 19.1 라우팅/화면 예시 테스트 (design.md: 라우팅·ARCHIVE "COMING SOON" 예시 테스트).
// 각 라우트가 올바른 화면을 렌더하는지, HOME 메인 문구가 그대로 노출되는지,
// ARCHIVE 는 "COMING SOON" 만, ABOUT 은 Match_Grade 휴리스틱 명시를 하는지 확인한다.

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )
}

describe('client-side routing (task 19.1)', () => {
  afterEach(() => cleanup())

  it('HOME(/) renders the exact main copy verbatim', () => {
    renderAt('/')
    // design.md 의 "메인 문구(그대로 사용)" — 한 글자도 바꾸지 않는다.
    expect(screen.getAllByText('CLOSELLER.').length).toBeGreaterThan(0)
    expect(screen.getByText('FIND WHAT THEY WEAR.')).toBeTruthy()
    expect(screen.getByText('UPLOAD. IDENTIFY. DISCOVER.')).toBeTruthy()
    expect(
      screen.getByText('사진 한 장으로 당신이 찾던 옷을 발견하세요.'),
    ).toBeTruthy()
  })

  it('VISUAL SEARCH(/search) renders the search flow skeleton', () => {
    renderAt('/search')
    expect(screen.getByTestId('visual-search-flow')).toBeTruthy()
  })

  it('RESULTS(/results) renders the results grid skeleton', () => {
    renderAt('/results')
    expect(screen.getByTestId('results-grid')).toBeTruthy()
  })

  it('ARCHIVE(/archive) shows only a COMING SOON notice', () => {
    renderAt('/archive')
    expect(screen.getByText('COMING SOON')).toBeTruthy()
  })

  it('ABOUT(/about) states Match_Grade is a type/ranking heuristic (Req 11.7)', () => {
    renderAt('/about')
    const main = document.querySelector('main')
    const text = main?.textContent ?? ''
    expect(text).toContain('Match_Grade')
    expect(text).toContain('유형')
    expect(text).toContain('순위')
    expect(text).toContain('휴리스틱')
  })
})
