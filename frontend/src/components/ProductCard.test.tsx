// @vitest-environment jsdom
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { NormalizedResult } from '../lib/apiTypes'
import ProductCard from './ProductCard'
import ResultGrid from './ResultGrid'

// task 22.1 ResultGrid/ProductCard 예시 테스트 (Req 14.1~14.4).
// 이미지·상품명·플랫폼·가격(또는 "미확인")·동일/유사 배지·Match_Grade·
// 새 탭 원본 링크(target=_blank, rel 에 noopener)·브랜드(있을 때)를 확인한다.
// fast-check 속성 테스트(Property 25)는 task 22.3 으로 분리된다.

const withPriceAndBrand: NormalizedResult = {
  title: '빈티지 데님 재킷',
  link: 'https://example.com/item/denim-jacket',
  image_url: 'https://img.example.com/denim.jpg',
  price: '₩129,000',
  currency: 'KRW',
  price_sort_value: 129000,
  platform: '번개장터',
  region: '국내',
  match_type: '동일 상품 후보',
  match_grade: '높음',
  source: 'SERP',
  brand: 'CLOSELLER',
}

const noPriceNoBrand: NormalizedResult = {
  title: 'Unknown Price Hoodie',
  link: 'https://example.com/item/hoodie',
  image_url: 'https://img.example.com/hoodie.jpg',
  price: '미확인',
  currency: null,
  price_sort_value: null,
  platform: 'eBay',
  region: '해외',
  match_type: '유사 상품',
  match_grade: '낮음',
  source: 'SERP',
  brand: null,
}

describe('ProductCard (task 22.1)', () => {
  afterEach(() => cleanup())

  it('renders image, title, platform, price+currency, badges and brand when present', () => {
    render(<ProductCard result={withPriceAndBrand} />)

    const image = screen.getByTestId('product-image') as HTMLImageElement
    expect(image.getAttribute('src')).toBe(withPriceAndBrand.image_url)
    expect(image.getAttribute('alt')).toBe(withPriceAndBrand.title)

    expect(screen.getByTestId('product-title').textContent).toBe(
      withPriceAndBrand.title,
    )
    expect(screen.getByTestId('product-platform').textContent).toBe(
      withPriceAndBrand.platform,
    )

    // 가격 + 통화 (Req 14.2)
    expect(screen.getByTestId('product-price-value').textContent).toBe('₩129,000')
    expect(screen.getByTestId('product-currency').textContent).toBe('KRW')

    // 동일/유사 배지 + Match_Grade (Req 14.2)
    expect(screen.getByTestId('match-type-badge').textContent).toBe('동일 상품 후보')
    expect(screen.getByTestId('match-grade-badge').textContent).toBe('높음')

    // 브랜드 표시 (Req 14.3)
    expect(screen.getByTestId('product-brand').textContent).toBe('CLOSELLER')
  })

  it('opens the original sale page in a NEW TAB with safe rel (Req 14.4)', () => {
    render(<ProductCard result={withPriceAndBrand} />)
    const link = screen.getByTestId('product-original-link') as HTMLAnchorElement
    expect(link.getAttribute('href')).toBe(withPriceAndBrand.link)
    expect(link.getAttribute('target')).toBe('_blank')
    expect(link.getAttribute('rel')).toContain('noopener')
  })

  it('shows "미확인" with no currency and no brand when those fields are missing', () => {
    render(<ProductCard result={noPriceNoBrand} />)
    expect(screen.getByTestId('product-price-value').textContent).toBe('미확인')
    expect(screen.queryByTestId('product-currency')).toBeNull()
    expect(screen.queryByTestId('product-brand')).toBeNull()
    expect(screen.getByTestId('match-type-badge').textContent).toBe('유사 상품')
    expect(screen.getByTestId('match-grade-badge').textContent).toBe('낮음')
  })

  it('does not render the 22.2 seams (badge/purchase slots) unless provided', () => {
    render(<ProductCard result={withPriceAndBrand} />)
    expect(screen.queryByTestId('product-badge-slot')).toBeNull()
    expect(screen.queryByTestId('product-purchase-slot')).toBeNull()
  })
})

describe('ResultGrid (task 22.1)', () => {
  afterEach(() => cleanup())

  it('renders one ProductCard per result (Req 14.1)', () => {
    render(<ResultGrid results={[withPriceAndBrand, noPriceNoBrand]} />)
    const cards = screen.getAllByTestId('product-card')
    expect(cards).toHaveLength(2)

    // 각 카드에 올바른 상품명이 매핑되는지 확인한다.
    const titles = screen
      .getAllByTestId('product-title')
      .map((node) => node.textContent)
    expect(titles).toEqual([withPriceAndBrand.title, noPriceNoBrand.title])

    // 각 카드의 원본 링크가 새 탭으로 열린다.
    for (const card of cards) {
      const link = within(card).getByTestId(
        'product-original-link',
      ) as HTMLAnchorElement
      expect(link.getAttribute('target')).toBe('_blank')
      expect(link.getAttribute('rel')).toContain('noopener')
    }
  })

  it('renders an empty grid for an empty result list', () => {
    render(<ResultGrid results={[]} />)
    expect(screen.queryAllByTestId('product-card')).toHaveLength(0)
  })
})
