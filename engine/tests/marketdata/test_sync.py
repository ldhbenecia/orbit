import sqlite3
from datetime import UTC, datetime, timedelta

from orbit.marketdata.store import CandleStore
from orbit.marketdata.sync import sync_daily_candles
from tests.marketdata.fake_upbit import FakeUpbit

FIRST = datetime(2024, 1, 1, tzinfo=UTC)
TODAY = datetime(2024, 3, 1, tzinfo=UTC)
NOW = TODAY + timedelta(hours=5)  # 오늘 봉이 아직 진행 중인 시각


def _store() -> CandleStore:
    return CandleStore(sqlite3.connect(":memory:"))


def test_진행_중인_오늘_봉은_저장하지_않음() -> None:
    store = _store()

    result = sync_daily_candles(
        FakeUpbit(FIRST, TODAY).client(), store, "KRW-BTC", NOW, lambda _: None
    )

    assert result.skipped_open == 1
    assert store.latest_start("KRW-BTC") == TODAY - timedelta(days=1)


def test_다시_실행해도_중복_없이_이어_붙음() -> None:
    store = _store()
    sync_daily_candles(FakeUpbit(FIRST, TODAY).client(), store, "KRW-BTC", NOW, lambda _: None)

    next_now = NOW + timedelta(days=1)
    result = sync_daily_candles(
        FakeUpbit(FIRST, TODAY + timedelta(days=1)).client(),
        store,
        "KRW-BTC",
        next_now,
        lambda _: None,
    )

    assert result.total == (TODAY - FIRST).days + 1
    assert result.last == TODAY
    assert result.missing_days == []


def test_저장한_가격은_Decimal_그대로_되읽힘() -> None:
    store = _store()
    sync_daily_candles(FakeUpbit(FIRST, TODAY).client(), store, "KRW-BTC", NOW, lambda _: None)

    candle = store.load("KRW-BTC")[0]

    assert str(candle.close) == "100000000.0"
    assert candle.start.tzinfo is not None
