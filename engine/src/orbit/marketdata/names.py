import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from orbit.db.migrations import migrate
from orbit.marketdata.instruments import Instrument


@dataclass(frozen=True, slots=True)
class InstrumentName:
    market: str
    symbol: str
    name: str
    exchange: str
    currency: Literal["KRW", "USD"]


def from_toss(instrument: Instrument, row: dict[str, Any]) -> InstrumentName:
    # 토스 종목 정보 한 줄 → 캐시. 통화는 거래소가 아니라 응답 값 그대로
    return InstrumentName(
        instrument.market, instrument.symbol, row["name"], row["market"], row["currency"]
    )


def save_names(conn: sqlite3.Connection, names: list[InstrumentName], now: datetime) -> None:
    migrate(conn)
    with conn:
        conn.executemany(
            "INSERT INTO instruments (market, symbol, name, exchange, currency, fetched_ts)"
            " VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (market) DO UPDATE SET"
            " name = excluded.name, exchange = excluded.exchange,"
            " currency = excluded.currency, fetched_ts = excluded.fetched_ts",
            [
                (n.market, n.symbol, n.name, n.exchange, n.currency, int(now.timestamp()))
                for n in names
            ],
        )


def load_names(conn: sqlite3.Connection) -> dict[str, InstrumentName]:
    migrate(conn)
    rows = conn.execute(
        "SELECT market, symbol, name, exchange, currency FROM instruments"
    ).fetchall()
    return {row[0]: InstrumentName(*row) for row in rows}
