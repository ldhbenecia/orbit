import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from orbit.backtest.engine import BacktestConfig, Funding, Trade
from orbit.backtest.metrics import Metrics
from orbit.db.migrations import migrate
from orbit.marketdata.store import VOLUME_SCALE
from orbit.units import round_to_units, to_units

PPM = 6


@dataclass(frozen=True, slots=True)
class RunSpec:
    market: str
    strategy: str
    params: dict[str, str]
    start: datetime
    end: datetime
    funding: Funding
    config: BacktestConfig
    code_version: str


def save_run(
    conn: sqlite3.Connection,
    spec: RunSpec,
    metrics: Metrics,
    trades: Sequence[Trade],
    created_at: datetime,
) -> int:
    migrate(conn)
    with conn:
        cursor = conn.execute(
            """
            INSERT INTO backtest_runs (
                created_ts, code_version, market, strategy, params, start_ts, end_ts,
                initial_krw, monthly_krw, fee_ppm, slippage_ppm,
                invested_krw, final_equity_krw, fees_krw, slippage_krw,
                return_ppm, worst_ppm, cagr_ppm, mdd_ppm, longest_underwater_days, trades
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(created_at.timestamp()),
                spec.code_version,
                spec.market,
                spec.strategy,
                json.dumps(spec.params, sort_keys=True),
                int(spec.start.timestamp()),
                int(spec.end.timestamp()),
                _won(spec.funding.initial),
                _won(spec.funding.monthly),
                round_to_units(spec.config.fee_rate, PPM),
                round_to_units(spec.config.slippage_rate, PPM),
                _won(metrics.invested),
                _won(metrics.final_equity),
                _won(metrics.fees),
                _won(metrics.slippage),
                round_to_units(metrics.return_on_invested, PPM),
                round_to_units(metrics.worst_vs_invested, PPM),
                round_to_units(metrics.cagr, PPM),
                round_to_units(metrics.mdd, PPM),
                metrics.longest_underwater_days,
                metrics.trades,
            ),
        )
        run_id = cursor.lastrowid
        if run_id is None:
            raise RuntimeError("백테스트 실행 기록 id 를 받지 못함")
        conn.executemany(
            """
            INSERT INTO backtest_trades (run_id, seq, ts, side, qty, price_krw, fee_krw, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    seq,
                    int(t.day.timestamp()),
                    t.side,
                    to_units(t.qty, VOLUME_SCALE),
                    to_units(t.price, 0),
                    _won(t.fee),
                    t.reason,
                )
                for seq, t in enumerate(trades)
            ],
        )
    return run_id


def _won(value: Decimal) -> int:
    return round_to_units(value, 0)
