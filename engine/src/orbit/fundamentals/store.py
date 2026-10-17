import sqlite3
from datetime import UTC, date, datetime

from orbit.db.migrations import migrate
from orbit.fundamentals.snapshot import Snapshot

_VALUES = "net_income, revenue, revenue_prev, operating_cf, capex, equity, shares"


def _ts(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp())


def _day(ts: int) -> date:
    return datetime.fromtimestamp(ts, UTC).date()


def save_snapshots(
    conn: sqlite3.Connection, market: str, snapshots: list[Snapshot], now: datetime
) -> None:
    # 분할이 새로 나오면 옛 보고서 주식 수도 바뀜 — 종목 단위로 통째로 바꿈
    migrate(conn)
    with conn:
        conn.execute("DELETE FROM fundamentals WHERE market = ?", (market,))
        conn.executemany(
            f"INSERT INTO fundamentals (market, filed_ts, period_end_ts, {_VALUES}, fetched_ts)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    market,
                    _ts(s.filed),
                    _ts(s.period_end),
                    s.net_income,
                    s.revenue,
                    s.revenue_prev,
                    s.operating_cf,
                    s.capex,
                    s.equity,
                    s.shares,
                    int(now.timestamp()),
                )
                for s in snapshots
            ],
        )
        conn.execute(
            "INSERT INTO fundamentals_fetched (market, fetched_ts) VALUES (?, ?)"
            " ON CONFLICT (market) DO UPDATE SET fetched_ts = excluded.fetched_ts",
            (market, int(now.timestamp())),
        )


def load_snapshots(conn: sqlite3.Connection, market: str) -> list[Snapshot]:
    migrate(conn)
    rows = conn.execute(
        f"SELECT filed_ts, period_end_ts, {_VALUES} FROM fundamentals"
        " WHERE market = ? ORDER BY filed_ts",
        (market,),
    ).fetchall()
    return [Snapshot(_day(r[0]), _day(r[1]), *r[2:]) for r in rows]


def fetched_since(conn: sqlite3.Connection, since: datetime) -> set[str]:
    migrate(conn)
    rows = conn.execute(
        "SELECT market FROM fundamentals_fetched WHERE fetched_ts >= ?",
        (int(since.timestamp()),),
    ).fetchall()
    return {row[0] for row in rows}
