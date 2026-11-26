// @vitest-environment jsdom
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { NormalizedResult } from '../lib/apiTypes'
import ResultGrid from './ResultGrid'
import TestDataBadge from './TestDataBadge'
import PurchaseButton from './PurchaseButton'
import { isPurchaseEnabled, isTestData } from '../lib/sourceGating'

// task 22.2 TestDataBadge · 구매 버튼 제어 (Req 19.3, 19.4).
// source=MOCK → "TEST DATA" 배지 + 구매 버튼 비활성, source=SERP → 배지 없음 +
// 구매 버튼 활성. fast-check 속성 테스트(Property 25)는 task 22.3 으로 분리된다.
//
// Results.tsx 가 ResultGrid 에 넘기는 것과 동일한 renderBadge/renderPurchase
// 심(seam, task 22.1)을 그대로 재현해, 배선(wiring)까지 함께 검증한다.

const mockResult: NormalizedResult = {
  title: 'MOCK 데님 재킷',
  link: 'https://example.com/item/mock-denim',
  image_url: 'https://img.example.com/mock-denim.jpg',
  price: '₩99,000',
  currency: 'KRW',
  price_sort_value: 99000,
  platform: '번개장터',
  region: '국내',
  match_type: '동일 상품 후보',
  match_grade: '높음',
  source: 'MOCK',
  brand: null,
}

const serpResult: NormalizedResult = {
  title: 'SERP 후디',
  link: 'https://example.com/item/serp-hoodie',
  image_url: 'https://img.example.com/serp-hoodie.jpg',
  price: '$120',
  currency: 'USD',
  price_sort_value: 120,
  platform: 'eBay',
  region: '해외',
  match_type: '유사 상품',
  match_grade: '보통',
  source: 'SERP',
  brand: null,
}

// Results.tsx 의 배선과 동일한 렌더 함수.
const renderBadge = (r: NormalizedResult) =>
  isTestData(r.source) ? <TestDataBadge /> : null
const renderPurchase = (r: NormalizedResult) => (
  <PurchaseButton source={r.source} link={r.link} />
)

describe('sourceGating 순수 로직 (task 22.2)', () => {
  it('isTestData: MOCK 만 테스트 데이터 (Req 19.3)', () => {
    expect(isTestData('MOCK')).toBe(true)
    expect(isTestData('SERP')).toBe(false)
  })

  it('isPurchaseEnabled: SERP 만 구매 활성 (Req 19.4)', () => {
    expect(isPurchaseEnabled('SERP')).toBe(true)
    expect(isPurchaseEnabled('MOCK')).toBe(false)
  })
})

describe('TestDataBadge (task 22.2)', () => {
  afterEach(() => cleanup())

  it('정확한 라벨 "TEST DATA" 를 렌더한다 (Req 19.3)', () => {
    render(<TestDataBadge />)
    expect(screen.getByTestId('test-data-badge').textContent).toBe('TEST DATA')
  })
})

describe('PurchaseButton 게이팅 (task 22.2, Req 19.4)', () => {
  afterEach(() => cleanup())

  it('source=MOCK 이면 구매 버튼이 비활성화된다', () => {
    render(<PurchaseButton source="MOCK" link={mockResult.link} />)
    const button = screen.getByTestId('purchase-button') as HTMLButtonElement
    expect(button.disabled).toBe(true)
    expect(button.getAttribute('aria-disabled')).toBe('true')
  })

  it('source=SERP 이면 구매 버튼이 활성화된다', () => {
    render(<PurchaseButton source="SERP" link={serpResult.link} />)
    const button = screen.getByTestId('purchase-button') as HTMLButtonElement
    expect(button.disabled).toBe(false)
    expect(button.getAttribute('aria-disabled')).toBe('false')
  })
})

describe('ResultGrid 배선 — 배지/구매 버튼 제어 (task 22.2, Req 19.3/19.4)', () => {
  afterEach(() => cleanup())

  it('MOCK 결과: TEST DATA 배지 표시 + 구매 버튼 비활성', () => {
    render(
      <ResultGrid
        results={[mockResult]}
        renderBadge={renderBadge}
        renderPurchase={renderPurchase}
      />,
    )
    const card = screen.getByTestId('product-card')

    // "TEST DATA" 배지가 보인다.
    expect(within(card).getByTestId('test-data-badge').textContent).toBe(
      'TEST DATA',
    )
    // 구매 버튼이 비활성이다.
    const button = within(card).getByTestId('purchase-button') as HTMLButtonElement
    expect(button.disabled).toBe(true)

    // 원본 이동 링크(Req 14.4)는 source 와 무관하게 유지된다.
    expect(within(card).getByTestId('product-original-link')).toBeTruthy()
  })

  it('SERP 결과: 배지 없음 + 구매 버튼 활성', () => {
    render(
      <ResultGrid
        results={[serpResult]}
        renderBadge={renderBadge}
        renderPurchase={renderPurchase}
      />,
    )
    const card = screen.getByTestId('product-card')

    // 배지가 없다 (배지 슬롯 자체가 렌더되지 않는다).
    expect(within(card).queryByTestId('test-data-badge')).toBeNull()
    expect(within(card).queryByTestId('product-badge-slot')).toBeNull()

    // 구매 버튼이 활성이다.
    const button = within(card).getByTestId('purchase-button') as HTMLButtonElement
    expect(button.disabled).toBe(false)
  })

  it('MOCK/SERP 혼재 목록에서 각 카드가 올바르게 게이팅된다', () => {
    render(
      <ResultGrid
        results={[mockResult, serpResult]}
        renderBadge={renderBadge}
        renderPurchase={renderPurchase}
      />,
    )
    const cards = screen.getAllByTestId('product-card')
    expect(cards).toHaveLength(2)

    // 첫 카드(MOCK): 배지 있음 + 비활성.
    expect(within(cards[0]).getByTestId('test-data-badge')).toBeTruthy()
    expect(
      (within(cards[0]).getByTestId('purchase-button') as HTMLButtonElement)
        .disabled,
    ).toBe(true)

    // 둘째 카드(SERP): 배지 없음 + 활성.
    expect(within(cards[1]).queryByTestId('test-data-badge')).toBeNull()
    expect(
      (within(cards[1]).getByTestId('purchase-button') as HTMLButtonElement)
        .disabled,
    ).toBe(false)
  })
})
