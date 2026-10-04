import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from orbit.db.migrations import migrate
from orbit.marketdata.candle import Candle
from orbit.units import from_units, to_units

# 마켓 앞부분별 가격 소수 자릿수
# KRW(업비트): 100원 이상 가격대만 호가가 1원 이상 단위라 저가 코인은 거부됨
# US: 1달러 미만 종목은 0.0001달러 단위라 4자리, KRX: 원 단위
QUOTE_SCALES = {"KRW": 0, "US": 4, "KRX": 0}
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

    def version(self, market: str) -> tuple[int, int | None]:
        # 봉 추가는 개수, 같은 봉 재수집은 받은 시각으로 바뀜 — 읽은 일봉을 다시 써도 되는지 판단용
        count, fetched = self._conn.execute(
            "SELECT COUNT(*), MAX(fetched_ts) FROM daily_candles WHERE market = ?", (market,)
        ).fetchone()
        return count, fetched

    def latest_start(self, market: str) -> datetime | None:
        (ts,) = self._conn.execute(
            "SELECT MAX(start_ts) FROM daily_candles WHERE market = ?", (market,)
        ).fetchone()
        return datetime.fromtimestamp(ts, UTC) if ts is not None else None
