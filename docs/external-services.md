# 외부 서비스 (External Services)

## 개요

CLOSELLER가 사용하는 **유일한 외부 서비스**는 **SerpApi Google Lens API**입니다. 그 외의 모든 인프라(S3, DynamoDB, Lambda, API Gateway, CloudWatch 등)는 AWS 안에서 실행되며, CLOSELLER가 AWS 외부로 데이터를 보내는 경로는 SerpApi 하나뿐입니다.

- 공식 문서: <https://serpapi.com/google-lens-api>

---

## SerpApi의 역할

Search_Lambda는 사용자가 크롭한 옷 이미지를 외부 검색에 넘기기 위해 SerpApi를 호출합니다.

- Search_Lambda가 크롭된 옷 이미지에 대해 **5분 유효의 Presigned GET URL**을 발급합니다.
- 이 URL을 SerpApi에 `engine=google_lens`로 전달하여 Google Lens 이미지 검색을 수행합니다.
- SerpApi는 `visual_matches`(실제 판매 상품 후보 목록)를 반환합니다.
- CLOSELLER는 이 `visual_matches`를 정규화·분류·정렬하여 상품 카드로 보여줍니다.

즉, SerpApi는 "크롭 이미지 → 실제 판매 상품 후보" 변환을 담당하는 외부 이미지 검색 엔진입니다.

---

## 사용 이유

- Google Lens의 이미지 검색 결과를 **서버에서 안정적으로** 받기 위해 SerpApi를 사용합니다. (브라우저에서 직접 Google Lens를 긁는 방식보다 안정적이고 응답 구조가 문서화되어 있습니다.)
- **데이터 정직성**: 공식 문서에 명시된 **요청 파라미터와 응답 필드만** 사용합니다. 문서에 없는 필드는 추측하거나 임의로 만들어 채워 넣지 않습니다. 응답에 없는 가격·상품·링크 값은 생성하지 않습니다.

---

## 무료 한도 (Free Tier)

SerpApi 무료 플랜의 호출 한도는 다음과 같습니다.

| 구분 | 한도 |
| --- | --- |
| 월간 | **250회** |
| 시간당 | **50회** |

> 참고: 위 수치는 본 프로젝트의 요구사항(Req 22.3)에 명시된 값(월 250회, 시간당 50회)을 그대로 기록한 것입니다. SerpApi가 추후 한도를 변경할 수 있으므로, 최신 값은 위의 공식 문서에서 확인하십시오.

### 무료 한도를 보호하기 위한 장치

CLOSELLER는 SerpApi 무료 한도를 초과하지 않도록 여러 겹의 보호 장치를 둡니다.

- **SHA-256 캐시 (TTL 24시간)**: 동일한 이미지는 해시가 같으므로, 24시간 안의 재검색은 외부 호출 없이 캐시에서 반환합니다.
- **월간 전체 호출 상한 (기본 200)**: 앱 전체의 월간 SerpApi 호출 수를 제한합니다.
- **IP별 일일 호출 상한 (기본 5)**: 한 IP가 하루에 호출할 수 있는 횟수를 제한합니다.
- **API Gateway 스로틀 (기본 rate 2/초, burst 5)**: 순간적인 과다 요청을 차단합니다.

> **앱 상한(200)을 SerpApi 월 한도(250)보다 낮게 둔 이유**: 여유 버퍼를 확보하기 위함입니다. 캐시 통계 지연, 재시도, 측정 오차 등으로 실제 호출이 예상보다 늘어나더라도 SerpApi 월 250회 한도를 넘지 않도록 안전 여유를 둡니다.

---

## 비밀값 관리

- SerpApi Key는 **AWS SSM Parameter Store의 SecureString**으로 보관합니다.
  - 파라미터 경로: `/closeller/serpapi/api-key`
- Search_Lambda는 이 Key를 **런타임에만** 로드하여 사용합니다.
- Key는 **코드, 커밋, 프론트엔드 어디에도** 값으로 넣지 않습니다. `template.yaml`에도 값이 아닌 참조만 둡니다.

---

## 승인 규칙

- 실제 SerpApi 호출(Key를 사용한 라이브 `google_lens` 검색)은 **사용자 승인 전에 실행하지 않습니다.**
- 로컬 개발·테스트는 환경변수 `USE_MOCK_SEARCH=true`로 수행하며, 이때는 SerpApi Key 없이 고정 테스트 데이터를 사용합니다(외부 미호출).
