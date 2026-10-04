import sqlite3
from datetime import UTC, datetime
from decimal import Decimal

from orbit.backtest.engine import DEFAULT_CONFIG, Funding, run_backtest
from orbit.backtest.metrics import compute_metrics
from orbit.backtest.runs import RunSpec, latest_runs, load_trades, save_run
from orbit.db.migrations import MIGRATIONS
from orbit.marketdata.candle import Candle
from orbit.strategies.registry import build_strategy
from tests.backtest.test_engine import candles

NOW = datetime(2026, 10, 4, tzinfo=UTC)


def _spec(prices: list[Candle]) -> RunSpec:
    return RunSpec(
        market="KRW-BTC",
        strategy="ma-3",
        params={"window": "3"},
        start=prices[1].start,
        end=prices[-1].start,
        funding=Funding(initial=Decimal(1_000_000), monthly=Decimal(0)),
        config=DEFAULT_CONFIG,
        code_version="abc1234",
    )


def _run(conn: sqlite3.Connection) -> int:
    prices = candles([(1_000_000, 1_000_000 + i % 4 * 50_000) for i in range(30)])
    strategy, _ = build_strategy("ma-3")
    spec = _spec(prices)
    result = run_backtest(prices, strategy, spec.funding, spec.config)
    return save_run(conn, spec, compute_metrics(result), result.trades, NOW)


def test_조건과_지표와_매매를_함께_저장() -> None:
    conn = sqlite3.connect(":memory:")

    run_id = _run(conn)

    run = conn.execute(
        "SELECT strategy, params, code_version, fee_ppm, slippage_ppm, trades"
        " FROM backtest_runs WHERE id = ?",
        (run_id,),
    ).fetchone()
    stored = conn.execute(
        "SELECT COUNT(*) FROM backtest_trades WHERE run_id = ?", (run_id,)
    ).fetchone()
    assert run == ("ma-3", '{"window": "3"}', "abc1234", 500, 500, stored[0])
    assert stored[0] > 0


def test_체결가와_수량은_정확한_정수로() -> None:
    conn = sqlite3.connect(":memory:")
    run_id = _run(conn)

    price, qty = conn.execute(
        "SELECT price_krw, qty FROM backtest_trades WHERE run_id = ? ORDER BY seq LIMIT 1",
        (run_id,),
    ).fetchone()

    assert price % 1000 == 0  # 100만원 이상은 1,000원 호가
    assert isinstance(qty, int) and qty > 0


def test_다시_실행하면_새_기록으로_쌓임() -> None:
    conn = sqlite3.connect(":memory:")

    first, second = _run(conn), _run(conn)

    assert second != first
    assert conn.execute("SELECT COUNT(*) FROM backtest_runs").fetchone() == (2,)


def test_기록_테이블_추가는_기존_일봉을_보존() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(f"BEGIN;\n{MIGRATIONS[0]}\nPRAGMA user_version = 1;\nCOMMIT;")
    conn.execute("INSERT INTO daily_candles VALUES ('KRW-BTC', 0, 1, 1, 1, 1, 1, 0)")
    conn.commit()

    _run(conn)

    assert conn.execute("SELECT COUNT(*) FROM daily_candles").fetchone() == (1,)
    assert conn.execute("PRAGMA user_version").fetchone() == (len(MIGRATIONS),)


def test_전략마다_가장_최근_실행만_목록에() -> None:
    conn = sqlite3.connect(":memory:")
    _run(conn)
    latest = _run(conn)

    runs = latest_runs(conn, "KRW-BTC")

    assert [(r.id, r.strategy) for r in runs] == [(latest, "ma-3")]
    assert latest_runs(conn, "KRW-ETH") == []


def test_저장한_매매를_체결_순서대로_되읽음() -> None:
    conn = sqlite3.connect(":memory:")
    prices = candles([(1_000_000, 1_000_000 + i % 4 * 50_000) for i in range(30)])
    result = run_backtest(prices, build_strategy("ma-3")[0], _spec(prices).funding)
    run_id = save_run(conn, _spec(prices), compute_metrics(result), result.trades, NOW)

    loaded = load_trades(conn, run_id)

    assert [(t.day, t.side, t.qty, t.price) for t in loaded] == [
        (t.day, t.side, t.qty, t.price) for t in result.trades
    ]
