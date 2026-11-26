/**
 * searchProgress — 검색 진행 상태 머신의 **순수(pure)·테스트 가능한 코어**
 * (task 21.2, Req 13.1, 13.2 / design.md "진행 상태 머신").
 *
 * 이 모듈은 React·DOM·네트워크에 의존하지 않는다. 오직 상태(스테이지) 집합과
 * 그 사이 전이(transition), 그리고 "어떤 API 단계가 어떤 스테이지에 대응하는가"
 * 라는 매핑만을 순수 함수로 제공한다. 프레젠테이션(진행 UI)은
 * `components/SearchProgress.tsx` 가, 실제 흐름 구동(apiClient.runSearch 호출)은
 * `pages/Search.tsx` 가 담당한다. 이렇게 분리해 두면 스테이지 순서·전이·종료
 * 상태를 jsdom 없이 단위 테스트로 못 박을 수 있다.
 *
 * [스테이지와 라벨 (Req 13.1 — design.md 라벨 그대로)]
 *   UPLOADING IMAGE → SEARCHING MARKETPLACES → MATCHING PRODUCTS → RESULTS READY
 * 내부 상태 식별자는 design.md stateDiagram 의 이름(UPLOADING_IMAGE 등)을 쓰고,
 * 화면에 보여줄 라벨은 공백을 포함한 정확한 문자열을 쓴다.
 *
 * [종료(terminal) 상태]
 *   - RESULTS_READY: 정상 완료. 상위(Search)는 이 상태가 되면 RESULTS 화면으로
 *     전환한다(Req 13.2).
 *   - ERROR: 업로드/검색 실패. 상위는 errorCode 를 보존해 ErrorNotice(task
 *     22.10)가 한국어 메시지를 매핑할 수 있게 한다.
 *   - IDLE 은 시작 전 대기 상태로, 진행 스테이지 목록에는 포함하지 않는다.
 */

/** 진행 스테이지(내부 식별자). design.md stateDiagram 의 이름과 일치한다. */
export const SEARCH_STAGE = {
  UploadingImage: 'UPLOADING_IMAGE',
  SearchingMarketplaces: 'SEARCHING_MARKETPLACES',
  MatchingProducts: 'MATCHING_PRODUCTS',
  ResultsReady: 'RESULTS_READY',
} as const

export type SearchStage = (typeof SEARCH_STAGE)[keyof typeof SEARCH_STAGE]

/**
 * 진행 스테이지의 **표시 순서**(Req 13.1). 진행 UI 는 이 순서 그대로 목록을
 * 그리고, 현재 스테이지 앞의 항목은 완료(completed), 현재 항목은 활성(active)으로
 * 표시한다. 순서를 바꾸면 Req 13.1 위반이므로 이 배열이 단일 진실 공급원이다.
 */
export const SEARCH_STAGE_ORDER: readonly SearchStage[] = [
  SEARCH_STAGE.UploadingImage,
  SEARCH_STAGE.SearchingMarketplaces,
  SEARCH_STAGE.MatchingProducts,
  SEARCH_STAGE.ResultsReady,
] as const

/**
 * 스테이지 → 화면 표시 라벨(Req 13.1, design.md 라벨 그대로). 공백을 포함한
 * 정확한 문자열을 사용한다.
 */
export const SEARCH_STAGE_LABEL: Readonly<Record<SearchStage, string>> = {
  [SEARCH_STAGE.UploadingImage]: 'UPLOADING IMAGE',
  [SEARCH_STAGE.SearchingMarketplaces]: 'SEARCHING MARKETPLACES',
  [SEARCH_STAGE.MatchingProducts]: 'MATCHING PRODUCTS',
  [SEARCH_STAGE.ResultsReady]: 'RESULTS READY',
} as const

/** 시작 전 대기 상태(스테이지 목록에는 포함하지 않는다). */
export const IDLE = 'IDLE' as const
export type Idle = typeof IDLE

/** 실패 종료 상태. errorCode 는 ErrorNotice(22.10) 매핑용으로 보존한다. */
export const ERROR = 'ERROR' as const
export type ErrorState = typeof ERROR

/**
 * 상태 머신이 가질 수 있는 전체 상태(진행 스테이지 + IDLE + ERROR). 진행 UI 와
 * 상위 흐름이 함께 다루는 합(union) 타입이다.
 */
export type SearchProgressState = Idle | SearchStage | ErrorState

/**
 * 어떤 상태가 진행 스테이지(IDLE·ERROR 가 아닌)인지 판별한다. 진행 UI 는
 * 스테이지일 때만 목록을 그린다.
 */
export function isSearchStage(state: SearchProgressState): state is SearchStage {
  return (SEARCH_STAGE_ORDER as readonly string[]).includes(state)
}

/**
 * 스테이지가 종료(terminal) 상태인지 — 즉 다음 스테이지가 없는지 — 판별한다.
 * RESULTS_READY 가 유일한 정상 종료 스테이지다. (ERROR 는 스테이지가 아니라
 * 별도 종료 상태다.)
 */
export function isTerminalStage(stage: SearchStage): boolean {
  return stage === SEARCH_STAGE.ResultsReady
}

/**
 * 다음 스테이지로의 전이. 순서(SEARCH_STAGE_ORDER)에서 한 칸 앞으로 간다.
 * 마지막(RESULTS_READY)에서는 더 갈 곳이 없으므로 그대로 RESULTS_READY 를
 * 반환한다(전이 멱등). 상위 흐름은 이 함수에 의존하지 않고 각 await 단계 전후로
 * 명시적 스테이지를 세팅할 수도 있지만, 순서 불변식은 이 함수가 보증한다.
 */
export function nextStage(stage: SearchStage): SearchStage {
  const index = SEARCH_STAGE_ORDER.indexOf(stage)
  if (index < 0 || index >= SEARCH_STAGE_ORDER.length - 1) {
    return stage
  }
  return SEARCH_STAGE_ORDER[index + 1]
}

/**
 * runSearch 흐름의 **API 단계(step)** 를 진행 스테이지로 매핑한다(정직한 매핑을
 * 문서화).
 *
 * apiClient.runSearch 는 내부에서 세 단계를 순서대로 await 한다:
 *   requestUpload → uploadToS3 → search
 * 이 중 앞의 두 단계(발급·S3 직접 업로드)는 "이미지 업로드"에 해당하므로
 * `UPLOADING_IMAGE` 로, 마지막 `search`(서버가 SerpApi 호출→정규화까지 한 번에
 * 수행)는 사용자 관점에서 "마켓플레이스 검색"이므로 `SEARCHING_MARKETPLACES` 로
 * 매핑한다.
 *
 * design.md 상태도는 SEARCHING_MARKETPLACES→MATCHING_PRODUCTS 를 "SerpApi 응답
 * 수신" 시점으로 나누지만, 프론트에서 `search`는 단일 await 호출이라 그 경계를
 * 직접 관측할 수 없다. 따라서 상위(Search)는 `search` 호출 직전에
 * SEARCHING_MARKETPLACES 를, 호출이 반환되기 직전(응답 처리 시작) 구간을
 * MATCHING_PRODUCTS 로 표현하고, 성공 시 RESULTS_READY 로 넘어간다. 이 매핑은
 * "서버 단일 호출을 둘러싼 명시적 스테이지 전이"라는 사실을 숨기지 않는다.
 */
export type ApiStep = 'requestUpload' | 'uploadToS3' | 'search' | 'normalize'

export function stageForApiStep(step: ApiStep): SearchStage {
  switch (step) {
    case 'requestUpload':
    case 'uploadToS3':
      return SEARCH_STAGE.UploadingImage
    case 'search':
      return SEARCH_STAGE.SearchingMarketplaces
    case 'normalize':
      return SEARCH_STAGE.MatchingProducts
  }
}
