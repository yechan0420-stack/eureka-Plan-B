# CLOSELLER

> FIND WHAT THEY WEAR. — 사진 한 장으로 당신이 찾던 옷을 발견하세요.

CLOSELLER는 패션 사진을 올리면 사진 속 옷과 **같거나 비슷한 실제 판매 상품(신품·중고)** 을 찾아
구매 링크를 보여주는 서비스입니다. 이미지 검색에는 SerpApi의 Google Lens API를 사용하며,
호스팅·백엔드·DB·파일 저장은 모두 AWS에서 동작합니다.

> ℹ️ 이 README는 스캐폴딩 단계(Task 1)의 시작용 개요입니다. 상세 실행·빌드·테스트 가이드는
> 이후 Task 24.1에서 보강됩니다.

## 기술 스택

- **프론트엔드**: React, TypeScript(strict), Vite, Tailwind CSS, AWS Amplify Hosting
- **백엔드**: AWS Lambda(Python), API Gateway(HTTP API), S3, DynamoDB
- **인프라 코드**: AWS SAM (`template.yaml`)
- **외부 검색**: SerpApi Google Lens API
- **리전**: 서울(`ap-northeast-2`)

## 폴더 구조

```
.
├── frontend/        # React + TypeScript + Vite 프론트엔드 (Amplify Hosting)
├── backend/         # Python Lambda 소스 및 테스트
├── docs/            # 설정 가이드, 외부 서비스, Free Tier, 비용 문서
├── template.yaml    # AWS SAM 인프라 정의
├── amplify.yml      # Amplify Hosting 빌드 설정
├── .env.example     # 환경변수 예시 (비밀값은 포함하지 않음)
└── .gitignore
```

## 환경변수

설정은 환경변수로 관리합니다. `.env.example`을 복사해 `.env`를 만들고 값을 채우세요
(`.env`는 커밋되지 않습니다).

```powershell
Copy-Item .env.example .env
```

> 🔒 **보안**: API Key와 AWS 자격 증명은 코드·커밋·로그 어디에도 넣지 않습니다.
> SerpApi Key는 AWS SSM Parameter Store(SecureString)에 보관하고, `.env`에는 그
> 파라미터 경로(`SERP_API_KEY_SSM_PARAM`)만 지정합니다.

## 개발 범위

본 저장소는 CLOSELLER **1차 MVP** 범위만 구현합니다.
(Bedrock, Cognito, 검색 기록·관심 상품 저장, 환율 변환 등은 포함하지 않습니다.)
