"""검색 결과 캐시(I/O 모듈).

Search_Lambda 파이프라인에서 이미지 해시(SHA-256) 기준 검색 결과 캐시를
DynamoDB `Cache_Table`에 조회/저장하는 책임을 담당한다(design.md 모듈 분리표의
`cache.py` 행, Req 6.2·6.3·6.4). 순수 모듈과 달리 외부 I/O(DynamoDB)에
의존하므로 I/O 모듈로 분류한다.

Cache_Table 스키마(design.md Data Models 참조):

    | 속성            | 타입          | 설명                                   |
    |-----------------|---------------|----------------------------------------|
    | imageHash (PK)  | String        | 이미지 바이트 SHA-256                   |
    | results         | String(JSON)  | 정규화 결과 배열                        |
    | currencyMixed   | Bool          | 통화 혼재 여부                          |
    | createdAt       | Number(epoch) | 생성 시각                              |
    | ttl             | Number(epoch) | createdAt + 86400 (24시간) — DynamoDB TTL |

규칙:
  - 저장 시 `ttl = createdAt + 86400`(24시간)으로 항상 설정한다(Req 6.4,
    Property 8: 캐시 저장 TTL 항상 24시간). TTL 간격은 모듈 상수
    `CACHE_TTL_SECONDS`로 고정한다.
  - `currencyMixed`(통화 혼재 여부)를 함께 저장한다(design.md Data Models).
  - `results`는 `NormalizedResult`의 순서를 보존하는 JSON 문자열로 직렬화해
    저장하고, 조회 시 다시 `NormalizedResult`로 역직렬화한다. 응답에 없는 값을
    생성·추론하지 않는다(Req 9.9) — 저장된 값만 그대로 복원한다.

boto3 의존성 주입(테스트에서 모킹):
  - 본 모듈은 모듈 수준에서 boto3 클라이언트/리소스를 만들지 않는다. 대신
    DynamoDB `Table` 리소스를 인자로 주입받는다(`lookup`/`store`의 `table`
    파라미터). 테스트는 `get_item`/`put_item`만 구현한 가짜 객체를 넘기면 되고,
    실제 AWS 호출은 일어나지 않는다.
  - 런타임(handler)이 사용할 수 있도록, 필요 시 `get_cache_table(...)`로 boto3
    리소스에서 Table을 얻는 헬퍼를 제공한다. boto3 import는 이 헬퍼 안에서만
    수행하므로, boto3가 없는(또는 모킹된) 테스트 환경에서도 모듈 import가
    실패하지 않는다.
"""

import json
import time
from dataclasses import asdict
from typing import Any, Optional, Protocol

from .models import NormalizedResult

__all__ = [
    "CACHE_TTL_SECONDS",
    "CacheEntry",
    "DynamoTable",
    "compute_ttl",
    "serialize_results",
    "deserialize_results",
    "lookup",
    "store",
    "get_cache_table",
]

# 캐시 TTL 간격: 24시간(초). ttl = createdAt + CACHE_TTL_SECONDS 로 고정한다(Req 6.4).
CACHE_TTL_SECONDS: int = 86400


class DynamoTable(Protocol):
    """주입받는 DynamoDB Table의 최소 인터페이스.

    boto3 `dynamodb.Table` 리소스가 이 형태를 만족한다. 테스트에서는
    `get_item`/`put_item`만 구현한 가짜 객체를 넘기면 되고 실제 AWS 호출은
    발생하지 않는다.
    """

    def get_item(self, *, Key: dict[str, Any]) -> dict[str, Any]: ...

    def put_item(self, *, Item: dict[str, Any]) -> dict[str, Any]: ...


class CacheEntry:
    """Cache_Table에서 조회한 캐시 항목(역직렬화 결과).

    `results`는 `NormalizedResult` 리스트로 복원된 값이며, `currency_mixed`는
    저장 시점의 통화 혼재 여부, `created_at`/`ttl`은 저장 시각과 만료 시각(epoch)이다.
    """

    __slots__ = ("image_hash", "results", "currency_mixed", "created_at", "ttl")

    def __init__(
        self,
        image_hash: str,
        results: list[NormalizedResult],
        currency_mixed: bool,
        created_at: int,
        ttl: int,
    ) -> None:
        self.image_hash = image_hash
        self.results = results
        self.currency_mixed = currency_mixed
        self.created_at = created_at
        self.ttl = ttl

    def __repr__(self) -> str:  # pragma: no cover - 디버깅 편의용
        return (
            "CacheEntry("
            f"image_hash={self.image_hash!r}, "
            f"results=<{len(self.results)} items>, "
            f"currency_mixed={self.currency_mixed!r}, "
            f"created_at={self.created_at!r}, ttl={self.ttl!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CacheEntry):
            return NotImplemented
        return (
            self.image_hash == other.image_hash
            and self.results == other.results
            and self.currency_mixed == other.currency_mixed
            and self.created_at == other.created_at
            and self.ttl == other.ttl
        )


def compute_ttl(created_at: int) -> int:
    """저장 시각(epoch)으로부터 캐시 만료 시각(epoch)을 계산한다(Req 6.4).

    항상 `created_at + CACHE_TTL_SECONDS`(= createdAt + 86400, 24시간)을 반환한다
    (Property 8: 캐시 저장 TTL 항상 24시간). `created_at` 값과 무관하게 TTL
    간격은 고정 24시간이다.
    """
    return created_at + CACHE_TTL_SECONDS


def serialize_results(results: list[NormalizedResult]) -> str:
    """정규화 결과 리스트를 Cache_Table `results` 속성용 JSON 문자열로 직렬화한다.

    `NormalizedResult`는 frozen dataclass이므로 `asdict`로 필드를 보존해 직렬화한다.
    입력 순서를 그대로 유지하며(서버 기본 정렬 결과 보존, Req 9.7), 한글 등
    비 ASCII 문자는 이스케이프하지 않는다(가독성, 값 보존).
    """
    return json.dumps([asdict(r) for r in results], ensure_ascii=False)


def deserialize_results(raw: str) -> list[NormalizedResult]:
    """Cache_Table `results` 속성(JSON 문자열)을 NormalizedResult 리스트로 복원한다.

    저장된 값만 그대로 복원하고 없는 값을 생성·추론하지 않는다(Req 9.9).
    저장 시점의 순서를 보존한다.
    """
    items = json.loads(raw)
    return [NormalizedResult(**item) for item in items]


def lookup(table: DynamoTable, image_hash: str) -> Optional[CacheEntry]:
    """Cache_Table에서 `image_hash`에 해당하는 캐시 항목을 조회한다(Req 6.2).

    주입받은 `table`(boto3 Table 또는 테스트용 가짜)로 `get_item`을 호출한다.
    항목이 없으면 None을 반환한다. 항목이 있으면 `results`(JSON)를
    `NormalizedResult` 리스트로 복원하고 `CacheEntry`로 감싸 반환한다.

    DynamoDB TTL 만료는 최종적으로 삭제로 이어지지만 즉시성은 보장되지 않으므로,
    조회된 항목의 `ttl`이 현재 시각보다 과거이면(이미 만료) 유효하지 않은 것으로
    보고 None을 반환해 캐시 미적중과 동일하게 처리한다(Req 6.3: "유효한 캐시 항목").
    """
    response = table.get_item(Key={"imageHash": image_hash})
    item = response.get("Item")
    if not item:
        return None

    created_at = int(item["createdAt"])
    ttl = int(item["ttl"])

    # 만료된(DynamoDB가 아직 수거하지 않은) 항목은 미적중으로 취급한다.
    if ttl <= int(time.time()):
        return None

    return CacheEntry(
        image_hash=str(item["imageHash"]),
        results=deserialize_results(str(item["results"])),
        currency_mixed=bool(item["currencyMixed"]),
        created_at=created_at,
        ttl=ttl,
    )


def store(
    table: DynamoTable,
    image_hash: str,
    results: list[NormalizedResult],
    currency_mixed: bool,
    created_at: Optional[int] = None,
) -> CacheEntry:
    """새 검색 결과를 Cache_Table에 TTL 24시간으로 저장한다(Req 6.4).

    `created_at`을 주지 않으면 현재 시각(epoch 초)을 사용한다. `ttl`은 항상
    `created_at + 86400`(24시간)으로 설정하며(Property 8), `currency_mixed`
    (통화 혼재 여부)도 함께 저장한다. `results`는 JSON 문자열로 직렬화해 보존한다.

    주입받은 `table`로 `put_item`을 호출하며, 저장에 사용한 값을 담은
    `CacheEntry`를 반환한다(호출부가 저장 결과를 바로 사용할 수 있게 한다).
    """
    effective_created_at = int(time.time()) if created_at is None else int(created_at)
    ttl = compute_ttl(effective_created_at)

    item: dict[str, Any] = {
        "imageHash": image_hash,
        "results": serialize_results(results),
        "currencyMixed": bool(currency_mixed),
        "createdAt": effective_created_at,
        "ttl": ttl,
    }
    table.put_item(Item=item)

    return CacheEntry(
        image_hash=image_hash,
        results=list(results),
        currency_mixed=bool(currency_mixed),
        created_at=effective_created_at,
        ttl=ttl,
    )


def get_cache_table(table_name: str, *, region_name: Optional[str] = None) -> Any:
    """런타임(handler)에서 Cache_Table DynamoDB Table 리소스를 얻는 헬퍼.

    boto3 import를 이 함수 내부에서만 수행하므로, boto3가 설치되지 않았거나
    모킹된 테스트 환경에서도 `cache` 모듈 import 자체는 실패하지 않는다. 테스트는
    이 헬퍼 대신 `lookup`/`store`에 가짜 Table을 직접 주입하면 되며, 이 함수를
    호출하지 않으므로 실제 AWS 호출이 발생하지 않는다.
    """
    import boto3  # 지연 import: 테스트 모킹·경량 import 경로 보호

    resource = boto3.resource("dynamodb", region_name=region_name)
    return resource.Table(table_name)
