"""해싱(순수 모듈).

Search_Lambda 파이프라인에서 사용하는 SHA-256 해시 계산을 담당한다.
I/O·외부 의존성(boto3·네트워크·파일)이 없는 순수 함수만 포함하며,
표준 라이브러리 `hashlib`만 사용한다(design.md 모듈 분리표 참조).

- 이미지 바이트 해시: 검증을 통과한 이미지 바이트의 SHA-256 16진 다이제스트를
  계산한다. 이 값은 Cache_Table의 `imageHash`(PK)로 사용된다(Req 6.1).
- IP 단방향 해시: 요청 IP 주소를 SHA-256 단방향 해시로 변환한다. Counter_Table에는
  이 해시 값만 저장하고 원본 IP는 저장하지 않는다. 이후 일일 카운터 키
  `IP#<sha256(ip)>#YYYY-MM-DD` 형태로 조합된다(Req 7.8).

두 함수 모두 동일 입력에 대해 항상 동일한 소문자 16진 다이제스트를 반환한다
(Property 6: SHA-256 해시 결정성). SHA-256은 단방향 함수이므로 해시에서
원본 바이트·IP를 복원할 수 없다(Property 10).
"""

import hashlib


def hash_image_bytes(data: bytes) -> str:
    """이미지 바이트의 SHA-256 16진 다이제스트를 반환한다(Req 6.1).

    Search_Lambda가 서버 재검증을 통과한 뒤 호출하며, 반환값은 Cache_Table의
    `imageHash` 키로 사용된다. 동일 바이트는 항상 동일한 해시를,
    서로 다른 바이트는 서로 다른 해시를 산출한다(Property 6).

    반환값은 소문자 16진 문자열(길이 64)이다.
    """
    return hashlib.sha256(data).hexdigest()


def hash_ip(ip: str) -> str:
    """IP 주소 문자열의 SHA-256 단방향 16진 다이제스트를 반환한다(Req 7.8).

    Counter_Table에는 이 해시 값만 저장하고 원본 IP 주소는 저장하지 않는다.
    SHA-256은 단방향 함수이므로 해시에서 원본 IP를 복원할 수 없다(Property 10).
    문자열은 UTF-8로 인코딩해 해시하며, 동일 IP는 항상 동일한 해시를 산출한다.

    반환값은 소문자 16진 문자열(길이 64)이다.
    """
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()
