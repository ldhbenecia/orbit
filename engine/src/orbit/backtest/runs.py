import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from orbit.backtest.engine import BacktestConfig, Funding, Trade
from orbit.backtest.metrics import Metrics
from orbit.db.migrations import migrate
from orbit.marketdata.store import VOLUME_SCALE
from orbit.units import from_units, round_to_units, to_units

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


@dataclass(frozen=True, slots=True)
class RunSummary:
    id: int
    strategy: str
    created_at: datetime
    code_version: str
    start: datetime
    end: datetime
    cagr: Decimal
    mdd: Decimal
    trades: int


@dataclass(frozen=True, slots=True)
class SavedTrade:
    day: datetime
    side: Literal["buy", "sell"]
    qty: Decimal
    price: Decimal
    reason: str


def latest_runs(conn: sqlite3.Connection, market: str) -> list[RunSummary]:
    # 전략마다 가장 최근 실행 하나 — 차트에서 고를 목록
    migrate(conn)
    rows = conn.execute(
        """
        SELECT id, strategy, created_ts, code_version, start_ts, end_ts, cagr_ppm, mdd_ppm, trades
        FROM backtest_runs AS r
        WHERE market = ? AND id = (
            SELECT MAX(id) FROM backtest_runs WHERE market = r.market AND strategy = r.strategy
        )
        ORDER BY strategy
        """,
        (market,),
    ).fetchall()
    return [
        RunSummary(
            id=row[0],
            strategy=row[1],
            created_at=datetime.fromtimestamp(row[2], UTC),
            code_version=row[3],
            start=datetime.fromtimestamp(row[4], UTC),
            end=datetime.fromtimestamp(row[5], UTC),
            cagr=from_units(row[6], PPM),
            mdd=from_units(row[7], PPM),
            trades=row[8],
        )
        for row in rows
    ]


def load_trades(conn: sqlite3.Connection, run_id: int) -> list[SavedTrade]:
    migrate(conn)
    rows = conn.execute(
        "SELECT ts, side, qty, price_krw, reason"
        " FROM backtest_trades WHERE run_id = ? ORDER BY seq",
        (run_id,),
    ).fetchall()
    return [
        SavedTrade(
            day=datetime.fromtimestamp(ts, UTC),
            side=side,
            qty=from_units(qty, VOLUME_SCALE),
            price=from_units(price, 0),
            reason=reason,
        )
        for ts, side, qty, price, reason in rows
    ]
