from datetime import UTC, datetime, timedelta
from decimal import Decimal

from orbit.backtest.compare import compare_lump_vs_dca, month_starts, select_period
from tests.backtest.test_engine import candles


def test_입금일은_첫_거래일과_매달_첫날() -> None:
    start = datetime(2024, 1, 30, tzinfo=UTC)

    assert month_starts(candles([(100, 100)] * 33, start)) == 3  # 1/31, 2/1, 3/1


def test_단순_보유와_적립식은_같은_총액을_투입() -> None:
    start = datetime(2024, 1, 30, tzinfo=UTC)

    results = compare_lump_vs_dca(candles([(100_000, 100_000)] * 33, start), Decimal(100_000))

    assert {m.invested for m in results.values()} == {Decimal(300_000)}


def test_기간은_시작일_판단용_전날_봉을_포함() -> None:
    all_candles = candles([(100, 100)] * 10)
    start = all_candles[3].start

    period = select_period(all_candles, start, start + timedelta(days=2))

    assert [c.start for c in period] == [c.start for c in all_candles[2:6]]
