from datetime import UTC, datetime, timedelta
from decimal import Decimal

from orbit.marketdata.aggregate import Interval, aggregate, period_start
from orbit.marketdata.candle import Candle


def _day(day: datetime, o: int, h: int, low: int, c: int) -> Candle:
    return Candle("KRW-BTC", day, Decimal(o), Decimal(h), Decimal(low), Decimal(c), Decimal(1))


def test_주봉은_월요일_월봉은_1일에_시작() -> None:
    sunday = datetime(2026, 10, 4, tzinfo=UTC)

    assert period_start(sunday, Interval.WEEK) == datetime(2026, 9, 28, tzinfo=UTC)
    assert period_start(sunday, Interval.MONTH) == datetime(2026, 10, 1, tzinfo=UTC)


def test_시가는_첫날_종가는_마지막날_고저는_기간_최고최저() -> None:
    mon = datetime(2026, 9, 28, tzinfo=UTC)
    days = [
        _day(mon, 100, 120, 90, 110),
        _day(mon + timedelta(1), 111, 150, 105, 140),
        _day(mon + timedelta(2), 139, 145, 80, 95),
    ]

    (week,) = aggregate(days, Interval.WEEK)

    assert (week.start, week.open, week.high, week.low, week.close) == (
        mon,
        *(Decimal(v) for v in (100, 150, 80, 95)),
    )
    assert week.volume == 3


def test_월이_바뀌어도_같은_주면_한_주봉() -> None:
    days = [
        _day(datetime(2026, 9, 30, tzinfo=UTC) + timedelta(i), 1, 1, 1, 1) for i in range(5)
    ]  # 수~일

    assert [c.start.day for c in aggregate(days, Interval.WEEK)] == [28]
    assert [c.start.month for c in aggregate(days, Interval.MONTH)] == [9, 10]
