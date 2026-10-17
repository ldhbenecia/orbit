import sqlite3
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from orbit.marketdata.candle import Candle
from orbit.marketdata.instruments import NEW_YORK, Instrument
from orbit.marketdata.store import CandleStore
from orbit.marketdata.sync import STOCK_EARLIEST, sync_stock_daily

EXA = Instrument("US-EXA", "EXA", NEW_YORK)
DAY = datetime(2026, 3, 2, tzinfo=UTC)
NOW = DAY + timedelta(days=10)


def bar(day: int, close: str) -> Candle:
    p = Decimal(close)
    return Candle("US-EXA", DAY + timedelta(days=day), p, p, p, p, Decimal(1))


class FakeToss:
    # 기간별로 다른 응답 — 요청한 시작일도 기록해 조건을 지워도 통과하지 않게
    def __init__(self, recent: list[Candle], full: list[Candle]) -> None:
        self.recent, self.full = recent, full
        self.since: list[date] = []

    def daily_candles(
        self, symbol: str, market: str, exchange_tz: ZoneInfo, since: date
    ) -> list[Candle]:
        assert (symbol, market) == ("EXA", "US-EXA")
        self.since.append(since)
        return self.full if since == STOCK_EARLIEST.date() else self.recent


def _stored(*bars: Candle) -> CandleStore:
    store = CandleStore(sqlite3.connect(":memory:"))
    store.upsert(list(bars), fetched_at=DAY)
    return store


def test_마지막_봉_가격이_그대로면_이어서만_받음() -> None:
    store = _stored(bar(0, "400"), bar(1, "404"))
    toss = FakeToss(recent=[bar(1, "404"), bar(2, "408")], full=[])

    sync_stock_daily(toss, store, EXA, NOW)

    assert toss.since == [(DAY + timedelta(days=1)).date()]
    assert [c.close for c in store.load("US-EXA")] == [400, 404, 408]


def test_수정주가가_바뀌면_전_기간을_다시_받아_통째로_바꿈() -> None:
    # 4:1 분할 — 같은 날 봉이 404 → 101 로 다시 옴
    # 옛 봉이 분할 전 가격으로 남으면 분할일에 75% 폭락처럼 보임
    store = _stored(bar(-1, "396"), bar(0, "400"), bar(1, "404"))
    adjusted = [bar(0, "100"), bar(1, "101"), bar(2, "102")]  # 새 응답에 없는 옛 봉(-1)은 지워짐
    toss = FakeToss(recent=[bar(1, "101"), bar(2, "102")], full=adjusted)

    result = sync_stock_daily(toss, store, EXA, NOW)

    assert toss.since == [(DAY + timedelta(days=1)).date(), STOCK_EARLIEST.date()]
    assert store.load("US-EXA") == adjusted
    assert result.total == 3 and result.replaced


def test_처음이면_전_기간을_한_번만_받음() -> None:
    store = CandleStore(sqlite3.connect(":memory:"))
    toss = FakeToss(recent=[], full=[bar(0, "100"), bar(1, "101")])

    sync_stock_daily(toss, store, EXA, NOW)

    assert toss.since == [STOCK_EARLIEST.date()]
    assert len(store.load("US-EXA")) == 2
