from datetime import UTC, datetime, timedelta

from orbit.marketdata.candle import find_missing_days


def test_빠진_날만_찾음() -> None:
    d = datetime(2024, 1, 1, tzinfo=UTC)
    starts = [d, d + timedelta(days=1), d + timedelta(days=4)]

    assert find_missing_days(starts) == [d + timedelta(days=2), d + timedelta(days=3)]


def test_연속이면_빠진_날_없음() -> None:
    d = datetime(2024, 1, 1, tzinfo=UTC)

    assert find_missing_days([d + timedelta(days=i) for i in range(5)]) == []
