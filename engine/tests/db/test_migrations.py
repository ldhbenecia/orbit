import sqlite3

import pytest

from orbit.db import migrations
from orbit.db.migrations import MIGRATIONS, migrate


def _version(conn: sqlite3.Connection) -> int:
    version: int = conn.execute("PRAGMA user_version").fetchone()[0]
    return version


def test_빈_DB_에_전부_적용하고_버전을_기록() -> None:
    conn = sqlite3.connect(":memory:")

    migrate(conn)

    assert _version(conn) == len(MIGRATIONS)


def test_다시_실행해도_데이터가_그대로() -> None:
    conn = sqlite3.connect(":memory:")
    migrate(conn)
    conn.execute("INSERT INTO daily_candles VALUES ('KRW-BTC', 0, 1, 1, 1, 1, 1, 0)")
    conn.commit()

    migrate(conn)

    assert conn.execute("SELECT COUNT(*) FROM daily_candles").fetchone()[0] == 1


def test_초기_TEXT_스키마는_정수_스키마로_교체() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE daily_candles (market TEXT, start_utc TEXT, close TEXT)")
    conn.execute("INSERT INTO daily_candles VALUES ('KRW-BTC', '2024-01-01', '1.0')")
    conn.commit()

    migrate(conn)

    columns = [row[1] for row in conn.execute("PRAGMA table_info(daily_candles)")]
    assert "start_ts" in columns
    assert conn.execute("SELECT COUNT(*) FROM daily_candles").fetchone()[0] == 0


def test_STRICT_테이블은_정수_컬럼에_문자열을_거부() -> None:
    conn = sqlite3.connect(":memory:")
    migrate(conn)

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO daily_candles VALUES ('KRW-BTC', 0, '1.5', 1, 1, 1, 1, 0)")


def test_실패한_마이그레이션은_스키마와_버전_모두_되돌림(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = sqlite3.connect(":memory:")
    migrate(conn)
    broken = [*MIGRATIONS, "CREATE TABLE half_done (x INTEGER); SELECT * FROM no_such_table;"]
    monkeypatch.setattr(migrations, "MIGRATIONS", broken)

    with pytest.raises(sqlite3.OperationalError):
        migrate(conn)

    assert _version(conn) == len(MIGRATIONS)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
    assert "half_done" not in tables
