from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from orbit.marketdata.candle import Candle


class Interval(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


def period_start(day: datetime, interval: Interval) -> datetime:
    # 업비트 기준 — 주봉은 월요일 UTC 0시, 월봉은 1일 UTC 0시에 시작
    if interval is Interval.WEEK:
        return day - timedelta(days=day.weekday())
    if interval is Interval.MONTH:
        return day.replace(day=1)
    return day


def aggregate(candles: Sequence[Candle], interval: Interval) -> list[Candle]:
    if interval is Interval.DAY:
        return list(candles)
    groups: dict[datetime, list[Candle]] = {}
    for c in candles:
        groups.setdefault(period_start(c.start, interval), []).append(c)
    return [
        Candle(
            market=group[0].market,
            start=start,
            open=group[0].open,
            high=max(c.high for c in group),
            low=min(c.low for c in group),
            close=group[-1].close,
            volume=sum((c.volume for c in group), Decimal(0)),
        )
        for start, group in groups.items()
    ]
