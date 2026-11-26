# CLOSELLER 설치 및 배포 가이드 (초보자용)

> 대상: AWS를 처음 쓰는 분. 모든 명령어는 **Windows PowerShell** 기준입니다.
> (충족 요구사항: Req 22.2, Req 22.6 — 한국어 설명 · PowerShell 명령어)

이 문서는 위에서 아래로 순서대로 따라 하면 됩니다. 중간에 건너뛰지 마세요.
특히 **🔒 승인 필요** 라고 표시된 단계는 실제 AWS 리소스를 만들어 **비용이 발생**할 수 있으므로,
내용을 이해하고 직접 실행 여부를 결정한 뒤에만 진행하세요.

사용하는 리전(Region)은 전부 **`ap-northeast-2` (서울)** 로 통일합니다.

---

## 1. AWS 계정 생성

1. 웹 브라우저에서 <https://aws.amazon.com/ko/> 에 접속합니다.
2. 오른쪽 위 **[AWS 계정 생성]** 버튼을 클릭합니다.
3. 다음 정보를 입력합니다.
   - 이메일 주소 (로그인에 쓰는 **루트 계정** 이메일)
   - 계정 이름 (예: `closeller-personal`)
4. 결제 정보로 **신용/체크카드**를 등록합니다. (프리 티어라도 카드 등록은 필수입니다.)
5. 휴대폰 문자 또는 음성 통화로 **본인 확인**을 완료합니다.
6. 지원 플랜은 **[기본 지원 - 무료]** 를 선택합니다.
7. 가입이 끝나면 **AWS Management Console** 에 로그인할 수 있습니다.

> 💡 지금 로그인한 이 계정이 **루트(root) 계정**입니다. 다음 단계에서 꼭 보호하세요.

---

## 2. 루트 계정 보호

루트 계정은 모든 권한을 가진 **가장 위험한 계정**입니다. 탈취되면 요금 폭탄이 날 수 있습니다.

### 2-1. 루트 계정에 MFA(다단계 인증) 활성화

1. 콘솔 오른쪽 위 계정 이름 → **[보안 자격 증명(Security credentials)]** 클릭.
2. **[다단계 인증(MFA)]** 섹션에서 **[MFA 디바이스 할당]** 클릭.
3. **인증 앱(Authenticator app)** 방식을 선택합니다.
   - 휴대폰에 **Google Authenticator** 또는 **Microsoft Authenticator** 앱을 설치합니다.
4. 화면의 QR 코드를 앱으로 스캔하고, 앱에 나오는 **6자리 코드 2개를 연속으로** 입력해 등록을 마칩니다.
5. 등록 후 로그아웃했다가 다시 로그인하여 MFA가 정상 동작하는지 확인합니다.

### 2-2. 루트 계정 일상 사용 금지

- 루트 계정은 **MFA 설정, 결제 정보 변경** 등 꼭 필요한 경우에만 사용합니다.
- 평소 개발·배포 작업은 **3단계에서 만드는 IAM 작업용 사용자**로 합니다.
- 루트 계정의 **액세스 키는 절대 만들지 않습니다.** (이미 있다면 삭제하세요.)

---

## 3. IAM 사용자/역할 생성 (작업용 사용자)

실제 작업은 루트 계정 대신 **권한이 제한된 IAM 사용자**로 합니다.

1. 콘솔 상단 검색창에 `IAM` 입력 → **IAM** 서비스로 이동.
2. 왼쪽 메뉴 **[사용자(Users)]** → **[사용자 생성(Create user)]** 클릭.
3. 사용자 이름을 입력합니다. (예: `closeller-dev`)
4. 권한 설정에서 **[직접 정책 연결(Attach policies directly)]** 선택.
   - 처음 배우는 단계라면 `AdministratorAccess` 를 붙이면 편하지만,
     **최소 권한 원칙**상 실제로는 아래처럼 필요한 서비스 권한만 주는 것이 안전합니다.
     - `AWSCloudFormationFullAccess` (SAM 배포)
     - `AWSLambda_FullAccess`
     - `AmazonAPIGatewayAdministrator`
     - `AmazonS3FullAccess`
     - `AmazonDynamoDBFullAccess`
     - `CloudWatchLogsFullAccess`
     - `AmazonSSMFullAccess` (파라미터 등록·조회)
     - `IAMFullAccess` (배포 중 역할 생성에 필요)
   - 운영 환경으로 넘어갈 때는 위 권한을 더 좁게 조정하세요.
5. 사용자 생성 후, 해당 사용자 → **[보안 자격 증명]** 탭 → **[액세스 키 만들기]**.
   - 사용 사례는 **[Command Line Interface (CLI)]** 선택.
   - 생성된 **액세스 키 ID**와 **비밀 액세스 키(Secret access key)** 를 안전한 곳에 저장합니다.
     (비밀 키는 이 화면을 벗어나면 다시 볼 수 없습니다.)

> ⚠️ 액세스 키는 비밀번호와 같습니다. **코드나 깃(Git) 커밋에 절대 넣지 마세요.**
> 다음 4단계의 `aws configure` 로만 로컬 PC에 저장합니다.

---

## 4. AWS CLI 설치 및 구성 (Windows)

### 4-1. 설치

PowerShell에서 다음을 실행하면 AWS CLI를 설치할 수 있습니다.

```powershell
msiexec.exe /i https://awscli.amazonaws.com/AWSCLIV2.msi
```

> 설치 마법사 창이 뜨면 **Next → Next → Install** 로 진행합니다.
> 설치 후에는 PowerShell 창을 **닫았다가 새로 열어야** `aws` 명령어가 인식됩니다.

### 4-2. 설치 확인

```powershell
aws --version
```

`aws-cli/2.x.x ...` 처럼 버전이 출력되면 성공입니다.

### 4-3. 자격 증명 구성

3단계에서 발급한 액세스 키로 CLI를 구성합니다.

```powershell
aws configure
```

프롬프트가 나오면 다음을 입력합니다.

- **AWS Access Key ID**: (3단계에서 받은 액세스 키 ID)
- **AWS Secret Access Key**: (3단계에서 받은 비밀 액세스 키)
- **Default region name**: `ap-northeast-2`
- **Default output format**: `json`

구성이 잘 됐는지 확인합니다.

```powershell
aws sts get-caller-identity
```

본인 계정 정보(UserId, Account, Arn)가 나오면 성공입니다.

---

## 5. AWS SAM CLI 설치 (Windows)

SAM(Serverless Application Model) CLI는 Lambda/API Gateway 등을 쉽게 배포하는 도구입니다.

### 5-1. 설치

1. 브라우저에서 <https://github.com/aws/aws-sam-cli/releases/latest> 로 이동.
2. `AWS_SAM_CLI_64_PY3.msi` (Windows 64비트 설치 파일)을 내려받아 실행합니다.
3. 설치 마법사를 **Next → Install** 로 진행합니다.
4. 설치 후 PowerShell 창을 **새로 엽니다.**

### 5-2. 설치 확인

```powershell
sam --version
```

`SAM CLI, version 1.x.x` 처럼 출력되면 성공입니다.

---

## 6. SerpApi 가입 및 API Key 발급

이 프로젝트는 이미지 검색(Google Lens)을 위해 **SerpApi** 라는 외부 서비스를 사용합니다.

1. 브라우저에서 <https://serpapi.com/> 에 접속해 **회원가입**합니다.
2. 로그인 후 대시보드의 **[Your Private API Key]** 에서 **API Key** 를 복사합니다.
3. 이 프로젝트가 사용하는 API는 **Google Lens API** 입니다.

### 무료 한도 (중요)

- 무료 플랜 기준 대략 **월 250회**, **시간당 50회** 호출 제한이 있습니다.
- 한도를 넘지 않도록 백엔드에서 호출 횟수를 제한합니다. (`.env`의 `MONTHLY_CALL_LIMIT`, `IP_DAILY_LIMIT`)
- SerpApi의 역할·사용 이유·한도에 대한 자세한 설명은 [`docs/external-services.md`](./external-services.md) 를 참고하세요.

> ⚠️ 복사한 API Key는 **코드나 `.env` 파일에 직접 넣지 않습니다.**
> 다음 7단계처럼 **AWS SSM Parameter Store** 에만 보관합니다.

---

## 7. SSM Parameter Store에 SerpApi Key 등록

API Key 같은 비밀값은 AWS **SSM Parameter Store** 에 암호화(SecureString)해서 저장합니다.
코드와 `.env` 에는 **파라미터 경로만** 적고 실제 값은 넣지 않습니다.

PowerShell에서 다음을 실행합니다. (`<YOUR_SERPAPI_KEY>` 부분을 6단계에서 복사한 실제 Key로 바꾸세요.)

```powershell
aws ssm put-parameter --name "/closeller/serpapi/api-key" --type SecureString --value "<YOUR_SERPAPI_KEY>" --region ap-northeast-2
```

등록이 잘 됐는지 확인합니다. (`--with-decryption` 없이 메타데이터만 확인하는 것이 안전합니다.)

```powershell
aws ssm get-parameter --name "/closeller/serpapi/api-key" --region ap-northeast-2
```

> ⚠️ **핵심 보안 규칙**
> - API Key 값은 **코드/깃 커밋에 넣지 말고 SSM에만** 보관합니다.
> - `.env` 파일에는 **파라미터 경로만** 지정합니다.
>   ```
>   SERP_API_KEY_SSM_PARAM=/closeller/serpapi/api-key
>   ```
> - 파라미터 이름과 리전은 `.env.example` 과 **반드시 동일**하게 유지합니다
>   (`/closeller/serpapi/api-key`, 리전 `ap-northeast-2`).

---

## 8. AWS Budgets 비용 알림 설정

예상치 못한 요금을 막기 위해 **예산(Budget)** 과 **알림**을 설정합니다.

1. 콘솔 상단 검색창에 `Budgets` 입력 → **AWS Budgets** 로 이동.
2. **[예산 생성(Create budget)]** 클릭.
3. 템플릿은 **[월별 비용 예산(Monthly cost budget)]** 을 선택합니다.
4. 예산 금액을 입력합니다. (예: 월 `5 USD` — 개인 학습용으로 충분히 낮게)
5. **알림 임계값(Alert threshold)** 을 설정합니다.
   - 예: 실제 비용이 예산의 **50%** 도달 시 알림
   - 예: 실제 비용이 예산의 **80%** 도달 시 알림
   - 예: 실제 비용이 예산의 **100%** 도달 시 알림
6. 알림을 받을 **이메일 주소**를 입력하고 예산을 저장합니다.

> 비용 설계와 예산 전략에 대한 상세 내용은 [`docs/cost-and-budgets.md`](./cost-and-budgets.md) 를 참고하세요.

---

## 9. 배포 순서

여기까지 준비가 끝났다면 아래 순서로 배포합니다.

### 9-1. 환경변수 파일 준비

프로젝트 루트에서 `.env.example` 을 복사해 `.env` 를 만들고 값을 채웁니다.

```powershell
Copy-Item .env.example .env
```

- `.env` 는 깃에 커밋되지 않습니다. (`.gitignore` 에 포함)
- `SERP_API_KEY_SSM_PARAM` 은 `/closeller/serpapi/api-key` 로, `AWS_REGION` 은 `ap-northeast-2` 로 둡니다.
- `VITE_API_BASE_URL` 은 **배포 후(9-4)** 에 실제 엔드포인트로 채웁니다.

### 9-2. 로컬 검증 (승인 불필요 — 비용 없음)

템플릿 문법을 검증하고 빌드합니다. 이 단계는 AWS 리소스를 만들지 않으므로 안전합니다.

```powershell
sam validate
sam build
```

둘 다 성공(에러 없음)해야 다음으로 넘어갑니다.

### 9-3. 🔒 승인 필요 — 실제 배포

> ⚠️ **경고: 이 단계부터 실제 AWS 리소스가 생성되어 비용이 발생할 수 있습니다.**
> `sam deploy` 는 **S3 버킷, DynamoDB 테이블, Lambda 함수, API Gateway, CloudWatch 로그 그룹** 등을 생성합니다.
> 이 작업은 **되돌리기(삭제) 전까지 과금**될 수 있고, 리소스 생성에 영향이 큽니다.
> **내용을 이해하고 직접 실행을 결정하기 전에는 아래 명령을 실행하지 마세요.**

처음 배포할 때는 안내형(guided) 모드로 진행합니다.

```powershell
sam deploy --guided
```

프롬프트에서 다음을 입력합니다.

- **Stack Name**: `closeller` (원하는 이름)
- **AWS Region**: `ap-northeast-2`
- 나머지는 기본값으로 진행하고, 마지막에 변경 사항(changeset) 확인 후 배포를 승인합니다.

두 번째부터는 저장된 설정으로 간단히 배포할 수 있습니다.

```powershell
sam deploy
```

### 9-4. 프론트엔드 연결 및 배포

1. 배포가 끝나면 출력(Outputs)에 **API Gateway 엔드포인트 URL** 이 표시됩니다.
2. 이 URL을 프론트엔드 환경변수 `VITE_API_BASE_URL` 에 설정합니다. (`.env` 수정)

   ```
   VITE_API_BASE_URL=https://실제-api-id.execute-api.ap-northeast-2.amazonaws.com
   ```
3. 프론트엔드를 빌드합니다.

   ```powershell
   npm run build
   ```
4. 빌드 결과물을 **AWS Amplify** 로 배포합니다. (리포지토리 연결 시 `amplify.yml` 설정에 따라 자동 빌드·배포됩니다.)

---

## 10. 정리(삭제) 방법

> ⚠️ **리소스를 남겨두면 계속 비용이 발생할 수 있습니다.**
> 학습이나 테스트가 끝났다면 아래 순서로 반드시 정리하세요.

### 10-1. SAM 스택 삭제

배포로 만든 리소스(Lambda, API Gateway, DynamoDB, 로그 그룹 등)를 한 번에 삭제합니다.

```powershell
sam delete
```

- Stack Name을 물어보면 배포 때 사용한 이름(예: `closeller`)을 입력합니다.
- 삭제 확인 질문에 모두 `y` 로 답합니다.

### 10-2. S3 버킷 비우기

S3 버킷에 객체가 남아 있으면 스택 삭제가 실패할 수 있습니다.
콘솔에서 해당 버킷을 열어 **[비우기(Empty)]** 후 **[삭제(Delete)]** 합니다.
CLI로 비우려면 다음을 사용할 수 있습니다. (버킷 이름을 실제 값으로 바꾸세요.)

```powershell
aws s3 rm s3://<YOUR_BUCKET_NAME> --recursive --region ap-northeast-2
```

### 10-3. SSM 파라미터 삭제

7단계에서 등록한 SerpApi Key 파라미터를 삭제합니다.

```powershell
aws ssm delete-parameter --name "/closeller/serpapi/api-key" --region ap-northeast-2
```

### 10-4. Budgets 정리

더 이상 필요 없으면 콘솔의 **AWS Budgets** 에서 8단계에 만든 예산을 삭제합니다.

### 10-5. 최종 확인

- 콘솔에서 Lambda, API Gateway, DynamoDB, S3, CloudWatch 로그 그룹이 모두 삭제됐는지 확인합니다.
- 며칠 뒤 **AWS Billing(결제)** 대시보드에서 예상치 못한 과금이 없는지 다시 확인합니다.

---

### 참고 문서

- 외부 서비스(SerpApi) 상세: [`docs/external-services.md`](./external-services.md)
- 비용·예산 설계: [`docs/cost-and-budgets.md`](./cost-and-budgets.md)
- AWS 프리 티어 조사: [`docs/aws-free-tier.md`](./aws-free-tier.md)
