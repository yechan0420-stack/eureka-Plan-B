import { describe, expect, it } from 'vitest'
import {
  ERROR,
  IDLE,
  SEARCH_STAGE,
  SEARCH_STAGE_LABEL,
  SEARCH_STAGE_ORDER,
  isSearchStage,
  isTerminalStage,
  nextStage,
  stageForApiStep,
  type SearchStage,
} from './searchProgress'

// task 21.2 SearchProgress 순수 코어 단위 테스트 — 스테이지 순서·전이·종료
// 상태·API 단계 매핑을 못 박는다(Req 13.1, 13.2 / design.md "진행 상태 머신").
// DOM 없이 순수 함수만 검증하므로 jsdom 제약과 무관하다.

describe('SearchProgress 순수 상태 머신 (task 21.2)', () => {
  it('스테이지 순서는 Req 13.1 순서와 라벨을 정확히 따른다', () => {
    // 내부 식별자 순서.
    expect(SEARCH_STAGE_ORDER).toEqual([
      SEARCH_STAGE.UploadingImage,
      SEARCH_STAGE.SearchingMarketplaces,
      SEARCH_STAGE.MatchingProducts,
      SEARCH_STAGE.ResultsReady,
    ])
    // 화면 표시 라벨(공백 포함 정확한 문자열, design.md 그대로).
    expect(SEARCH_STAGE_ORDER.map((s) => SEARCH_STAGE_LABEL[s])).toEqual([
      'UPLOADING IMAGE',
      'SEARCHING MARKETPLACES',
      'MATCHING PRODUCTS',
      'RESULTS READY',
    ])
  })

  it('nextStage 는 순서대로 한 칸씩 전이한다', () => {
    expect(nextStage(SEARCH_STAGE.UploadingImage)).toBe(
      SEARCH_STAGE.SearchingMarketplaces,
    )
    expect(nextStage(SEARCH_STAGE.SearchingMarketplaces)).toBe(
      SEARCH_STAGE.MatchingProducts,
    )
    expect(nextStage(SEARCH_STAGE.MatchingProducts)).toBe(
      SEARCH_STAGE.ResultsReady,
    )
  })

  it('전이를 반복하면 첫 스테이지에서 마지막 스테이지까지 순서대로 도달한다', () => {
    const visited: SearchStage[] = [SEARCH_STAGE.UploadingImage]
    let current = SEARCH_STAGE.UploadingImage as SearchStage
    // 종료 스테이지에 도달할 때까지 전이한다(무한 루프 방지 상한 포함).
    for (let i = 0; i < 10 && !isTerminalStage(current); i += 1) {
      current = nextStage(current)
      visited.push(current)
    }
    expect(visited).toEqual([...SEARCH_STAGE_ORDER])
  })

  it('RESULTS_READY 는 종료 스테이지이며 전이는 멱등(자기 자신)이다', () => {
    expect(isTerminalStage(SEARCH_STAGE.ResultsReady)).toBe(true)
    expect(nextStage(SEARCH_STAGE.ResultsReady)).toBe(SEARCH_STAGE.ResultsReady)
  })

  it('비종료 스테이지는 isTerminalStage 가 false 다', () => {
    expect(isTerminalStage(SEARCH_STAGE.UploadingImage)).toBe(false)
    expect(isTerminalStage(SEARCH_STAGE.SearchingMarketplaces)).toBe(false)
    expect(isTerminalStage(SEARCH_STAGE.MatchingProducts)).toBe(false)
  })

  it('isSearchStage 는 진행 스테이지만 참이고 IDLE·ERROR 는 거짓이다', () => {
    for (const stage of SEARCH_STAGE_ORDER) {
      expect(isSearchStage(stage)).toBe(true)
    }
    expect(isSearchStage(IDLE)).toBe(false)
    expect(isSearchStage(ERROR)).toBe(false)
  })

  it('API 단계는 정직하게 스테이지로 매핑된다', () => {
    // 업로드 발급·S3 직접 업로드는 "이미지 업로드" 스테이지.
    expect(stageForApiStep('requestUpload')).toBe(SEARCH_STAGE.UploadingImage)
    expect(stageForApiStep('uploadToS3')).toBe(SEARCH_STAGE.UploadingImage)
    // 서버 검색 호출은 "마켓플레이스 검색".
    expect(stageForApiStep('search')).toBe(SEARCH_STAGE.SearchingMarketplaces)
    // 응답 정규화 처리 구간은 "상품 매칭".
    expect(stageForApiStep('normalize')).toBe(SEARCH_STAGE.MatchingProducts)
  })
})
