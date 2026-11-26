---
inclusion: always
---

# CLOSELLER 프로젝트 규칙

## 서비스
- 이름: CLOSELLER. 패션 사진을 올리면 사진 속 옷과 같거나 비슷한 실제 판매 상품(신품, 중고)을 찾아 구매 링크를 보여주는 서비스.
- 이 프로젝트는 팀 프로젝트이고, 서비스가 실제로 돌아가는 곳은 AWS다.

## 인프라 원칙
- 호스팅, 백엔드, DB, 파일 저장은 모두 AWS에서 한다. Supabase와 Firebase는 쓰지 않는다.
- GCP, Azure는 쓰기 전에 반드시 나에게 먼저 묻는다.
- AWS 밖의 외부 서비스(예: SerpApi)를 쓰면 docs/external-services.md에 역할, 이유, 무료 한도를 적는다.
- Kiro, GitHub, Notion은 개발과 기록 도구이고 AWS는 서비스가 실제로 실행되는 기반이다. 문서에서 둘을 구분해서 쓴다.
- 사용하는 AWS 서비스의 Free Tier 지원 여부와 한도를 공식 문서 기준으로 조사해 docs/aws-free-tier.md에 정리한다. 확실하지 않으면 "확인 필요"라고 쓴다.

## 기술 스택
- 프론트엔드: React, TypeScript, Vite, Tailwind CSS, AWS Amplify Hosting
- 백엔드: AWS Lambda(Python), API Gateway(HTTP API), S3, DynamoDB
- 인프라 코드: AWS SAM(template.yaml)
- 외부 검색: SerpApi Google Lens API
- 리전: 서울(ap-northeast-2). 리전과 모델 ID는 환경변수로 바꿀 수 있게 한다.
- 단계별 개발: 지금 요청한 단계의 기능만 만든다. 요청하지 않은 기능(Bedrock, Cognito 등)은 미리 만들지 않는다.

## 비용 규칙
- 상시 켜져 있는 유료 리소스(EC2, RDS, NAT Gateway 등)는 만들지 않는다.
- DynamoDB는 Provisioned 방식의 작은 용량을 쓴다 (무료 한도 대상).
- 비밀값(API Key) 보관은 SSM Parameter Store SecureString을 쓴다. Secrets Manager는 쓰기 전에 나에게 묻는다.
- CloudWatch 로그 보존 기간은 14일.
- SerpApi 무료 플랜은 월 250회다. 캐싱과 호출 횟수 제한을 항상 적용한다.

## 승인 규칙 (중요)
- 아래 작업은 내가 승인하기 전에는 실행하지 말고, 명령어와 예상 영향만 보여주고 기다린다.
  - sam deploy, AWS 리소스를 만들거나 바꾸거나 지우는 모든 명령
  - 비용이 발생할 수 있는 작업, 실제 SerpApi 호출
- 로컬 파일 생성, 빌드, 테스트, sam validate, sam build는 승인 없이 해도 된다.
- API Key와 AWS 자격 증명은 코드, 로그, 커밋, 채팅 어디에도 남기지 않는다.

## 보안 규칙
- API Key는 프론트엔드에 넣지 않는다. 외부 API는 Lambda에서만 호출한다.
- S3는 비공개(Block Public Access, 서버 측 암호화). 이미지 접근은 5분짜리 Presigned URL만 쓴다.
- 업로드 검증은 서버에서 한다: JPG, PNG, WEBP만, 최대 10MB, 실제 파일 내용(매직 바이트) 확인.
- IAM은 최소 권한으로 쓰고, 리소스에 *를 쓰지 않는다. CORS 허용 출처를 명시한다.
- 업로드 이미지는 검색 처리가 끝나면 바로 삭제하고, S3 Lifecycle(1일)로 한 번 더 지운다.
- 외부 검색 서비스로 사진이 전송된다는 사실을 업로드 전에 안내하고 동의를 받는다.

## 데이터 정직성 규칙
- 상품 링크는 실제 검색 API가 돌려준 URL만 쓴다. 링크, 상품, 가격을 지어내지 않는다.
- 가격이나 판매 상태를 알 수 없으면 "미확인"으로 표시한다.
- 알 수 없는 브랜드, 제품명, 품번은 "추정" 또는 "식별 불가"로 표시한다.
- 근거 없는 숫자 점수를 만들지 않는다. 일치도는 근거가 있는 등급(높음/보통/낮음)으로 표시한다.
- 테스트 데이터는 source: "MOCK"으로 표시하고 화면에 "TEST DATA" 배지를 붙이며, 구매 버튼은 비활성화한다.
- 사진 속 사람(연예인 포함)이 누구인지 식별하거나 추측하지 않는다. 의류와 액세서리만 분석한다.
- 판매 플랫폼의 이용약관을 지키고, 비공개 API나 무단 크롤링을 쓰지 않는다.

## 디자인 규칙
- 럭셔리 패션 에디토리얼 스타일(Saint Laurent, The Row, Vogue, SSENSE 감성). 흔한 AI 쇼핑몰처럼 보이지 않게 한다.
- 색상: 배경 #0A0A0A, 보조 배경 #181818, 글자 #F5F5F5, 포인트 #C5F277
- 큰 볼드 타이포, 모노톤, 은은한 필름 그레인. 네온, 그라데이션, 과한 그림자 금지.
- 상품 이미지 중심 그리드, 자연스러운 호버, 모바일과 PC 반응형.
- 메인 문구(그대로 사용): CLOSELLER. / FIND WHAT THEY WEAR. / UPLOAD. IDENTIFY. DISCOVER. / 사진 한 장으로 당신이 찾던 옷을 발견하세요.
- 화면: HOME, VISUAL SEARCH, RESULTS, ARCHIVE, ABOUT

## 코드와 문서 규칙
- TypeScript strict. 백엔드의 검증, 정규화, 분류 로직은 핸들러와 분리해서 단위 테스트를 쓴다.
- 설정은 환경변수로 받고 .env.example을 제공한다. .env는 .gitignore에 넣는다.
- 외부 API 실패, 시간 초과, 결과 없음, 한도 초과는 각각 알아보기 쉬운 메시지로 보여준다.
- 폴더: frontend/, backend/, docs/, template.yaml, amplify.yml, .env.example, README.md
- 설명과 문서는 한국어, 명령어는 Windows PowerShell 기준.
- 내가 직접 해야 하는 일(AWS 계정, IAM, API Key 발급과 등록)은 초보자도 따라 할 수 있게 단계별로 설명한다.
- 구현 후에는 빌드와 테스트를 실제로 실행해서 결과를 그대로 보고한다. 실패는 숨기지 않는다.