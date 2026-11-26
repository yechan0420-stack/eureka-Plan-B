import { describe, expect, it } from 'vitest'
import type { NormalizedResult } from './apiTypes'
import {
  EMPTY_FILTER_STATE,
  MATCH_TYPE_OPTIONS,
  REGION_OPTIONS,
  derivePlatformOptions,
  filterResults,
  hasActiveFilter,
  toggleValue,
  type FilterState,
} from './filterResults'

// task 22.8 FilterControls 필터 순수 코어 단위 테스트 — 단일 패싯 부분집합,
// 패싯 간 AND, 패싯 내 OR, 빈 선택 = 전체, 부분집합+입력 순서 보존, 플랫폼 옵션
// 유도(Req 16.1~16.3 / design.md Property 23). fast-check(22.9)는 별도 선택
// 작업이며 여기서는 예시·엣지 케이스만 다룬다.

/**
 * 테스트 결과를 간결하게 만드는 헬퍼. 식별용 `title` 과 필터에 쓰이는
 * region / match_type / platform 만 의미 있게 지정하고 나머지는 채운다.
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

/** 결과에서 식별용 title 만 뽑아 순서 비교를 쉽게 한다. */
function titles(results: readonly NormalizedResult[]): string[] {
  return results.map((r) => r.title)
}

/** 모든 패싯을 다양하게 섞은 샘플 목록(입력 순서가 의미를 가진다). */
function sampleResults(): NormalizedResult[] {
  return [
    makeResult('a', {
      region: '국내',
      match_type: '동일 상품 후보',
      platform: '무신사',
    }),
    makeResult('b', {
      region: '해외',
      match_type: '유사 상품',
      platform: 'eBay',
    }),
    makeResult('c', {
      region: '국내',
      match_type: '유사 상품',
      platform: '번개장터',
    }),
    makeResult('d', {
      region: '미확인',
      match_type: '동일 상품 후보',
      platform: '기타',
    }),
    makeResult('e', {
      region: '해외',
      match_type: '동일 상품 후보',
      platform: 'Grailed',
    }),
  ]
}

describe('filterResults — 필터 순수 코어 (task 22.8)', () => {
  it('옵션 상수는 데이터 모델 값·나열 순서를 지킨다', () => {
    expect(REGION_OPTIONS).toEqual(['국내', '해외', '미확인'])
    expect(MATCH_TYPE_OPTIONS).toEqual(['동일 상품 후보', '유사 상품'])
    expect(EMPTY_FILTER_STATE).toEqual({
      regions: [],
      matchTypes: [],
      platforms: [],
    })
  })

  describe('빈 선택 = 전체 표시 (무필터)', () => {
    it('모든 패싯이 비면 입력 전체를 순서 그대로 반환한다', () => {
      const input = sampleResults()
      const out = filterResults(input, EMPTY_FILTER_STATE)
      expect(titles(out)).toEqual(['a', 'b', 'c', 'd', 'e'])
    })

    it('빈 목록은 빈 새 배열을 반환한다', () => {
      const input: NormalizedResult[] = []
      const out = filterResults(input, EMPTY_FILTER_STATE)
      expect(out).toEqual([])
      expect(out).not.toBe(input)
    })
  })

  describe('단일 패싯 (Req 16.1, 16.2, 16.3)', () => {
    it('지역 단일 선택은 해당 구분만 남긴다(부분집합)', () => {
      const out = filterResults(sampleResults(), {
        ...EMPTY_FILTER_STATE,
        regions: ['국내'],
      })
      expect(titles(out)).toEqual(['a', 'c'])
    })

    it('유형 단일 선택은 해당 유형만 남긴다', () => {
      const out = filterResults(sampleResults(), {
        ...EMPTY_FILTER_STATE,
        matchTypes: ['동일 상품 후보'],
      })
      expect(titles(out)).toEqual(['a', 'd', 'e'])
    })

    it('플랫폼 단일 선택은 해당 플랫폼만 남긴다', () => {
      const out = filterResults(sampleResults(), {
        ...EMPTY_FILTER_STATE,
        platforms: ['eBay'],
      })
      expect(titles(out)).toEqual(['b'])
    })
  })

  describe('패싯 내 OR', () => {
    it('지역 복수 선택은 둘 중 하나라도 맞으면 통과(국내 OR 해외)', () => {
      const out = filterResults(sampleResults(), {
        ...EMPTY_FILTER_STATE,
        regions: ['국내', '해외'],
      })
      // 미확인(d)만 제외.
      expect(titles(out)).toEqual(['a', 'b', 'c', 'e'])
    })

    it('플랫폼 복수 선택도 OR 로 묶인다', () => {
      const out = filterResults(sampleResults(), {
        ...EMPTY_FILTER_STATE,
        platforms: ['무신사', 'Grailed'],
      })
      expect(titles(out)).toEqual(['a', 'e'])
    })
  })

  describe('패싯 간 AND', () => {
    it('지역 AND 유형: 두 조건을 모두 만족하는 결과만 남긴다', () => {
      const out = filterResults(sampleResults(), {
        ...EMPTY_FILTER_STATE,
        regions: ['국내'],
        matchTypes: ['유사 상품'],
      })
      // 국내(a,c) ∩ 유사(b,c) = c
      expect(titles(out)).toEqual(['c'])
    })

    it('세 패싯 동시 AND', () => {
      const out = filterResults(sampleResults(), {
        regions: ['해외'],
        matchTypes: ['동일 상품 후보'],
        platforms: ['Grailed'],
      })
      expect(titles(out)).toEqual(['e'])
    })

    it('교집합이 없으면 빈 배열', () => {
      const out = filterResults(sampleResults(), {
        ...EMPTY_FILTER_STATE,
        regions: ['국내'],
        platforms: ['eBay'], // eBay 는 해외(b)뿐 → 국내와 교집합 없음
      })
      expect(out).toEqual([])
    })
  })

  describe('부분집합 + 입력 순서 보존 (Property 23)', () => {
    it('결과는 입력의 부분집합이며 원본 참조를 그대로 유지한다', () => {
      const input = sampleResults()
      const out = filterResults(input, {
        ...EMPTY_FILTER_STATE,
        matchTypes: ['동일 상품 후보'],
      })
      // 모든 출력 원소는 입력에 존재(동일 참조).
      for (const r of out) {
        expect(input).toContain(r)
      }
      // 입력 등장 순서를 보존한다(a→d→e).
      const indices = out.map((r) => input.indexOf(r))
      const sorted = [...indices].sort((x, y) => x - y)
      expect(indices).toEqual(sorted)
    })

    it('입력 배열을 변형하지 않고 새 배열을 반환한다', () => {
      const input = sampleResults()
      const snapshot = titles(input)
      const out = filterResults(input, {
        ...EMPTY_FILTER_STATE,
        regions: ['국내'],
      })
      expect(titles(input)).toEqual(snapshot)
      expect(out).not.toBe(input)
    })
  })

  describe('derivePlatformOptions', () => {
    it('결과에 존재하는 플랫폼을 처음 등장 순서로 중복 없이 유도한다', () => {
      const input = [
        makeResult('a', { platform: '무신사' }),
        makeResult('b', { platform: 'eBay' }),
        makeResult('c', { platform: '무신사' }), // 중복
        makeResult('d', { platform: 'Grailed' }),
      ]
      expect(derivePlatformOptions(input)).toEqual(['무신사', 'eBay', 'Grailed'])
    })

    it('빈 목록은 빈 옵션', () => {
      expect(derivePlatformOptions([])).toEqual([])
    })
  })

  describe('보조 헬퍼', () => {
    it('hasActiveFilter 는 패싯이 하나라도 선택되면 참', () => {
      expect(hasActiveFilter(EMPTY_FILTER_STATE)).toBe(false)
      expect(
        hasActiveFilter({ ...EMPTY_FILTER_STATE, regions: ['국내'] }),
      ).toBe(true)
      expect(
        hasActiveFilter({ ...EMPTY_FILTER_STATE, platforms: ['eBay'] }),
      ).toBe(true)
    })

    it('toggleValue 는 없으면 추가, 있으면 제거한 새 배열을 반환한다', () => {
      const base: FilterState['regions'] = ['국내']
      const added = toggleValue(base, '해외')
      expect(added).toEqual(['국내', '해외'])
      const removed = toggleValue(added, '국내')
      expect(removed).toEqual(['해외'])
      // 순수성: 원본 불변.
      expect(base).toEqual(['국내'])
    })
  })
})
