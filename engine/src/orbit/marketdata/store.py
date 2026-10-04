import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from orbit.db.migrations import migrate
from orbit.marketdata.candle import Candle
from orbit.units import from_units, to_units

QUOTE_SCALES = {"KRW": 0}  # 호가 통화별 소수 자릿수 — 원화 마켓 호가는 1원 이상 단위
VOLUME_SCALE = 8  # 코인 수량 최소 단위 (사토시)

_COLUMNS = "market, start_ts, open, high, low, close, volume, fetched_ts"


def price_scale(market: str) -> int:
    quote = market.split("-", 1)[0]
    if quote not in QUOTE_SCALES:
        raise ValueError(f"지원하지 않는 호가 통화: {market}")
    return QUOTE_SCALES[quote]


class CandleStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        migrate(conn)

    @classmethod
    def open(cls, path: Path) -> "CandleStore":
        path.parent.mkdir(parents=True, exist_ok=True)
        return cls(sqlite3.connect(path))

    def close(self) -> None:
        self._conn.close()

    def upsert(self, candles: list[Candle], fetched_at: datetime) -> None:
        fetched_ts = int(fetched_at.timestamp())
        rows = []
        for c in candles:
            scale = price_scale(c.market)
            rows.append(
                (
                    c.market,
                    int(c.start.timestamp()),
                    to_units(c.open, scale),
                    to_units(c.high, scale),
                    to_units(c.low, scale),
                    to_units(c.close, scale),
                    to_units(c.volume, VOLUME_SCALE),
                    fetched_ts,
                )
            )
        with self._conn:
            self._conn.executemany(
                f"""
                INSERT INTO daily_candles ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (market, start_ts) DO UPDATE SET
                    open = excluded.open, high = excluded.high, low = excluded.low,
                    close = excluded.close, volume = excluded.volume,
                    fetched_ts = excluded.fetched_ts
                """,
                rows,
            )

    def load(self, market: str) -> list[Candle]:
        scale = price_scale(market)
        rows = self._conn.execute(
            "SELECT start_ts, open, high, low, close, volume"
            " FROM daily_candles WHERE market = ? ORDER BY start_ts",
            (market,),
        ).fetchall()
        return [
            Candle(
                market=market,
                start=datetime.fromtimestamp(start_ts, UTC),
                open=from_units(open_, scale),
                high=from_units(high, scale),
                low=from_units(low, scale),
                close=from_units(close, scale),
                volume=from_units(volume, VOLUME_SCALE),
            )
            for start_ts, open_, high, low, close, volume in rows
        ]

    def latest_start(self, market: str) -> datetime | None:
        (ts,) = self._conn.execute(
            "SELECT MAX(start_ts) FROM daily_candles WHERE market = ?", (market,)
        ).fetchone()
        return datetime.fromtimestamp(ts, UTC) if ts is not None else None
