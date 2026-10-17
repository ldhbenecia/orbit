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


def test_미국_수정주가는_소수_8자리까지_그대로_저장() -> None:
    # 액면분할을 여러 번 한 종목은 오래전 수정주가가 1달러 미만·소수 8자리로 옴
    store = CandleStore(sqlite3.connect(":memory:"))

    store.upsert([_candle(0, "0.95962272", market="US-AAA")], fetched_at=D)

    assert store.load("US-AAA")[0].close == Decimal("0.95962272")


def test_미국_일봉은_자릿수를_바꾸며_다시_받도록_지우고_다른_시장은_그대로() -> None:
    from orbit.db.migrations import MIGRATIONS

    conn = sqlite3.connect(":memory:")
    conn.executescript("".join(MIGRATIONS[:6]) + "PRAGMA user_version = 6;")
    conn.execute("INSERT INTO daily_candles VALUES ('US-AAA', 0, 1, 1, 1, 1, 1, 0)")
    conn.execute("INSERT INTO daily_candles VALUES ('KRW-BTC', 0, 1, 1, 1, 1, 1, 0)")
    conn.commit()

    CandleStore(conn)  # 마이그레이션 적용

    markets = [r[0] for r in conn.execute("SELECT market FROM daily_candles").fetchall()]
    assert markets == ["KRW-BTC"]
