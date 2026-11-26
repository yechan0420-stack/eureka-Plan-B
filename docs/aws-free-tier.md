# AWS Free Tier(프리 티어) 조사 결과

## 개요

본 문서는 CLOSELLER가 사용하는 AWS 서비스별 Free Tier(프리 티어) 조사 결과를 정리한 것이다.

> ⚠️ **중요**: Free Tier 정책과 수치는 AWS에 의해 수시로 변동될 수 있다. 본 문서의 값은 작성 시점의 일반적인 정보에 기반하며, **최신 값은 반드시 AWS 공식 요금/프리 티어 페이지에서 재확인**해야 한다.
>
> - [AWS 프리 티어](https://aws.amazon.com/free/)
> - 각 서비스의 요금(Pricing) 페이지
>
> 확실하지 않은 항목은 아래 표에서 **"확인 필요"** 로 표시했다.

CLOSELLER가 사용하는 AWS 서비스(design.md / template.yaml 기준):

- AWS Lambda
- Amazon API Gateway (HTTP API)
- Amazon S3 (Image_Bucket)
- Amazon DynamoDB (Cache_Table, Counter_Table, Provisioned 소용량)
- Amazon CloudWatch Logs (로그 보존 14일)
- AWS Systems Manager(SSM) Parameter Store
- AWS Amplify Hosting

---

## 서비스별 Free Tier 요약

| 서비스 | Free Tier 요지 | CLOSELLER 사용 특성 | 비고 / 확인 필요 |
| --- | --- | --- | --- |
| **AWS Lambda** | 월 100만 요청 + 월 40만 GB-초 컴퓨팅 시간이 무료로 널리 알려져 있음(일반적으로 상시 무료로 소개됨). | 작은 메모리 할당과 짧은 타임아웃으로 요청당 컴퓨팅 소모를 최소화하여 사용. | **확인 필요**: 정확한 한도 수치, 상시 무료 여부(상시 무료 vs 12개월)는 공식 페이지에서 재확인. |
| **Amazon API Gateway (HTTP API)** | HTTP API에 대한 요청 기반 요금이 적용됨. 프리 티어 한도가 적용될 수 있음. | 프론트엔드 → 백엔드 진입점으로 HTTP API 사용. 요청 수가 낮게 유지됨. | **확인 필요**: 12개월 무료 한도 적용 여부와 월 무료 요청 수(HTTP API vs REST API 구분 포함)는 재확인 필요. |
| **Amazon S3 (Image_Bucket)** | 저장 용량 및 요청(GET/PUT 등)에 대한 무료 한도가 제공됨(일반적으로 12개월). | Lifecycle 규칙으로 업로드 이미지를 1일 후 삭제하여 저장량을 최소로 유지. | **확인 필요**: 정확한 저장 용량·요청 수·데이터 전송 무료 한도 및 12개월 적용 여부는 재확인 필요. |
| **Amazon DynamoDB (Cache_Table, Counter_Table)** | 저장 용량(예: 25GB)과 읽기/쓰기 용량 단위에 대한 상시 무료 한도가 있는 것으로 알려짐. | Provisioned 모드 소용량으로 설정하여 무료 한도 내 운영을 목표. | **확인 필요**: 정확한 저장 용량, 읽기/쓰기 용량 단위(RCU/WCU) 무료 한도 수치는 재확인 필요. |
| **Amazon CloudWatch Logs** | 로그 수집(ingestion) 및 저장(storage)에 대한 무료 한도가 제공됨. | 로그 보존 기간을 14일로 설정하여 저장량과 비용을 제한. | **확인 필요**: 수집/저장/조회(분석)별 정확한 무료 한도 수치는 재확인 필요. |
| **AWS SSM Parameter Store** | Standard 파라미터는 일반적으로 무료로 알려져 있음. Advanced 파라미터는 유료. | SerpApi Key 등 설정값을 Standard 파라미터로 저장(Advanced 미사용). | **확인 필요**: Standard 파라미터 저장·조회의 완전 무료 여부, 고처리량(higher throughput) 요금 적용 조건은 재확인 필요. |
| **AWS Amplify Hosting** | 빌드 분(build minutes), 호스팅 저장, 데이터 전송에 대한 무료 한도가 제공됨(일부는 12개월 한정일 수 있음). | 프론트엔드 정적 호스팅/빌드에 사용. | **확인 필요**: 빌드 분, 호스팅 저장, 데이터 전송별 무료 한도 수치와 12개월 적용 여부는 재확인 필요. |

---

## 중요 주의사항

1. **리전 의존성**: 위 수치와 적용 여부는 리전(CLOSELLER 기본 리전은 `ap-northeast-2`, 서울)에 따라 달라질 수 있다. 리전별 요금·프리 티어 적용 범위를 반드시 확인한다. → **확인 필요**
2. **가입 시점 의존성**: 프리 티어는 크게 **12개월 프리 티어**(계정 생성 후 12개월 한정)와 **상시 무료(Always Free)** 로 나뉜다. 어떤 서비스/한도가 어느 유형에 속하는지는 계정 가입 시점과 AWS 정책에 따라 달라지므로, 본 문서에서는 불확실한 부분을 **"확인 필요"** 로 명시했다.
3. **정확한 수치 미확정**: 본 문서는 version/time-sensitive 한 정확 수치(예: 월 요청 수, GB-초, 저장 용량, 빌드 분 등)를 임의로 확정하지 않는다. 모든 정확 수치는 AWS 공식 페이지에서 재확인한 뒤 갱신한다.
4. **과금 모니터링 권장**: 프리 티어 초과로 인한 예기치 않은 과금을 방지하기 위해 **AWS Budgets** 기반의 예산 알림을 반드시 설정할 것을 권장한다. 비용 설계와 예산 알림 설정 방법은 [`docs/cost-and-budgets.md`](./cost-and-budgets.md)를 참고한다.

---

_참고: 본 문서는 요구사항 22.4(`docs/aws-free-tier.md`에 서비스별 Free Tier 조사 결과를 기록하고 불확실한 항목을 "확인 필요"로 표시)를 충족한다._
