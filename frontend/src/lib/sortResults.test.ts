import { describe, expect, it } from 'vitest'
import type {
  NormalizedResult,
  ResultMatchGrade,
} from './apiTypes'
import {
  DEFAULT_SORT,
  SORT_OPTION,
  SORT_OPTION_LABEL,
  SORT_OPTION_ORDER,
  isSortOption,
  sortResults,
} from './sortResults'

// task 22.4 SortControls 정렬 순수 코어 단위 테스트 — 가격 오름/내림(미확인 항상
// 뒤 + 안정 정렬), 일치도 높은순(높음>보통>낮음 + 안정 정렬), 기본 옵션을 못
// 박는다(Req 15.1~15.7 / design.md Property 20, 21). fast-check(22.5/22.6)는
// 별도 선택 작업이며 여기서는 예시·엣지 케이스만 다룬다.

/**
 * 테스트 결과를 간결하게 만드는 헬퍼. 식별용 `title` 과 정렬에 쓰이는
 * `price_sort_value` / `match_grade` 만 의미 있게 지정하고 나머지는 채운다.
 */
function makeResult(
  title: string,
  overrides: Partial<NormalizedResult> = {},
): NormalizedResult {
  return {
    title,
    link: `https://example.com/${title}`,
    image_url: `https://example.com/${title}.jpg`,
    price: '미확인',
    currency: null,
    price_sort_value: null,
    platform: '기타',
    region: '미확인',
    match_type: '유사 상품',
    match_grade: '낮음',
    source: 'SERP',
    brand: null,
    ...overrides,
  }
}

/** 정렬 결과에서 식별용 title 만 뽑아 순서 비교를 쉽게 한다. */
function titles(results: readonly NormalizedResult[]): string[] {
  return results.map((r) => r.title)
}

describe('sortResults — 정렬 순수 코어 (task 22.4)', () => {
  it('기본 정렬은 일치도 높은순이다(Req 15.5 / design.md)', () => {
    expect(DEFAULT_SORT).toBe(SORT_OPTION.MatchGradeDesc)
  })

  it('옵션 라벨·나열 순서는 한국어 라벨과 기본값 우선 순서를 지킨다', () => {
    expect(SORT_OPTION_LABEL[SORT_OPTION.PriceAsc]).toBe('가격 낮은순')
    expect(SORT_OPTION_LABEL[SORT_OPTION.PriceDesc]).toBe('가격 높은순')
    expect(SORT_OPTION_LABEL[SORT_OPTION.MatchGradeDesc]).toBe('일치도 높은순')
    // 기본값(일치도 높은순)이 맨 앞.
    expect(SORT_OPTION_ORDER[0]).toBe(DEFAULT_SORT)
    expect(SORT_OPTION_ORDER).toEqual([
      SORT_OPTION.MatchGradeDesc,
      SORT_OPTION.PriceAsc,
      SORT_OPTION.PriceDesc,
    ])
  })

  it('isSortOption 은 유효 옵션만 참, 그 외는 거짓', () => {
    expect(isSortOption('PRICE_ASC')).toBe(true)
    expect(isSortOption('PRICE_DESC')).toBe(true)
    expect(isSortOption('MATCH_GRADE_DESC')).toBe(true)
    expect(isSortOption('nope')).toBe(false)
    expect(isSortOption(null)).toBe(false)
    expect(isSortOption(undefined)).toBe(false)
    expect(isSortOption(1)).toBe(false)
  })

  describe('가격 정렬 (Req 15.1, 15.2, 15.3, 15.6)', () => {
    it('낮은순: 숫자값 오름차순, 미확인(null)은 항상 뒤', () => {
      const input = [
        makeResult('c', { price_sort_value: 300 }),
        makeResult('u1', { price_sort_value: null }),
        makeResult('a', { price_sort_value: 100 }),
        makeResult('b', { price_sort_value: 200 }),
        makeResult('u2', { price_sort_value: null }),
      ]
      expect(titles(sortResults(input, SORT_OPTION.PriceAsc))).toEqual([
        'a',
        'b',
        'c',
        'u1',
        'u2',
      ])
    })

    it('높은순: 숫자값 내림차순, 미확인(null)은 여전히 항상 뒤', () => {
      const input = [
        makeResult('c', { price_sort_value: 300 }),
        makeResult('u1', { price_sort_value: null }),
        makeResult('a', { price_sort_value: 100 }),
        makeResult('b', { price_sort_value: 200 }),
        makeResult('u2', { price_sort_value: null }),
      ]
      // 내림차순이어도 미확인은 뒤로, 그 사이 상대 순서(u1, u2)는 입력 순서 유지.
      expect(titles(sortResults(input, SORT_OPTION.PriceDesc))).toEqual([
        'c',
        'b',
        'a',
        'u1',
        'u2',
      ])
    })

    it('동일 가격은 입력 순서를 유지한다(안정 정렬)', () => {
      const input = [
        makeResult('first', { price_sort_value: 100 }),
        makeResult('second', { price_sort_value: 100 }),
        makeResult('third', { price_sort_value: 100 }),
      ]
      expect(titles(sortResults(input, SORT_OPTION.PriceAsc))).toEqual([
        'first',
        'second',
        'third',
      ])
      // 내림차순에서도 동률은 입력 순서 유지.
      expect(titles(sortResults(input, SORT_OPTION.PriceDesc))).toEqual([
        'first',
        'second',
        'third',
      ])
    })

    it('모두 미확인이면 입력 순서를 그대로 유지한다(안정 정렬)', () => {
      const input = [
        makeResult('x', { price_sort_value: null }),
        makeResult('y', { price_sort_value: null }),
        makeResult('z', { price_sort_value: null }),
      ]
      expect(titles(sortResults(input, SORT_OPTION.PriceAsc))).toEqual([
        'x',
        'y',
        'z',
      ])
      expect(titles(sortResults(input, SORT_OPTION.PriceDesc))).toEqual([
        'x',
        'y',
        'z',
      ])
    })
  })

  describe('일치도 정렬 (Req 15.5, 15.6)', () => {
    it('높음 > 보통 > 낮음 순으로 배치한다', () => {
      const input = [
        makeResult('low', { match_grade: '낮음' }),
        makeResult('high', { match_grade: '높음' }),
        makeResult('mid', { match_grade: '보통' }),
      ]
      expect(titles(sortResults(input, SORT_OPTION.MatchGradeDesc))).toEqual([
        'high',
        'mid',
        'low',
      ])
    })

    it('같은 등급은 입력 순서를 유지한다(안정 정렬)', () => {
      const grades: ResultMatchGrade[] = ['높음', '보통', '낮음']
      const input = grades.flatMap((grade) => [
        makeResult(`${grade}-1`, { match_grade: grade }),
        makeResult(`${grade}-2`, { match_grade: grade }),
      ])
      // 입력은 높음,높음,보통,보통,낮음,낮음 순서. 등급 내 상대 순서 유지.
      expect(titles(sortResults(input, SORT_OPTION.MatchGradeDesc))).toEqual([
        '높음-1',
        '높음-2',
        '보통-1',
        '보통-2',
        '낮음-1',
        '낮음-2',
      ])
    })
  })

  describe('순수성 (입력 비변형 + 새 배열)', () => {
    it('입력 배열을 변형하지 않고 새 배열을 반환한다', () => {
      const input = [
        makeResult('b', { price_sort_value: 200 }),
        makeResult('a', { price_sort_value: 100 }),
      ]
      const snapshot = titles(input)
      const sorted = sortResults(input, SORT_OPTION.PriceAsc)
      // 원본 순서는 그대로.
      expect(titles(input)).toEqual(snapshot)
      // 반환은 새 배열 인스턴스.
      expect(sorted).not.toBe(input)
      expect(titles(sorted)).toEqual(['a', 'b'])
    })

    it('빈 목록은 빈 새 배열을 반환한다', () => {
      const input: NormalizedResult[] = []
      const sorted = sortResults(input, DEFAULT_SORT)
      expect(sorted).toEqual([])
      expect(sorted).not.toBe(input)
    })
  })
})
