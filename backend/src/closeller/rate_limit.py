"""호출 횟수 제한(I/O 모듈).

Search_Lambda 파이프라인에서 SerpApi 호출 횟수를 제한하기 위해 DynamoDB
`Counter_Table`을 조회하고 조건부 원자 증가를 수행하는 책임을 담당한다
(design.md 모듈 분리표의 `rate_limit.py` 행, Req 7.1~7.8). 순수 모듈과 달리
외부 I/O(DynamoDB)에 의존하므로 I/O 모듈로 분류한다.

Counter_Table 스키마(design.md Data Models 참조):

    | 속성             | 타입          | 설명                                                    |
    |------------------|---------------|---------------------------------------------------------|
    | counterId (PK)   | String        | 월간 `GLOBAL#YYYY-MM` / 일일 `IP#<sha256(ip)>#YYYY-MM-DD` |
    | count            | Number        | 현재 호출 수                                            |
    | ttl              | Number(epoch) | 기간 경과 후 자동 삭제                                  |

규칙:
  - **기간 리셋**: 키에 기간(YYYY-MM, YYYY-MM-DD)을 포함해 월/일 카운터가 자연
    분리된다. 별도 리셋 작업이 필요 없다.
  - **상한**: 월간 전체 기본 200, IP별 일일 기본 5. 환경변수로 설정하며 허용 범위는
    1~1,000,000 정수다(Req 7.3, 7.4). 환경변수 이름은 `MONTHLY_CALL_LIMIT`,
    `IP_DAILY_LIMIT`(.env.example 참조).
  - **조건부 원자 증가**: SerpApi 호출 직전, 카운터를 1씩 원자적으로 증가시킨다
    (Req 7.5). 증가 후 값이 상한을 초과하게 되면 조건식이 실패하고, 이때
    카운터 값은 증가 이전 그대로 유지된다(Req 7.6, Property 9).

        UpdateExpression:     SET #c = if_not_exists(#c, :zero) + :one, #ttl = :ttl
        ConditionExpression:  attribute_not_exists(#c) OR #c < :limit

    `#c < :limit` 이므로 현재 값이 `limit - 1` 이하일 때만 증가가 성립한다. 즉
    증가 후 값은 최대 `limit`이며 절대 상한을 초과하지 않는다(Property 9).
  - **IP 저장**: `hashing.hash_ip`로 만든 SHA-256 단방향 해시만 키에 넣는다. 원본
    IP는 저장하지 않는다(Req 7.8, Property 10) — IP 해시는 이 모듈에서 재구현하지
    않고 `hashing.py`를 재사용한다.
  - **TTL**: 각 카운터 항목에 `ttl`을 설정해 기간 경과 후 자동 삭제되게 한다
    (design.md Counter_Table). 월간 키는 생성 시각 + 31일, 일일 키는 생성 시각
    + 1일을 기본값으로 둔다(해당 기간이 지나면 의미가 없으므로 충분히 여유를 둔 값).

boto3 의존성 주입(테스트에서 모킹) — `cache.py`와 동일한 패턴:
  - 본 모듈은 모듈 수준에서 boto3 클라이언트/리소스를 만들지 않는다. 대신 DynamoDB
    `Table` 리소스를 인자로 주입받는다(`try_increment`/`get_count`의 `table`
    파라미터). 테스트는 `update_item`/`get_item`만 구현한 가짜 객체를 넘기면 되고,
    실제 AWS 호출은 일어나지 않는다.
  - 조건부 업데이트 실패는 DynamoDB의 `ConditionalCheckFailedException`으로
    나타난다. 본 모듈은 boto3를 import하지 않고도 이를 판별할 수 있도록 예외의
    클래스 이름(`ConditionalCheckFailedException`)으로 감지한다. 따라서 테스트용
    가짜 Table은 동일한 이름의 예외를 던지기만 하면 되고 boto3가 필요 없다.
  - 런타임(handler)이 사용할 수 있도록 `get_counter_table(...)`로 boto3 리소스에서
    Table을 얻는 헬퍼를 제공한다. boto3 import는 이 헬퍼 안에서만 수행하므로,
    boto3가 없는(또는 모킹된) 테스트 환경에서도 모듈 import가 실패하지 않는다.
"""

import os
import time
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

from .hashing import hash_ip

__all__ = [
    "DEFAULT_MONTHLY_LIMIT",
    "DEFAULT_IP_DAILY_LIMIT",
    "LIMIT_MIN",
    "LIMIT_MAX",
    "MONTHLY_TTL_SECONDS",
    "DAILY_TTL_SECONDS",
    "DynamoTable",
    "monthly_counter_id",
    "ip_daily_counter_id",
    "monthly_limit_from_env",
    "ip_daily_limit_from_env",
    "try_increment",
    "get_count",
    "get_counter_table",
]

# 상한 기본값과 환경변수 이름(Req 7.3, 7.4; .env.example).
DEFAULT_MONTHLY_LIMIT: int = 200
DEFAULT_IP_DAILY_LIMIT: int = 5
MONTHLY_LIMIT_ENV: str = "MONTHLY_CALL_LIMIT"
IP_DAILY_LIMIT_ENV: str = "IP_DAILY_LIMIT"

# 상한 허용 범위: 1~1,000,000 정수(Req 7.3, 7.4).
LIMIT_MIN: int = 1
LIMIT_MAX: int = 1_000_000

# 카운터 항목 TTL 간격(초). 키에 이미 기간이 포함되어 자연 분리되므로, TTL은
# 기간 경과 후 더 이상 의미 없는 항목을 수거하기 위한 여유값이다.
MONTHLY_TTL_SECONDS: int = 31 * 86400  # 31일
DAILY_TTL_SECONDS: int = 86400  # 1일

# 키 접두사.
_GLOBAL_PREFIX = "GLOBAL"
_IP_PREFIX = "IP"


class DynamoTable(Protocol):
    """주입받는 DynamoDB Table의 최소 인터페이스.

    boto3 `dynamodb.Table` 리소스가 이 형태를 만족한다. 테스트에서는
    `update_item`/`get_item`만 구현한 가짜 객체를 넘기면 되고 실제 AWS 호출은
    발생하지 않는다. `update_item`은 조건 실패 시
    `ConditionalCheckFailedException`(클래스 이름 기준)을 던져야 한다.
    """

    def update_item(self, **kwargs: Any) -> dict[str, Any]: ...

    def get_item(self, *, Key: dict[str, Any]) -> dict[str, Any]: ...


def _is_conditional_check_failed(exc: BaseException) -> bool:
    """예외가 DynamoDB 조건부 체크 실패인지 클래스 이름으로 판별한다.

    boto3를 import하지 않고도 판별할 수 있게 하여(테스트 모킹·경량 import 경로
    보호), 가짜 Table이 동일 이름의 예외를 던지기만 하면 조건 실패로 인식한다.
    botocore의 `ClientError`는 `response["Error"]["Code"]`로도 노출되므로 두 경로를
    모두 확인한다.
    """
    if type(exc).__name__ == "ConditionalCheckFailedException":
        return True
    # botocore.exceptions.ClientError 로 올라오는 경우(리소스가 아닌 클라이언트 API 등).
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        code = response.get("Error", {}).get("Code")
        if code == "ConditionalCheckFailedException":
            return True
    return False


def _coerce_limit(value: int) -> int:
    """상한 값을 허용 범위(1~1,000,000)로 제한한 정수로 반환한다(Req 7.3, 7.4)."""
    return max(LIMIT_MIN, min(LIMIT_MAX, int(value)))


def _limit_from_env(env_name: str, default: int) -> int:
    """환경변수에서 상한을 읽어 허용 범위로 보정해 반환한다.

    값이 없거나 정수로 해석할 수 없으면 기본값을 사용한다. 해석된 값이 허용 범위를
    벗어나면 범위 안으로 클램프한다(Req 7.3, 7.4).
    """
    raw = os.environ.get(env_name)
    if raw is None:
        return _coerce_limit(default)
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return _coerce_limit(default)
    return _coerce_limit(parsed)


def monthly_limit_from_env() -> int:
    """월간 전체 호출 상한을 환경변수에서 읽는다(기본 200, Req 7.3)."""
    return _limit_from_env(MONTHLY_LIMIT_ENV, DEFAULT_MONTHLY_LIMIT)


def ip_daily_limit_from_env() -> int:
    """IP별 일일 호출 상한을 환경변수에서 읽는다(기본 5, Req 7.4)."""
    return _limit_from_env(IP_DAILY_LIMIT_ENV, DEFAULT_IP_DAILY_LIMIT)


def _now_epoch() -> int:
    return int(time.time())


def _period_from_epoch(now: int) -> datetime:
    return datetime.fromtimestamp(now, tz=timezone.utc)


def monthly_counter_id(now: Optional[int] = None) -> str:
    """월간 전체 카운터 키 `GLOBAL#YYYY-MM`을 만든다.

    `now`(epoch 초)를 주지 않으면 현재 시각(UTC)을 사용한다. 키에 기간(YYYY-MM)을
    포함하므로 월이 바뀌면 자연히 새 카운터로 분리된다(별도 리셋 불필요).
    """
    period = _period_from_epoch(_now_epoch() if now is None else int(now))
    return f"{_GLOBAL_PREFIX}#{period.strftime('%Y-%m')}"


def ip_daily_counter_id(ip: str, now: Optional[int] = None) -> str:
    """IP별 일일 카운터 키 `IP#<sha256(ip)>#YYYY-MM-DD`를 만든다(Req 7.8).

    원본 IP는 저장하지 않고 `hashing.hash_ip`(SHA-256 단방향 해시)만 키에 넣는다
    (Property 10). `now`(epoch 초)를 주지 않으면 현재 시각(UTC)을 사용하며, 키에
    기간(YYYY-MM-DD)을 포함하므로 날짜가 바뀌면 자연히 새 카운터로 분리된다.
    """
    period = _period_from_epoch(_now_epoch() if now is None else int(now))
    return f"{_IP_PREFIX}#{hash_ip(ip)}#{period.strftime('%Y-%m-%d')}"


def try_increment(
    table: DynamoTable,
    counter_id: str,
    limit: int,
    *,
    ttl_seconds: int,
    now: Optional[int] = None,
) -> bool:
    """카운터를 조건부로 원자 증가시킨다. 성공하면 True, 상한 도달이면 False(Req 7.5~7.7).

    DynamoDB 조건부 UpdateItem으로 다음을 수행한다:

        SET  count = if_not_exists(count, :zero) + :one, ttl = :ttl
        조건: attribute_not_exists(count) OR count < :limit

    조건 `count < limit`가 성립할 때만(현재 값이 `limit - 1` 이하) 증가하므로 증가
    후 값은 최대 `limit`이며 상한을 절대 초과하지 않는다(Property 9). 현재 값이
    이미 상한 이상이면 조건식이 실패하여 `ConditionalCheckFailedException`이 발생하고,
    이때 카운터 값은 증가 이전 그대로 유지된다(Req 7.6). 이 경우 False를 반환해
    호출부가 SerpApi를 호출하지 않고 한도 초과 안내를 반환하도록 한다(Req 7.7).

    `limit`은 허용 범위(1~1,000,000)로 보정해 사용한다. `now`를 주지 않으면 현재
    시각(epoch 초)을 사용하며, `ttl = now + ttl_seconds`로 설정한다.
    """
    effective_now = _now_epoch() if now is None else int(now)
    effective_limit = _coerce_limit(limit)
    ttl = effective_now + int(ttl_seconds)

    try:
        table.update_item(
            Key={"counterId": counter_id},
            UpdateExpression=(
                "SET #c = if_not_exists(#c, :zero) + :one, #ttl = :ttl"
            ),
            ConditionExpression="attribute_not_exists(#c) OR #c < :limit",
            ExpressionAttributeNames={"#c": "count", "#ttl": "ttl"},
            ExpressionAttributeValues={
                ":zero": 0,
                ":one": 1,
                ":limit": effective_limit,
                ":ttl": ttl,
            },
        )
    except Exception as exc:  # noqa: BLE001 - 조건 실패만 선별 처리, 그 외 재전파
        if _is_conditional_check_failed(exc):
            # 상한 도달/초과: 값 유지, 증가 실패(Req 7.6, 7.7).
            return False
        raise
    return True


def get_count(table: DynamoTable, counter_id: str) -> int:
    """Counter_Table에서 `counter_id`의 현재 호출 수를 조회한다(Req 7.1).

    항목이 없으면 0을 반환한다. 상한 확인(조회 후 비교)에 사용할 수 있으나, 실제
    상한 보장은 `try_increment`의 조건부 업데이트가 원자적으로 담당한다(Property 9).
    """
    response = table.get_item(Key={"counterId": counter_id})
    item = response.get("Item")
    if not item:
        return 0
    return int(item.get("count", 0))


def get_counter_table(table_name: str, *, region_name: Optional[str] = None) -> Any:
    """런타임(handler)에서 Counter_Table DynamoDB Table 리소스를 얻는 헬퍼.

    boto3 import를 이 함수 내부에서만 수행하므로, boto3가 설치되지 않았거나 모킹된
    테스트 환경에서도 `rate_limit` 모듈 import 자체는 실패하지 않는다. 테스트는 이
    헬퍼 대신 `try_increment`/`get_count`에 가짜 Table을 직접 주입하면 되며, 이
    함수를 호출하지 않으므로 실제 AWS 호출이 발생하지 않는다.
    """
    import boto3  # 지연 import: 테스트 모킹·경량 import 경로 보호

    resource = boto3.resource("dynamodb", region_name=region_name)
    return resource.Table(table_name)
