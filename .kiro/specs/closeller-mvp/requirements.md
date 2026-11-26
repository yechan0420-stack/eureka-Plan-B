# Requirements Document

## Introduction

CLOSELLER 1차 MVP는 사용자가 패션 사진을 올리고 사진 속 옷 영역을 크롭하면, SerpApi Google Lens의 실제 검색 결과를 상품 카드로 보여주고 원본 판매 페이지로 이동할 수 있게 하는 기능이다. 본 단계는 "업로드 → 크롭 → 외부 검색 → 결과 표시"의 핵심 흐름만 구현한다. 의류 분석(Bedrock), 로그인(Cognito), 검색 기록/관심 상품 저장은 본 단계 범위에서 제외하며 미리 만들지 않는다. ARCHIVE 화면은 "COMING SOON" 안내만 제공한다. 환율 변환은 하지 않고 가격은 검색 API가 반환한 통화 그대로 표시한다. 인프라는 모두 AWS에서 실행되며, 외부 검색은 SerpApi Google Lens API만 사용한다.

본 문서의 모든 요구사항은 `.kiro/steering/closeller.md`의 프로젝트 규칙(인프라, 비용, 승인, 보안, 데이터 정직성, 디자인, 코드/문서 규칙)을 준수한다.

## Glossary

- **CLOSELLER_System**: 본 MVP 전체 시스템. 프론트엔드, 백엔드, 인프라를 포함한 서비스 전체를 가리킨다.
- **Frontend**: React, TypeScript, Vite, Tailwind CSS로 만들어 AWS Amplify Hosting에서 서빙되는 웹 클라이언트.
- **Upload_Lambda**: `POST /uploads` 요청을 처리하는 AWS Lambda(Python) 함수. Presigned POST를 발급한다.
- **Search_Lambda**: `POST /search` 요청을 처리하는 AWS Lambda(Python) 함수. 검증, 캐시 조회, 호출 제한, SerpApi 호출, 결과 정규화, 원본 삭제를 수행한다.
- **API_Gateway**: AWS API Gateway HTTP API. `POST /uploads`, `POST /search` 라우트를 노출하고 스로틀과 CORS를 적용한다.
- **Image_Bucket**: 업로드 이미지를 저장하는 비공개 S3 버킷.
- **Cache_Table**: 이미지 해시 기반 검색 결과 캐시를 저장하는 DynamoDB 테이블(TTL 24시간).
- **Counter_Table**: 월간 전체 호출 수와 IP별 일일 호출 수 카운터를 저장하는 DynamoDB 테이블(TTL 적용). (하나의 테이블로 통합하거나 Cache_Table과 분리 저장할 수 있으나, 본 문서에서는 카운터 역할을 지칭한다.)
- **SerpApi_Service**: 외부 검색 서비스인 SerpApi Google Lens API. AWS 외부 서비스이다.
- **Presigned_POST**: S3가 발급하는 5분 유효의 직접 업로드용 서명 URL과 정책. 크기 제한을 포함한다.
- **Presigned_GET**: S3가 발급하는 5분 유효의 읽기용 서명 URL. SerpApi가 이미지에 접근할 때 사용한다.
- **Product_Card**: 검색 결과 1건을 표시하는 UI 요소. 상품 이미지, 브랜드(있을 때), 상품명, 가격+통화 또는 "미확인", 판매 플랫폼, 동일상품후보/유사상품 배지, 일치도 등급, 원본 판매 페이지 이동 버튼을 포함한다.
- **Platform_Map**: 판매 페이지 도메인을 판매 플랫폼 이름으로 분류하는 매핑표. 한 곳에서 관리하며 단위 테스트를 둔다.
- **Match_Grade**: 일치도 등급. "높음", "보통", "낮음" 중 하나이며, SerpApi 결과 유형과 순위 기반 휴리스틱으로 산정한다.
- **Consent_Checkbox**: 사진이 외부 검색 서비스(Google Lens, SerpApi)로 전송된다는 안내에 대한 사용자 동의 체크박스.
- **Mock_Mode**: 환경변수 `USE_MOCK_SEARCH=true`일 때 활성화되는 테스트 모드. SerpApi를 호출하지 않고 고정 테스트 데이터를 반환한다.
- **Parameter_Store**: AWS SSM Parameter Store. SerpApi Key를 SecureString으로 보관한다.

## Requirements

### Requirement 1: 사진 업로드 입력

**User Story:** 사용자로서, HOME 화면에서 패션 사진을 올리고 싶다. 그래야 옷 검색을 시작할 수 있다.

#### Acceptance Criteria

1. WHEN 사용자가 HOME 화면에 접근하면, THE Frontend SHALL 드래그앤드롭 영역과 파일 선택 버튼을 표시한다
2. WHERE 사용자가 모바일 기기를 사용하면, THE Frontend SHALL 카메라 촬영과 앨범 선택 입력 수단을 제공한다
3. WHEN 사용자가 파일을 선택하거나 드롭하면, THE Frontend SHALL 선택된 이미지의 미리보기를 표시한다
4. IF 선택된 파일의 형식이 JPG, PNG, WEBP 중 하나가 아니면, THEN THE Frontend SHALL 지원 형식 안내 메시지를 표시하고 해당 파일을 거부한다
5. IF 선택된 파일의 크기가 10MB를 초과하면, THEN THE Frontend SHALL 크기 초과 안내 메시지를 표시하고 해당 파일을 거부한다

### Requirement 2: 옷 영역 크롭

**User Story:** 사용자로서, 사진에서 옷 영역만 크롭하고 싶다. 그래야 옷 부분만 검색에 사용된다.

#### Acceptance Criteria

1. WHEN 미리보기가 표시되면, THE Frontend SHALL 사용자가 옷 영역을 지정할 수 있는 크롭 도구를 제공한다
2. THE Frontend SHALL 크롭 처리를 브라우저에서 수행한다
3. WHEN 사용자가 크롭을 확정하면, THE Frontend SHALL 크롭된 이미지만 서버 업로드 대상으로 사용한다
4. THE Frontend SHALL 크롭되지 않은 원본 이미지를 서버로 전송하지 않는다

### Requirement 3: 외부 검색 전송 동의

**User Story:** 사용자로서, 내 사진이 외부 검색 서비스로 전송된다는 사실을 미리 알고 동의하고 싶다. 그래야 내 데이터가 어디로 가는지 통제할 수 있다.

#### Acceptance Criteria

1. WHEN 사용자가 크롭을 확정하면, THE Frontend SHALL "사진이 외부 검색 서비스(Google Lens, SerpApi)로 전송됩니다"라는 안내 문구와 Consent_Checkbox를 표시한다
2. WHILE Consent_Checkbox가 선택되지 않은 상태이면, THE Frontend SHALL 검색 시작 동작을 비활성화한다
3. WHEN Consent_Checkbox가 선택되고 사용자가 검색을 시작하면, THE Frontend SHALL 검색 요청을 진행한다

### Requirement 4: 크롭 이미지 업로드

**User Story:** 사용자로서, 크롭한 이미지를 안전하게 서버에 올리고 싶다. 그래야 검색 처리가 시작된다.

#### Acceptance Criteria

1. WHEN Frontend가 업로드를 시작하면, THE Frontend SHALL Upload_Lambda에 `POST /uploads` 요청을 보낸다
2. WHEN Upload_Lambda가 업로드 요청을 받으면, THE Upload_Lambda SHALL 유효 시간 300초(5분)와 최대 크기 10MB 제한과 허용 Content-Type(image/jpeg, image/png, image/webp)을 포함한 Presigned_POST를 발급하고 3초 이내에 응답한다
3. WHEN Presigned_POST가 발급되면, THE Frontend SHALL 발급된 Presigned_POST를 사용하여 Image_Bucket으로 이미지를 직접 업로드한다
4. THE Upload_Lambda SHALL 업로드 객체 키를 버전 4 랜덤 UUID로 생성한다
5. THE Upload_Lambda SHALL 원본 파일명을 저장하지 않는다
6. IF 업로드된 이미지의 크기가 10MB를 초과하면, THEN THE Image_Bucket SHALL Presigned_POST 크기 제한에 따라 업로드를 거부하고, Image_Bucket에 객체를 저장하지 않으며, Frontend가 실패를 식별할 수 있는 거부 응답을 반환한다
7. IF Presigned_POST의 유효 시간 300초가 경과한 후 업로드가 시도되면, THEN THE Image_Bucket SHALL 업로드를 거부하고 Frontend가 만료를 식별할 수 있는 거부 응답을 반환한다
8. IF 업로드된 이미지의 Content-Type이 허용 목록(image/jpeg, image/png, image/webp)에 포함되지 않으면, THEN THE Image_Bucket SHALL 업로드를 거부하고 Image_Bucket에 객체를 저장하지 않는다

### Requirement 5: 검색 요청 서버 검증

**User Story:** 백엔드 담당자로서, 검색 처리 전에 업로드된 이미지를 서버에서 다시 검증하고 싶다. 그래야 잘못된 입력으로 외부 호출이 낭비되지 않는다.

#### Acceptance Criteria

1. WHEN Search_Lambda가 `POST /search` 요청을 받으면, THE Search_Lambda SHALL 해당 객체가 Image_Bucket에 존재하는지 확인한다
2. WHEN Search_Lambda가 객체를 검증하면, THE Search_Lambda SHALL 객체 크기가 10MB 이하인지 확인한다
3. WHEN Search_Lambda가 객체를 검증하면, THE Search_Lambda SHALL 파일 내용의 매직 바이트를 확인하여 JPG, PNG, WEBP 중 하나인지 검증한다
4. IF 객체가 존재하지 않거나 크기 또는 매직 바이트 검증에 실패하면, THEN THE Search_Lambda SHALL 검증 실패 오류를 반환하고 SerpApi_Service를 호출하지 않는다

### Requirement 6: 검색 결과 캐싱

**User Story:** 운영자로서, 동일한 이미지에 대해 외부 호출을 반복하지 않도록 캐시를 쓰고 싶다. 그래야 SerpApi 호출 비용과 한도를 아낄 수 있다.

#### Acceptance Criteria

1. WHEN Search_Lambda가 검증을 통과하면, THE Search_Lambda SHALL 이미지의 SHA-256 해시를 계산한다
2. WHEN SHA-256 해시가 계산되면, THE Search_Lambda SHALL Cache_Table에서 해당 해시의 캐시 항목을 조회한다
3. IF 유효한 캐시 항목이 존재하면, THEN THE Search_Lambda SHALL 캐시된 결과를 반환하고 SerpApi_Service를 호출하지 않는다
4. WHEN Search_Lambda가 새 검색 결과를 생성하면, THE Search_Lambda SHALL 해당 결과를 TTL 24시간으로 Cache_Table에 저장한다

### Requirement 7: 호출 횟수 제한

**User Story:** 운영자로서, SerpApi 호출 횟수를 제한하고 싶다. 그래야 무료 한도와 비용을 초과하지 않는다.

#### Acceptance Criteria

1. WHEN Search_Lambda가 캐시 미적중 상태이면, THE Search_Lambda SHALL SerpApi_Service 호출 전에 월간 전체 호출 수와 요청 IP별 일일 호출 수를 Counter_Table에서 조회하여 각각의 상한과 비교한다
2. WHEN Search_Lambda가 캐시 적중 상태이면, THE Search_Lambda SHALL 월간 전체 호출 카운터와 IP별 일일 호출 카운터를 증가시키지 않는다
3. THE Counter_Table SHALL 월간 전체 SerpApi 호출 상한을 환경변수로 설정된 값(기본 200, 허용 범위 1~1,000,000의 정수)으로 적용한다
4. THE Counter_Table SHALL IP별 일일 호출 상한을 환경변수로 설정된 값(기본 5, 허용 범위 1~1,000,000의 정수)으로 적용한다
5. WHEN Search_Lambda가 상한 확인을 통과한 후 SerpApi_Service를 호출하기 직전이면, THE Search_Lambda SHALL DynamoDB 조건부 업데이트로 월간 전체 호출 카운터와 IP별 일일 호출 카운터를 각각 1씩 원자적으로 증가시킨다
6. IF 증가 후 값이 상한을 초과하게 되는 조건으로 인해 DynamoDB 조건부 업데이트가 실패하면, THEN THE Search_Lambda SHALL SerpApi_Service를 호출하지 않고 카운터를 증가 이전 값으로 유지하며 한도 초과 안내 메시지를 반환한다
7. IF 월간 전체 호출 수 또는 IP별 일일 호출 수가 각각의 상한 값 이상(상한 도달 또는 초과)이면, THEN THE Search_Lambda SHALL SerpApi_Service를 호출하지 않고 한도 초과임을 나타내는 안내 메시지를 반환한다
8. THE Search_Lambda SHALL IP 주소를 단방향 해시 형태로만 Counter_Table에 저장하고 원본 IP 주소는 저장하지 않는다
9. THE API_Gateway SHALL 요청 스로틀을 환경변수로 설정된 값(기본 rate 초당 2건, burst 5건, 각 허용 범위 1~10,000의 정수)으로 적용한다

### Requirement 8: SerpApi Google Lens 검색 호출

**User Story:** 사용자로서, 크롭한 옷 이미지로 실제 상품 검색을 수행하고 싶다. 그래야 실제 판매 상품을 찾을 수 있다.

#### Acceptance Criteria

1. WHEN 캐시 미적중이고 호출 제한을 통과하면, THE Search_Lambda SHALL 유효 시간 5분의 Presigned_GET URL을 발급한다
2. WHEN Presigned_GET URL이 발급되면, THE Search_Lambda SHALL 해당 URL이 외부에서 접근 가능한지 확인한다
3. WHEN 외부 접근 가능이 확인되면, THE Search_Lambda SHALL SerpApi_Service의 google_lens 엔진을 Presigned_GET URL로 호출한다
4. WHEN Search_Lambda가 SerpApi_Service를 호출하면, THE Search_Lambda SHALL SerpApi Key를 Parameter_Store의 SecureString에서 런타임에 읽어 사용한다
5. THE Search_Lambda SHALL SerpApi_Service의 요청 파라미터와 응답 구조를 공식 문서에 명시된 필드만 사용하여 처리한다
6. THE Search_Lambda SHALL 공식 문서에 없는 응답 필드를 추측하여 사용하지 않는다

### Requirement 9: 검색 결과 정규화

**User Story:** 사용자로서, 검색 결과가 일관된 형식으로 정리되어 보이길 원한다. 그래야 상품을 쉽게 비교할 수 있다.

#### Acceptance Criteria

1. WHEN Search_Lambda가 SerpApi_Service 응답을 받으면, THE Search_Lambda SHALL 각 결과를 상품명, 판매 플랫폼, 상품 이미지 URL, 판매 페이지 URL을 포함한 정규화 형식으로 변환한다
2. IF SerpApi_Service 결과에 상품명, 상품 이미지 URL, 판매 페이지 URL 중 하나라도 비어 있거나 누락되면, THEN THE Search_Lambda SHALL 해당 결과를 정규화 대상에서 제외한다
3. WHERE SerpApi_Service 응답에 브랜드 정보가 포함되면, THE Search_Lambda SHALL 브랜드를 결과에 포함한다
4. WHERE SerpApi_Service 응답에 가격과 통화 정보가 포함되면, THE Search_Lambda SHALL 가격과 통화를 반환된 그대로 결과에 포함한다
5. IF 가격 정보가 없거나 숫자 값으로 파싱할 수 없으면, THEN THE Search_Lambda SHALL 가격을 "미확인"으로 표시하고 해당 결과는 유지한다
6. WHEN Search_Lambda가 결과를 정규화하면, THE Search_Lambda SHALL 판매 페이지 URL을 정규화(스킴·호스트 소문자 변환, 추적용 쿼리 파라미터 및 프래그먼트 제거, 끝 슬래시 제거)한 값을 기준으로 중복을 판정하여, 동일 기준의 결과 중 첫 번째 결과 1건만 남기고 나머지를 제거한다
7. WHEN Search_Lambda가 결과를 정규화하면, THE Search_Lambda SHALL 가격이 "미확인"이 아닌 결과를 가격 오름차순으로, 가격이 동일하거나 "미확인"인 결과는 상품명 가나다순으로 정렬한다
8. IF 판매 페이지 URL의 스킴이 http 또는 https가 아니면, THEN THE Search_Lambda SHALL 해당 결과를 제외한다
9. THE Search_Lambda SHALL SerpApi_Service 응답에 존재하지 않는 가격, 상품, 링크 값을 생성하거나 추론하여 채워 넣지 않는다

### Requirement 10: 판매 플랫폼 분류

**User Story:** 사용자로서, 상품이 어느 플랫폼에서 판매되는지 알고 싶다. 그래야 신뢰할 수 있는 곳에서 구매할 수 있다.

#### Acceptance Criteria

1. WHEN Search_Lambda가 결과를 정규화하면, THE Search_Lambda SHALL 판매 페이지 도메인을 Platform_Map 기준으로 후루츠패밀리, 번개장터, 무신사, KREAM, eBay, Grailed, Vestiaire Collective 중 하나로 분류한다
2. IF 도메인이 Platform_Map에 정의된 플랫폼과 일치하지 않고 브랜드 공식 홈페이지로 보이면, THEN THE Search_Lambda SHALL 플랫폼을 "공식 홈페이지 후보"로 분류한다
3. IF 도메인이 Platform_Map에 정의된 플랫폼과 일치하지 않고 분류 근거가 없으면, THEN THE Search_Lambda SHALL 플랫폼을 "기타"로 분류한다
4. THE Search_Lambda SHALL 플랫폼을 기준으로 국내 또는 해외 구분을 결정한다
5. IF 플랫폼 기준으로 국내 또는 해외를 판단할 근거가 없으면, THEN THE Search_Lambda SHALL 국내/해외 구분을 "미확인"으로 표시한다
6. THE CLOSELLER_System SHALL Platform_Map을 한 곳에서 관리하고 Platform_Map 분류 로직에 대한 단위 테스트를 둔다

### Requirement 11: 상품 유형과 일치도 등급

**User Story:** 사용자로서, 결과가 동일 상품인지 유사 상품인지, 그리고 얼마나 일치하는지 알고 싶다. 그래야 결과를 신뢰할지 판단할 수 있다.

#### Acceptance Criteria

1. WHERE SerpApi_Service 결과 유형이 상품 식별자 일치 또는 판매처 상품 페이지로 직접 연결되는 상품 결과임을 나타내면, THE Search_Lambda SHALL 해당 결과를 "동일 상품 후보"로 구분한다
2. IF 동일 상품 후보로 구분할 근거가 없으면, THEN THE Search_Lambda SHALL 해당 결과를 "유사 상품"으로 구분한다
3. WHEN 결과가 "동일 상품 후보"이면, THE Search_Lambda SHALL 결과 순위가 1~3위이면 Match_Grade를 "높음", 4~10위이면 "보통", 11위 이상이면 "낮음"으로 산정한다
4. WHEN 결과가 "유사 상품"이면, THE Search_Lambda SHALL 결과 순위가 1~3위이면 Match_Grade를 "보통", 4위 이상이면 "낮음"으로 산정한다
5. IF 결과의 순위 값이 없거나 유효하지 않으면, THEN THE Search_Lambda SHALL Match_Grade를 "낮음"으로 산정한다
6. THE Search_Lambda SHALL Match_Grade에 숫자 점수를 사용하지 않고 값을 "높음", "보통", "낮음" 중 하나로만 산정한다
7. THE CLOSELLER_System SHALL Match_Grade가 결과 유형과 순위 기반 휴리스틱임을 코드 주석과 ABOUT 화면에 명시한다

### Requirement 12: 원본 이미지 삭제

**User Story:** 사용자로서, 내 사진이 검색 후 서버에 남지 않길 원한다. 그래야 내 데이터가 보호된다.

#### Acceptance Criteria

1. WHEN Search_Lambda가 검색 처리를 완료하면, THE Search_Lambda SHALL 성공과 실패 여부와 무관하게 Image_Bucket의 원본 이미지를 즉시 삭제한다
2. THE Image_Bucket SHALL 1일 후 객체를 삭제하는 Lifecycle 규칙을 적용한다

### Requirement 13: 검색 진행 상태 표시

**User Story:** 사용자로서, 검색이 진행되는 동안 현재 단계를 알고 싶다. 그래야 기다리는 동안 무슨 일이 일어나는지 알 수 있다.

#### Acceptance Criteria

1. WHILE 검색이 진행 중이면, THE Frontend SHALL 진행 상태를 UPLOADING IMAGE, SEARCHING MARKETPLACES, MATCHING PRODUCTS, RESULTS READY 순서로 표시한다
2. WHEN 검색 결과가 준비되면, THE Frontend SHALL RESULTS READY 상태로 전환하고 RESULTS 화면을 표시한다

### Requirement 14: 결과 화면 상품 카드

**User Story:** 사용자로서, 검색 결과를 상품 카드로 보고 원본 판매 페이지로 이동하고 싶다. 그래야 실제로 구매할 수 있다.

#### Acceptance Criteria

1. WHEN RESULTS 화면이 표시되면, THE Frontend SHALL 각 결과를 Product_Card로 표시한다
2. THE Product_Card SHALL 상품 이미지, 상품명, 판매 플랫폼, 가격+통화 또는 "미확인", 동일상품후보/유사상품 배지, Match_Grade 등급, 원본 판매 페이지 이동 버튼을 표시한다
3. WHERE 결과에 브랜드 정보가 있으면, THE Product_Card SHALL 브랜드를 표시한다
4. WHEN 사용자가 원본 판매 페이지 이동 버튼을 누르면, THE Frontend SHALL 해당 판매 페이지를 새 탭에서 연다

### Requirement 15: 결과 정렬

**User Story:** 사용자로서, 결과를 가격이나 일치도 기준으로 정렬하고 싶다. 그래야 원하는 상품을 빠르게 찾을 수 있다.

#### Acceptance Criteria

1. WHEN 사용자가 가격 낮은순 정렬을 선택하면, THE Frontend SHALL 가격이 "미확인"이 아닌 결과를 가격 숫자값 오름차순으로 정렬한다
2. WHEN 사용자가 가격 높은순 정렬을 선택하면, THE Frontend SHALL 가격이 "미확인"이 아닌 결과를 가격 숫자값 내림차순으로 정렬한다
3. WHILE 가격 기준 정렬이 적용된 상태이면, THE Frontend SHALL 가격이 "미확인"인 모든 결과를 가격이 "미확인"이 아닌 모든 결과보다 뒤에 배치한다
4. WHILE 가격 기준 정렬이 적용된 상태에서 서로 다른 통화의 가격이 섞여 있으면, THE Frontend SHALL 환율 변환 없이 각 결과를 반환된 통화 그대로 표시하고 통화 구분 없이 가격 숫자값만으로 정렬하며, 결과 목록 상단에 통화가 혼재되어 직접 비교가 불가함을 알리는 안내 문구를 표시한다
5. WHEN 사용자가 일치도 높은순 정렬을 선택하면, THE Frontend SHALL 결과를 Match_Grade 등급을 높음 > 보통 > 낮음 순서로 정렬한다
6. IF 가격 정렬에서 두 결과의 가격 숫자값이 같거나 일치도 정렬에서 두 결과의 Match_Grade 등급이 같으면, THEN THE Frontend SHALL 두 결과를 원본 검색 결과에서의 기존 순서(안정 정렬)로 유지한다
7. WHEN 결과 목록이 처음 표시되고 사용자가 정렬 기준을 선택하지 않았으면, THE Frontend SHALL 기본값으로 일치도 높은순(Match_Grade 등급 높음 > 보통 > 낮음) 정렬을 적용한다

### Requirement 16: 결과 필터

**User Story:** 사용자로서, 결과를 조건별로 거르고 싶다. 그래야 관심 있는 결과만 볼 수 있다.

#### Acceptance Criteria

1. WHEN 사용자가 국내 또는 해외 필터를 선택하면, THE Frontend SHALL 선택한 구분에 해당하는 결과만 표시한다
2. WHEN 사용자가 동일상품후보 또는 유사상품 필터를 선택하면, THE Frontend SHALL 선택한 유형에 해당하는 결과만 표시한다
3. WHEN 사용자가 판매 플랫폼 필터를 선택하면, THE Frontend SHALL 선택한 플랫폼에 해당하는 결과만 표시한다

### Requirement 17: 오류 화면

**User Story:** 사용자로서, 문제가 생겼을 때 무슨 일인지 구분해서 알고 싶다. 그래야 다음에 무엇을 할지 판단할 수 있다.

#### Acceptance Criteria

1. IF 이미지 업로드가 실패하면, THEN THE Frontend SHALL 업로드 실패 전용 안내 메시지를 표시한다
2. IF 검색 처리가 시간 초과되면, THEN THE Frontend SHALL 시간 초과 전용 안내 메시지를 표시한다
3. IF 검색 결과가 없으면, THEN THE Frontend SHALL 결과 없음 전용 안내 메시지를 표시한다
4. IF 호출 한도를 초과하면, THEN THE Frontend SHALL 한도 초과 전용 안내 메시지를 표시한다

### Requirement 18: 화면 구성

**User Story:** 사용자로서, 일관된 화면 구조로 서비스를 이용하고 싶다. 그래야 서비스를 쉽게 탐색할 수 있다.

#### Acceptance Criteria

1. THE Frontend SHALL HOME, VISUAL SEARCH, RESULTS, ARCHIVE, ABOUT 화면을 제공한다
2. WHEN 사용자가 ARCHIVE 화면에 접근하면, THE Frontend SHALL "COMING SOON" 안내만 표시한다
3. THE Frontend SHALL 럭셔리 패션 에디토리얼 디자인 규칙(배경 #0A0A0A, 보조 배경 #181818, 글자 #F5F5F5, 포인트 #C5F277, 모노톤, 큰 볼드 타이포)을 적용한다
4. THE Frontend SHALL 모바일과 PC 반응형 레이아웃을 제공한다

### Requirement 19: 테스트 모드

**User Story:** 개발자로서, API Key 없이도 로컬에서 전체 흐름을 확인하고 싶다. 그래야 외부 호출 비용 없이 개발과 검증을 할 수 있다.

#### Acceptance Criteria

1. WHERE 환경변수 `USE_MOCK_SEARCH`가 true이면, THE Search_Lambda SHALL SerpApi_Service를 호출하지 않고 고정 테스트 데이터를 반환한다
2. WHEN Mock_Mode에서 결과를 반환하면, THE Search_Lambda SHALL 각 결과에 source 값 "MOCK"을 포함한다
3. WHEN Frontend가 source "MOCK" 결과를 표시하면, THE Frontend SHALL 해당 결과에 "TEST DATA" 배지를 표시한다
4. WHEN Frontend가 source "MOCK" 결과를 표시하면, THE Frontend SHALL 해당 결과의 구매 버튼을 비활성화한다
5. THE Search_Lambda SHALL 테스트 데이터에 실제 상점처럼 보이는 가짜 판매 링크를 포함하지 않는다
6. WHERE 환경변수 `USE_MOCK_SEARCH`가 true이면, THE CLOSELLER_System SHALL API Key 없이 업로드, 크롭, 결과 표시의 전체 흐름을 로컬에서 수행한다

### Requirement 20: 인프라 정의 (AWS SAM)

**User Story:** 운영자로서, 인프라를 코드로 정의하고 싶다. 그래야 비용과 보안 규칙을 일관되게 적용할 수 있다.

#### Acceptance Criteria

1. THE CLOSELLER_System SHALL Image_Bucket을 비공개(Block Public Access), 서버 측 암호화, 허용 출처를 파라미터로 받는 CORS, 1일 후 객체 삭제 Lifecycle로 정의한다
2. THE CLOSELLER_System SHALL Cache_Table과 Counter_Table을 Provisioned 방식의 작은 용량과 TTL로 정의한다
3. THE CLOSELLER_System SHALL Upload_Lambda와 Search_Lambda를 각각 최소 권한 IAM, 작은 메모리, 짧은 타임아웃으로 정의한다
4. THE CLOSELLER_System SHALL API_Gateway HTTP API에 `POST /uploads`와 `POST /search` 라우트, 스로틀, CORS를 정의한다
5. THE CLOSELLER_System SHALL SerpApi Key를 template.yaml에 값으로 넣지 않고 Parameter_Store SecureString에서 런타임에 읽도록 정의한다
6. THE CLOSELLER_System SHALL CloudWatch 로그 보존 기간을 14일로 정의한다
7. THE CLOSELLER_System SHALL amplify.yml에서 frontend 디렉터리를 Amplify Hosting으로 빌드하도록 정의한다
8. THE CLOSELLER_System SHALL IAM 정책 리소스에 와일드카드(*)를 사용하지 않는다
9. THE CLOSELLER_System SHALL 상시 켜져 있는 유료 리소스(EC2, RDS, NAT Gateway 등)를 정의하지 않는다

### Requirement 21: 환경 설정과 비밀값 보호

**User Story:** 개발자로서, 설정을 환경변수로 받고 비밀값을 코드에 남기지 않고 싶다. 그래야 보안 규칙을 지킬 수 있다.

#### Acceptance Criteria

1. THE CLOSELLER_System SHALL 리전, 월간 호출 상한, IP별 일일 호출 상한, API Gateway 스로틀 값, `USE_MOCK_SEARCH`를 환경변수로 받는다
2. THE CLOSELLER_System SHALL `.env.example` 파일을 제공한다
3. THE CLOSELLER_System SHALL `.env`를 `.gitignore`에 포함한다
4. THE CLOSELLER_System SHALL API Key와 AWS 자격 증명을 코드, 로그, 커밋에 포함하지 않는다
5. THE Frontend SHALL 외부 API Key를 포함하지 않는다
6. THE CLOSELLER_System SHALL 외부 API 호출을 Search_Lambda에서만 수행한다

### Requirement 22: 문서화

**User Story:** 팀원으로서, 설정과 비용과 외부 서비스에 대한 문서를 보고 싶다. 그래야 초보자도 따라 할 수 있고 규칙을 이해할 수 있다.

#### Acceptance Criteria

1. THE CLOSELLER_System SHALL README.md를 제공한다
2. THE CLOSELLER_System SHALL `docs/setup-guide.md`를 Windows PowerShell 기준의 초보자용 단계별 안내(AWS 계정, 루트 계정 보호, IAM, AWS CLI/SAM CLI 설치, SerpApi 가입과 Key 발급, SSM Key 등록, AWS Budgets 알림, 배포 순서, 정리 방법)로 제공한다
3. THE CLOSELLER_System SHALL `docs/external-services.md`에 SerpApi의 역할, 사용 이유, 무료 한도(월 250회, 시간당 50회)를 기록한다
4. THE CLOSELLER_System SHALL `docs/aws-free-tier.md`에 서비스별 Free Tier 조사 결과를 기록하고 불확실한 항목을 "확인 필요"로 표시한다
5. THE CLOSELLER_System SHALL `docs/cost-and-budgets.md`를 제공한다
6. THE CLOSELLER_System SHALL 설명과 문서를 한국어로 작성하고 명령어를 Windows PowerShell 기준으로 작성한다

### Requirement 23: 승인 전 외부/비용 작업 보류

**User Story:** 프로젝트 소유자로서, 비용이 발생하거나 되돌리기 어려운 작업은 내 승인 후에만 실행되길 원한다. 그래야 예상치 못한 비용과 변경을 막을 수 있다.

#### Acceptance Criteria

1. IF 작업이 sam deploy, AWS 리소스 생성/변경/삭제, 또는 실제 SerpApi_Service 호출에 해당하면, THEN THE CLOSELLER_System SHALL 사용자 승인 전에 해당 작업을 실행하지 않고 명령어와 예상 영향만 제시한다
2. THE CLOSELLER_System SHALL 로컬 파일 생성, 빌드, 테스트, sam validate, sam build를 사용자 승인 없이 수행한다

### Requirement 24: 완료 검증

**User Story:** 개발자로서, 구현 후 정해진 검증을 실제로 실행하고 결과를 투명하게 보고하고 싶다. 그래야 품질을 확인하고 실패를 숨기지 않는다.

#### Acceptance Criteria

1. WHEN 구현이 완료되면, THE CLOSELLER_System SHALL `npm run build`와 타입 검사를 통과한다
2. WHEN 구현이 완료되면, THE CLOSELLER_System SHALL 파일 검증, 도메인 분류, 정규화, 중복 제거, 가격 파싱, 호출 제한에 대한 백엔드 단위 테스트를 통과한다
3. WHEN 구현이 완료되면, THE CLOSELLER_System SHALL sam validate와 sam build를 통과한다
4. WHEN Mock_Mode로 실행하면, THE CLOSELLER_System SHALL 업로드부터 크롭, 결과 화면까지의 흐름을 로컬에서 동작시킨다
5. WHEN 검증을 실행하면, THE CLOSELLER_System SHALL 실행한 검증 명령과 결과 요약을 보고한다
