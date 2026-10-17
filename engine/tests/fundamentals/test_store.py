import sqlite3
from datetime import UTC, date, datetime

from orbit.fundamentals.snapshot import Snapshot
from orbit.fundamentals.store import load_snapshots, save_snapshots

NOW = datetime(2026, 10, 17, tzinfo=UTC)


def snap(filed: date, shares: int | None) -> Snapshot:
    return Snapshot(filed, date(2026, 6, 30), 1, 2, 3, 4, 5, -6, shares)


def test_종목_단위로_통째로_바꿈() -> None:
    # 분할이 새로 감지되면 옛 보고서 주식 수도 바뀜 — 예전 줄이 남으면 안 됨
    conn = sqlite3.connect(":memory:")
    save_snapshots(conn, "US-EXA", [snap(date(2026, 5, 5), 100), snap(date(2026, 8, 5), 110)], NOW)
    save_snapshots(conn, "US-EXB", [snap(date(2026, 8, 5), 7)], NOW)

    save_snapshots(
        conn, "US-EXA", [snap(date(2026, 8, 5), 1_100), snap(date(2026, 11, 5), None)], NOW
    )

    assert load_snapshots(conn, "US-EXA") == [
        snap(date(2026, 8, 5), 1_100),
        snap(date(2026, 11, 5), None),
    ]
    assert load_snapshots(conn, "US-EXB") == [snap(date(2026, 8, 5), 7)]
