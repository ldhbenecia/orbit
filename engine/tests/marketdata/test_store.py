import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from orbit.marketdata.candle import Candle
from orbit.marketdata.store import CandleStore

D = datetime(2024, 1, 1, tzinfo=UTC)


def _candle(day: int, close: str, market: str = "KRW-BTC") -> Candle:
    price = Decimal(close)
    return Candle(market, D + timedelta(days=day), price, price, price, price, Decimal("1.5"))


def test_가격은_숫자로_저장돼_SQL_정렬·비교가_맞음() -> None:
    conn = sqlite3.connect(":memory:")
    store = CandleStore(conn)
    # 문자열 비교였다면 "9000000" > "10000000" 이 됨
    store.upsert([_candle(0, "9000000"), _candle(1, "10000000")], fetched_at=D)

    highest = conn.execute("SELECT close FROM daily_candles ORDER BY close DESC LIMIT 1").fetchone()
    above = conn.execute("SELECT COUNT(*) FROM daily_candles WHERE close > 9500000").fetchone()

    assert highest == (10000000,)
    assert above == (1,)


def test_원화_마켓에_소수_가격이_들어오면_저장을_거부() -> None:
    store = CandleStore(sqlite3.connect(":memory:"))

    with pytest.raises(ValueError):
        store.upsert([_candle(0, "115216000.1")], fetched_at=D)
    assert store.load("KRW-BTC") == []


def test_지원하지_않는_호가_통화는_거부() -> None:
    store = CandleStore(sqlite3.connect(":memory:"))

    with pytest.raises(ValueError):
        store.upsert([_candle(0, "100", market="USDT-BTC")], fetched_at=D)


def test_받은_시각은_재수집하면_갱신() -> None:
    conn = sqlite3.connect(":memory:")
    store = CandleStore(conn)
    store.upsert([_candle(0, "100")], fetched_at=D)
    later = D + timedelta(days=3)

    store.upsert([_candle(0, "100")], fetched_at=later)

    assert conn.execute("SELECT fetched_ts FROM daily_candles").fetchone() == (
        int(later.timestamp()),
    )
