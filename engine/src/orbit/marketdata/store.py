import sqlite3
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from orbit.marketdata.candle import Candle

# 가격을 REAL 로 두면 float 오차가 생김 — Decimal 문자열(TEXT)로 저장
_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_candles (
    market TEXT NOT NULL,
    start_utc TEXT NOT NULL,
    open TEXT NOT NULL,
    high TEXT NOT NULL,
    low TEXT NOT NULL,
    close TEXT NOT NULL,
    volume TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (market, start_utc)
)
"""


class CandleStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.execute(_SCHEMA)

    @classmethod
    def open(cls, path: Path) -> "CandleStore":
        path.parent.mkdir(parents=True, exist_ok=True)
        return cls(sqlite3.connect(path))

    def close(self) -> None:
        self._conn.close()

    def upsert(self, candles: list[Candle]) -> None:
        with self._conn:
            self._conn.executemany(
                """
                INSERT INTO daily_candles VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (market, start_utc) DO UPDATE SET
                    open = excluded.open, high = excluded.high, low = excluded.low,
                    close = excluded.close, volume = excluded.volume, value = excluded.value
                """,
                [
                    (
                        c.market,
                        c.start.isoformat(),
                        str(c.open),
                        str(c.high),
                        str(c.low),
                        str(c.close),
                        str(c.volume),
                        str(c.value),
                    )
                    for c in candles
                ],
            )

    def load(self, market: str) -> list[Candle]:
        rows = self._conn.execute(
            "SELECT * FROM daily_candles WHERE market = ? ORDER BY start_utc", (market,)
        ).fetchall()
        return [
            Candle(
                market=row[0],
                start=datetime.fromisoformat(row[1]),
                open=Decimal(row[2]),
                high=Decimal(row[3]),
                low=Decimal(row[4]),
                close=Decimal(row[5]),
                volume=Decimal(row[6]),
                value=Decimal(row[7]),
            )
            for row in rows
        ]

    def latest_start(self, market: str) -> datetime | None:
        row = self._conn.execute(
            "SELECT MAX(start_utc) FROM daily_candles WHERE market = ?", (market,)
        ).fetchone()
        return datetime.fromisoformat(row[0]) if row and row[0] else None
