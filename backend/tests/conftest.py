"""pytest 공통 설정.

`src/` 를 import 경로에 추가해 테스트에서 `import closeller...` 형태로
순수 모듈을 가져올 수 있게 한다. pyproject.toml 의 `pythonpath = ["src"]`
설정과 함께 동작하며, pyproject 설정을 읽지 못하는 환경에서도 안전하도록 보강한다.
"""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
