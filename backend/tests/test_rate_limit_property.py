"""호출 제한 속성 테스트 (Property 9).

`rate_limit.try_increment`의 조건부 원자 증가가 카운터 상한을 절대 초과하지
않음을 검증한다. 실제 AWS/boto3를 호출하지 않고, DynamoDB의 조건부 UpdateItem
의미를 재현하는 가짜 in-memory Table을 주입해 검증한다
(design.md Property 9, Req 7.5~7.7 참조).

Property 9: 임의의 상한 값 L과 임의 길이의 호출 증가 시퀀스에 대해 카운터 값은
상한 L을 절대 초과하지 않으며, 상한에 도달한 상태에서의 증가 시도는 실패하여
값이 유지되고(SerpApi_Service가 호출되지 않도록 False 반환) 성공한 증가 횟수는
min(N, L)과 같다(Req 7.5, 7.6, 7.7).
"""

from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from closeller.rate_limit import (
    DAILY_TTL_SECONDS,
    LIMIT_MAX,
    LIMIT_MIN,
    try_increment,
)


class ConditionalCheckFailedException(Exception):
    """가짜 Table이 조건식 실패 시 던지는 예외.

    `rate_limit`는 boto3 없이 예외의 클래스 이름(`ConditionalCheckFailedException`)
    으로 조건부 체크 실패를 감지한다. 따라서 동일 이름의 예외를 던지기만 하면
    실제 DynamoDB 없이도 상한 도달 분기를 정확히 재현할 수 있다.
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


# --- 생성기(generator): 상한·증가 횟수 입력 공간을 지능적으로 구성한다 --------

# 상한 L: 허용 범위(1~1,000,000) 안에서, 경계(최소/작은 값)에 가중치를 두어
# 포화 상태를 자주 밟도록 구성한다. 상위 경계도 대표값으로 포함한다.
_limit = st.one_of(
    st.integers(min_value=LIMIT_MIN, max_value=20),
    st.just(LIMIT_MIN),
    st.just(LIMIT_MAX),
    st.integers(min_value=LIMIT_MIN, max_value=LIMIT_MAX),
)

# 증가 시도 횟수 N: 0 ~ 50. 작은 상한과 조합하면 포화 이후 시도가 반복된다.
_attempts = st.integers(min_value=0, max_value=50)


# Feature: closeller-mvp, Property 9: 호출 카운터는 상한 절대 초과하지 않음
@settings(max_examples=300)
@given(limit=_limit, attempts=_attempts)
def test_counter_never_exceeds_limit(limit: int, attempts: int) -> None:
    """N번의 증가 시도 후에도 저장 카운터는 상한 L을 절대 초과하지 않는다.

    성공한 증가 횟수는 min(N, L)과 같고, 저장된 값도 min(N, L)이다. 상한에 도달한
    뒤의 시도는 모두 False를 반환하며(SerpApi 미호출) 값을 그대로 유지한다
    (Req 7.5, 7.6, 7.7).
    """
    table = FakeCounterTable()
    counter_id = "GLOBAL#2025-01"

    successes = 0
    for _ in range(attempts):
        ok = try_increment(
            table,
            counter_id,
            limit,
            ttl_seconds=DAILY_TTL_SECONDS,
            now=1_700_000_000,
        )
        if ok:
            successes += 1
        # 어떤 시점에서도 저장 값이 상한을 초과하지 않는다(Property 9 핵심).
        assert table.stored_count(counter_id) <= limit

    expected = min(attempts, limit)
    assert successes == expected
    assert table.stored_count(counter_id) == expected


# Feature: closeller-mvp, Property 9: 호출 카운터는 상한 절대 초과하지 않음
@settings(max_examples=300)
@given(limit=st.integers(min_value=LIMIT_MIN, max_value=20), extra=_attempts)
def test_once_capped_increments_fail_and_value_preserved(limit: int, extra: int) -> None:
    """상한 도달 후의 증가 시도는 실패(False)하며 값이 보존된다(Req 7.6, 7.7).

    먼저 상한까지 정확히 채운 뒤, 추가 시도가 모두 False를 반환하고 저장 값이
    계속 L로 유지되는지 확인한다.
    """
    table = FakeCounterTable()
    counter_id = "IP#deadbeef#2025-01-01"

    # 상한까지 정확히 채운다 — 모두 성공해야 한다.
    for _ in range(limit):
        assert (
            try_increment(
                table, counter_id, limit, ttl_seconds=DAILY_TTL_SECONDS, now=1_700_000_000
            )
            is True
        )
    assert table.stored_count(counter_id) == limit

    # 이후 추가 시도는 모두 실패(False)하고 값은 L로 유지된다.
    for _ in range(extra):
        assert (
            try_increment(
                table, counter_id, limit, ttl_seconds=DAILY_TTL_SECONDS, now=1_700_000_000
            )
            is False
        )
        assert table.stored_count(counter_id) == limit


# Feature: closeller-mvp, Property 9: 호출 카운터는 상한 절대 초과하지 않음
@settings(max_examples=200)
@given(
    limit=st.integers(min_value=LIMIT_MIN, max_value=20),
    counter_ids=st.lists(
        st.sampled_from(["GLOBAL#2025-01", "IP#aaa#2025-01-01", "IP#bbb#2025-01-01"]),
        min_size=0,
        max_size=40,
    ),
)
def test_independent_counters_each_bounded(limit: int, counter_ids: list[str]) -> None:
    """서로 다른 counterId는 독립적으로 각자 상한 L 이하로 유지된다.

    월간 전체 키와 IP별 일일 키가 한 Table 안에 섞여 증가해도, 각 키의 저장
    값이 개별적으로 L을 초과하지 않음을 확인한다(기간·범위별 자연 분리).
    """
    table = FakeCounterTable()
    for cid in counter_ids:
        try_increment(table, cid, limit, ttl_seconds=DAILY_TTL_SECONDS, now=1_700_000_000)

    for cid in set(counter_ids):
        attempts_for_cid = counter_ids.count(cid)
        assert table.stored_count(cid) == min(attempts_for_cid, limit)
        assert table.stored_count(cid) <= limit
