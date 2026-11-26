"""스캐폴딩 확인용 테스트.

백엔드 패키지 구조와 pytest 설정이 올바른지 확인한다.
개별 순수/ I/O 모듈 테스트는 이후 작업에서 추가한다.
"""


def test_closeller_package_importable() -> None:
    """`src/` 레이아웃에서 closeller 패키지를 import 할 수 있어야 한다."""
    import closeller

    assert hasattr(closeller, "__all__")
