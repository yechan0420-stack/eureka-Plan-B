"""호출 제한 단위 테스트 (예시 기반).

`rate_limit.try_increment`의 상한 도달·초과 동작을 구체적인 예시로 검증한다.
속성 기반 테스트(Property 9)는 `test_rate_limit_property.py`에 별도로 존재하며,
이 파일은 다음 명시적 시나리오를 결정적으로 확인한다(Req 7.5, 7.6):

  - 상한까지 정확히 채우는 동안 매 증가가 성공한다.
  - 상한에 도달한 상태에서의 증가 시도는 False를 반환하고 저장 값이 유지된다.
  - 상한 초과 반복 시도도 계속 False를 반환하며 값이 바뀌지 않는다.

더불어 카운터 키 생성 헬퍼(`monthly_counter_id`/`ip_daily_counter_id`)와
환경변수 상한 파싱(`monthly_limit_from_env`/`ip_daily_limit_from_env`)의
기본값·클램핑을 보조적으로 확인한다.

실제 AWS/boto3는 호출하지 않는다. DynamoDB 조건부 UpdateItem 의미를 재현하는
가짜 in-memory Table을 주입하며, 조건 실패 시 클래스 이름이
`ConditionalCheckFailedException`인 예외를 던진다(`rate_limit`는 boto3 없이
예외 클래스 이름으로 조건 실패를 감지한다).
"""

from typing import Any

import pytest

from closeller import rate_limit
from closeller.hashing import hash_ip
from closeller.rate_limit import (
    DEFAULT_IP_DAILY_LIMIT,
    DEFAULT_MONTHLY_LIMIT,
    IP_DAILY_LIMIT_ENV,
    LIMIT_MAX,
    LIMIT_MIN,
    MONTHLY_LIMIT_ENV,
    DAILY_TTL_SECONDS,
    MONTHLY_TTL_SECONDS,
    get_count,
    ip_daily_counter_id,
    ip_daily_limit_from_env,
    monthly_counter_id,
    monthly_limit_from_env,
    try_increment,
)


class ConditionalCheckFailedException(Exception):
    """가짜 Table이 조건식 실패 시 던지는 예외.

    `rate_limit`는 boto3 없이 예외의 클래스 이름(`ConditionalCheckFailedException`)
    으로 조건부 체크 실패를 감지한다. 동일 이름의 예외를 던지기만 하면 실제
    DynamoDB 없이도 상한 도달 분기를 정확히 재현할 수 있다.
    """


class FakeCounterTable:
    """DynamoDB Counter_Table의 조건부 UpdateItem 의미를 재현하는 가짜 Table.

    `try_increment`가 사용하는 UpdateExpression/ConditionExpression을 그대로
    해석한다:

        SET  count = if_not_exists(count, :zero) + :one, ttl = :ttl
        조건: attribute_not_exists(count) OR count < :limit

    조건이 거짓이면(현재 값이 `:limit` 이상) 값을 바꾸지 않고
    `ConditionalCheckFailedException`을 던진다. 참이면 count를 1 증가시키고 ttl을
    설정한다. 실제 AWS 호출은 일어나지 않는다.
    """

    def __init__(self) -> None:
        # counterId -> item({"count": int, "ttl": int})
        self._items: dict[str, dict[str, Any]] = {}

    def update_item(self, **kwargs: Any) -> dict[str, Any]:
        key = kwargs["Key"]["counterId"]
        values = kwargs["ExpressionAttributeValues"]
        limit = values[":limit"]
        ttl = values[":ttl"]

        item = self._items.get(key)
        current = item["count"] if item is not None else None

        # 조건: attribute_not_exists(count) OR count < :limit
        condition_met = current is None or current < limit
        if not condition_met:
            # 상한 도달/초과: 값 유지, 증가 실패(Req 7.6).
            raise ConditionalCheckFailedException("count >= limit")

        new_count = (current if current is not None else values[":zero"]) + values[":one"]
        self._items[key] = {"count": new_count, "ttl": ttl}
        return {}

    def get_item(self, *, Key: dict[str, Any]) -> dict[str, Any]:
        item = self._items.get(Key["counterId"])
        if item is None:
            return {}
        return {"Item": {"count": item["count"], "ttl": item["ttl"]}}

    # 테스트 검증용 헬퍼(비-DynamoDB API).
    def stored_count(self, counter_id: str) -> int:
        item = self._items.get(counter_id)
        return 0 if item is None else item["count"]


_NOW = 1_700_000_000  # 고정 시각으로 TTL/키를 결정적으로 만든다.


# --- 상한 도달까지 매 증가 성공 (Req 7.5) -----------------------------------
def test_increments_succeed_up_to_cap() -> None:
    """상한(IP 일일 기본 5)까지 정확히 채우는 동안 매 증가가 성공한다."""
    table = FakeCounterTable()
    counter_id = "IP#deadbeef#2025-01-01"
    limit = DEFAULT_IP_DAILY_LIMIT  # 5

    for expected_count in range(1, limit + 1):
        assert (
            try_increment(
                table, counter_id, limit, ttl_seconds=DAILY_TTL_SECONDS, now=_NOW
            )
            is True
        )
        # 각 증가 후 저장 값이 정확히 1씩 늘어난다.
        assert table.stored_count(counter_id) == expected_count

    assert table.stored_count(counter_id) == limit


# --- 상한 도달 상태의 다음 증가는 실패하고 값 유지 (Req 7.6) ------------------
def test_increment_at_cap_fails_and_preserves_value() -> None:
    """상한에 도달하면 다음 증가는 False이고 저장 값이 그대로 유지된다(Req 7.6)."""
    table = FakeCounterTable()
    counter_id = "GLOBAL#2025-01"
    limit = 3

    for _ in range(limit):
        assert (
            try_increment(
                table, counter_id, limit, ttl_seconds=MONTHLY_TTL_SECONDS, now=_NOW
            )
            is True
        )
    assert table.stored_count(counter_id) == limit

    # 상한 도달 상태에서의 증가 시도는 실패하고 값은 그대로 유지된다.
    assert (
        try_increment(
            table, counter_id, limit, ttl_seconds=MONTHLY_TTL_SECONDS, now=_NOW
        )
        is False
    )
    assert table.stored_count(counter_id) == limit


# --- 상한 초과 반복 시도도 계속 실패하고 값 불변 (Req 7.5, 7.6) ---------------
def test_repeated_over_cap_attempts_keep_failing_without_change() -> None:
    """상한 초과 상태에서 여러 번 더 시도해도 모두 False이고 값이 바뀌지 않는다."""
    table = FakeCounterTable()
    counter_id = "IP#cafebabe#2025-02-14"
    limit = 2

    # 상한까지 채운다.
    for _ in range(limit):
        assert (
            try_increment(
                table, counter_id, limit, ttl_seconds=DAILY_TTL_SECONDS, now=_NOW
            )
            is True
        )
    assert table.stored_count(counter_id) == limit

    # 추가 10회 시도 — 모두 실패(False)하고 값은 계속 limit로 고정된다.
    for _ in range(10):
        assert (
            try_increment(
                table, counter_id, limit, ttl_seconds=DAILY_TTL_SECONDS, now=_NOW
            )
            is False
        )
        assert table.stored_count(counter_id) == limit
        # get_count로 읽어도 상한을 넘지 않는다.
        assert get_count(table, counter_id) == limit


# --- 상한 1(최소값): 첫 증가만 성공, 이후 실패 (Req 7.5, 7.6) ----------------
def test_limit_one_allows_single_increment_only() -> None:
    """상한이 1이면 첫 증가만 성공하고 이후 시도는 실패하며 값은 1로 유지된다."""
    table = FakeCounterTable()
    counter_id = "GLOBAL#2025-03"

    assert (
        try_increment(table, counter_id, 1, ttl_seconds=MONTHLY_TTL_SECONDS, now=_NOW)
        is True
    )
    assert table.stored_count(counter_id) == 1

    assert (
        try_increment(table, counter_id, 1, ttl_seconds=MONTHLY_TTL_SECONDS, now=_NOW)
        is False
    )
    assert table.stored_count(counter_id) == 1


# --- TTL이 now + ttl_seconds로 저장된다 -------------------------------------
def test_ttl_stored_as_now_plus_interval() -> None:
    """증가 성공 시 ttl = now + ttl_seconds로 저장된다(기간 경과 자동 수거용)."""
    table = FakeCounterTable()
    counter_id = "IP#abc123#2025-04-01"

    assert (
        try_increment(table, counter_id, 5, ttl_seconds=DAILY_TTL_SECONDS, now=_NOW)
        is True
    )
    stored = table.get_item(Key={"counterId": counter_id})["Item"]
    assert stored["ttl"] == _NOW + DAILY_TTL_SECONDS


# --- get_count: 항목 없으면 0 ------------------------------------------------
def test_get_count_returns_zero_when_absent() -> None:
    """카운터 항목이 아직 없으면 현재 호출 수는 0이다."""
    table = FakeCounterTable()
    assert get_count(table, "GLOBAL#2099-12") == 0


# --- 카운터 키 헬퍼: 월간 GLOBAL#YYYY-MM -------------------------------------
def test_monthly_counter_id_format() -> None:
    """월간 카운터 키는 `GLOBAL#YYYY-MM` 형식이다(UTC 기준)."""
    # _NOW = 1_700_000_000 → 2023-11-14T22:13:20Z → YYYY-MM = 2023-11
    assert monthly_counter_id(now=_NOW) == "GLOBAL#2023-11"


# --- 카운터 키 헬퍼: 일일 IP#<sha256>#YYYY-MM-DD (Req 7.8) -------------------
def test_ip_daily_counter_id_format_uses_ip_hash() -> None:
    """일일 카운터 키는 `IP#<sha256(ip)>#YYYY-MM-DD`이고 원본 IP를 포함하지 않는다."""
    ip = "203.0.113.7"
    counter_id = ip_daily_counter_id(ip, now=_NOW)

    expected = f"IP#{hash_ip(ip)}#2023-11-14"
    assert counter_id == expected
    # 원본 IP 문자열이 키에 그대로 노출되지 않는다(단방향 해시만 사용).
    assert ip not in counter_id


# --- 환경변수 상한 파싱: 기본값 (Req 7.3, 7.4) -------------------------------
def test_limits_default_when_env_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """환경변수가 없으면 월간 200/IP 일일 5 기본값을 사용한다."""
    monkeypatch.delenv(MONTHLY_LIMIT_ENV, raising=False)
    monkeypatch.delenv(IP_DAILY_LIMIT_ENV, raising=False)

    assert monthly_limit_from_env() == DEFAULT_MONTHLY_LIMIT == 200
    assert ip_daily_limit_from_env() == DEFAULT_IP_DAILY_LIMIT == 5


# --- 환경변수 상한 파싱: 유효한 정수 반영 -----------------------------------
def test_limits_read_valid_integer_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """허용 범위 안의 환경변수 정수는 그대로 상한으로 사용된다."""
    monkeypatch.setenv(MONTHLY_LIMIT_ENV, "500")
    monkeypatch.setenv(IP_DAILY_LIMIT_ENV, "12")

    assert monthly_limit_from_env() == 500
    assert ip_daily_limit_from_env() == 12


# --- 환경변수 상한 파싱: 범위 밖 값 클램핑 (Req 7.3, 7.4) --------------------
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param("0", LIMIT_MIN, id="below-min-clamped-to-min"),
        pytest.param("-10", LIMIT_MIN, id="negative-clamped-to-min"),
        pytest.param("2000000", LIMIT_MAX, id="above-max-clamped-to-max"),
    ],
)
def test_limits_clamped_to_allowed_range(
    raw: str, expected: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """범위(1~1,000,000)를 벗어난 환경변수 값은 경계값으로 클램프된다."""
    monkeypatch.setenv(MONTHLY_LIMIT_ENV, raw)
    assert monthly_limit_from_env() == expected


# --- 환경변수 상한 파싱: 정수 해석 불가 → 기본값 ----------------------------
def test_limits_fall_back_to_default_on_non_integer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """정수로 해석할 수 없는 환경변수 값은 기본값으로 대체된다."""
    monkeypatch.setenv(MONTHLY_LIMIT_ENV, "not-a-number")
    monkeypatch.setenv(IP_DAILY_LIMIT_ENV, "")

    assert monthly_limit_from_env() == DEFAULT_MONTHLY_LIMIT
    assert ip_daily_limit_from_env() == DEFAULT_IP_DAILY_LIMIT


# --- 비조건부 예외는 재전파된다 ---------------------------------------------
def test_non_conditional_exception_propagates() -> None:
    """조건 실패가 아닌 예외는 삼키지 않고 그대로 전파된다."""

    class ExplodingTable:
        def update_item(self, **_: Any) -> dict[str, Any]:
            raise RuntimeError("boom")

        def get_item(self, *, Key: dict[str, Any]) -> dict[str, Any]:
            return {}

    with pytest.raises(RuntimeError, match="boom"):
        try_increment(
            ExplodingTable(), "GLOBAL#2025-01", 5, ttl_seconds=DAILY_TTL_SECONDS, now=_NOW
        )


# --- 모듈은 boto3 없이도 import/사용 가능 (지연 import 보장) -----------------
def test_module_usable_without_boto3() -> None:
    """핵심 함수들이 boto3를 import하지 않고도 노출되어 있어야 한다(지연 import)."""
    assert callable(rate_limit.try_increment)
    assert callable(rate_limit.get_count)
    assert rate_limit.LIMIT_MIN == 1
    assert rate_limit.LIMIT_MAX == 1_000_000
