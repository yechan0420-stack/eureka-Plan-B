# CLOSELLER 백엔드

AWS Lambda(Python)에서 실행되는 CLOSELLER 1차 MVP 백엔드다.
검증·정규화·분류 등 **순수 로직을 핸들러와 분리**해 단위/속성 테스트 대상으로 둔다.

## 폴더 구조

```
backend/
├─ src/
│  └─ closeller/        # 소스 패키지 (순수 모듈 + I/O 모듈, 이후 작업에서 추가)
│     └─ __init__.py
├─ tests/               # pytest 테스트 (단위 + hypothesis 속성 테스트)
│  ├─ conftest.py       # src/ 를 import 경로에 추가
│  └─ test_scaffolding.py
├─ pyproject.toml       # 의존성 + pytest 설정
├─ requirements.txt     # 런타임 의존성 (boto3)
└─ requirements-dev.txt # 개발·테스트 의존성 (pytest, hypothesis)
```

모듈 분리 계획(순수/ I/O)은 `.kiro/specs/closeller-mvp/design.md`의 모듈 분리표를 따른다.

## 로컬 개발 (Windows PowerShell)

```powershell
# backend 디렉터리에서 실행
# 1) 가상환경 생성·활성화
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) 개발·테스트 의존성 설치
pip install -r requirements-dev.txt

# 3) 테스트 실행
pytest
```

> 참고: 비밀값(API Key, AWS 자격 증명)은 코드·파일·로그 어디에도 넣지 않는다.
> 실제 SerpApi 호출과 AWS 리소스 변경은 승인 전에는 실행하지 않는다.
