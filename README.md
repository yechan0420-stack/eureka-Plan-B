# CLOSELLER

> FIND WHAT THEY WEAR. — 사진 한 장으로 당신이 찾던 옷을 발견하세요.

## 프로젝트 개요

CLOSELLER는 패션 사진을 올리면 사진 속 옷과 **같거나 비슷한 실제 판매 상품(신품·중고)** 을
찾아 구매로 이어지는 링크를 보여주는 서비스입니다. 본 저장소는 **1차 MVP** 범위를 구현합니다.

사용자 흐름은 다음과 같습니다.

1. **업로드** — 사용자가 패션 사진을 올립니다.
2. **브라우저 크롭** — 브라우저 안(canvas)에서 원하는 영역만 잘라냅니다. 원본은 서버로 보내지 않고, 크롭 결과만 업로드합니다.
3. **외부 검색** — SerpApi의 Google Lens로 잘라낸 이미지를 외부 검색합니다.
4. **결과 표시** — 같거나 비슷한 상품을 카드 그리드로 보여줍니다(플랫폼·가격·일치도·원본 이동 버튼 등).

### 범위 (MVP)

본 저장소는 아래 범위만 다룹니다. 다음 기능은 **포함하지 않습니다.**

- Amazon Bedrock (AI 분석)
- Amazon Cognito (로그인·인증)
- 검색 기록·관심 상품 저장
- 환율 변환 (통화가 섞여도 변환하지 않고 숫자값 그대로 정렬하며, 섞였다는 안내만 표시)

## 기술 스택

- **프론트엔드**: React, TypeScript(`strict`), Vite, Tailwind CSS, AWS Amplify Hosting
- **백엔드**: AWS Lambda(Python), API Gateway(HTTP API), Amazon S3, Amazon DynamoDB, AWS SSM Parameter Store(SecureString)
- **인프라 코드**: AWS SAM (`template.yaml`)
- **외부 검색**: SerpApi Google Lens API
- **리전**: 서울(`ap-northeast-2`)

## 폴더 구조

```
.
├── frontend/        # React + TypeScript + Vite 프론트엔드 (Amplify Hosting)
├── backend/         # Python Lambda 소스(src/)와 테스트(tests/), pyproject.toml
├── docs/            # 설정 가이드, 외부 서비스, Free Tier, 비용 문서
├── template.yaml    # AWS SAM 인프라 정의 (S3, DynamoDB, Lambda, API Gateway)
├── amplify.yml      # Amplify Hosting 빌드 설정
├── .env.example     # 환경변수 예시 (비밀값은 포함하지 않음)
└── .gitignore
```

### 문서 (`docs/`)

상세한 설정·운영 정보는 `docs/` 아래 문서에서 다룹니다.

- [`docs/setup-guide.md`](docs/setup-guide.md) — Windows PowerShell 기준 초보자용 단계별 설정·배포·정리 가이드
- [`docs/external-services.md`](docs/external-services.md) — SerpApi의 역할·사용 이유·무료 한도
- [`docs/aws-free-tier.md`](docs/aws-free-tier.md) — 서비스별 AWS Free Tier 조사 결과
- [`docs/cost-and-budgets.md`](docs/cost-and-budgets.md) — 비용 설계와 예산 알림 안내

## 환경변수 설정

설정은 환경변수로 관리합니다. `.env.example`을 복사해 `.env`를 만들고 값을 채우세요
(`.env`는 `.gitignore`에 포함되어 커밋되지 않습니다).

```powershell
Copy-Item .env.example .env
```

주요 키는 다음과 같습니다.

| 키 | 설명 | 기본값 |
| --- | --- | --- |
| `AWS_REGION` | 사용 AWS 리전(서울) | `ap-northeast-2` |
| `MONTHLY_CALL_LIMIT` | 월간 전체 SerpApi 호출 상한 | `200` |
| `IP_DAILY_LIMIT` | IP별 일일 호출 상한 | `5` |
| `THROTTLE_RATE` | API Gateway 초당 요청 처리율(허용 범위 1~10,000) | `2` |
| `THROTTLE_BURST` | API Gateway 순간 버스트 허용량(허용 범위 1~10,000) | `5` |
| `USE_MOCK_SEARCH` | `true`면 외부 SerpApi를 호출하지 않고 고정 MOCK 데이터 반환 | `false` |
| `SERP_API_KEY_SSM_PARAM` | SerpApi Key가 저장된 SSM Parameter Store 파라미터 **경로**(Key 값 아님) | `/closeller/serpapi/api-key` |
| `VITE_API_BASE_URL` | 프론트엔드가 호출할 백엔드 API 베이스 URL(배포 후 API Gateway 엔드포인트로 교체) | — |

> 🔒 **보안**: API Key와 AWS 자격 증명은 코드·커밋·로그 어디에도 넣지 않습니다.
> SerpApi Key는 AWS SSM Parameter Store(SecureString)에 보관하고, `.env`에는 그
> 파라미터 **경로**(`SERP_API_KEY_SSM_PARAM`)만 지정합니다. 실제 Key 값은 어디에도 적지 않습니다.

## 로컬 실행·빌드·테스트 (Windows PowerShell)

아래 명령은 모두 Windows PowerShell 기준입니다.

### 프론트엔드 (`frontend/`)

```powershell
# 1) 의존성 설치
npm ci --prefix frontend

# 2) 개발 서버 실행
npm run dev --prefix frontend

# 3) 프로덕션 빌드 (tsc -b && vite build)
npm run build --prefix frontend

# 4) 테스트 실행 (vitest run)
npm run test --prefix frontend
```

> 참고: `frontend` 디렉터리로 이동해 실행해도 됩니다.
>
> ```powershell
> Set-Location frontend
> npm ci
> npm run dev
> ```

### 백엔드 (`backend/`)

```powershell
# backend 디렉터리에서 실행
Set-Location backend

# 1) 가상환경 생성
python -m venv .venv

# 2) 가상환경 활성화
.\.venv\Scripts\Activate.ps1

# 3) 개발·테스트 의존성 설치
pip install -r requirements-dev.txt

# 4) 테스트 실행 (pytest + hypothesis 속성 테스트 포함)
pytest
```

> PowerShell 실행 정책 때문에 `Activate.ps1` 실행이 막히면, 현재 세션에서만 아래로 허용할 수 있습니다.
>
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
> ```

### 인프라 로컬 검증 (승인 불필요)

`sam validate`와 `sam build`는 AWS 리소스를 만들지 않으므로 승인 없이 로컬에서 수행할 수 있습니다.

```powershell
# template.yaml 문법·구성 검증
sam validate

# 로컬 빌드 (배포하지 않음)
sam build
```

### Mock 로컬 E2E (API Key 없이)

`USE_MOCK_SEARCH=true`로 두면 외부 SerpApi를 호출하지 않고 고정 MOCK 데이터로
업로드 → 크롭 → 결과 화면 전체 흐름을 로컬에서 확인할 수 있습니다.

```powershell
# 현재 PowerShell 세션에서 Mock 모드 활성화
$env:USE_MOCK_SEARCH = "true"

# 로컬 API 실행 (SAM Local)
sam local start-api
```

## 승인 규칙

비용이 발생하거나 되돌리기 어려운 작업은 **사용자 승인 전에는 실행하지 않습니다.**

- `sam deploy` 및 AWS 리소스(S3 / DynamoDB / Lambda / API Gateway / 로그 그룹) 생성·변경·삭제
- 실제 SerpApi 호출(Key를 사용한 라이브 Google Lens 검색)

승인 없이 수행 가능한 작업: 로컬 파일 생성, 빌드, 테스트, `sam validate`, `sam build`.

> 📄 실제 배포 절차(AWS 계정 준비, IAM, AWS CLI/SAM CLI 설치, SerpApi Key 발급·SSM 등록,
> AWS Budgets 알림, 배포 순서, 정리 방법)는 [`docs/setup-guide.md`](docs/setup-guide.md)를 참조하세요.
