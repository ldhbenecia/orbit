import sqlite3

# 적용된 마이그레이션은 고치거나 지우지 않음 — 변경은 항상 뒤에 추가
MIGRATIONS: list[str] = [
    # 1: 초기 TEXT 스키마는 시세 캐시라 다시 받으면 됨 — 버리고 정수 스키마로
    """
    DROP TABLE IF EXISTS daily_candles;
    CREATE TABLE daily_candles (
        market TEXT NOT NULL,
        start_ts INTEGER NOT NULL,   -- 봉 시작 시각, epoch 초 (UTC)
        open INTEGER NOT NULL,       -- 호가 통화 최소 단위 (원화는 원)
        high INTEGER NOT NULL,
        low INTEGER NOT NULL,
        close INTEGER NOT NULL,
        volume INTEGER NOT NULL,     -- 코인 수량 × 10^8
        fetched_ts INTEGER NOT NULL, -- 거래소에서 받은 시각, epoch 초 (UTC)
        PRIMARY KEY (market, start_ts)
    ) STRICT, WITHOUT ROWID;
    """,
]


def migrate(conn: sqlite3.Connection) -> int:
    current: int = conn.execute("PRAGMA user_version").fetchone()[0]
    for version, sql in enumerate(MIGRATIONS[current:], start=current + 1):
        try:
            # 스키마 변경과 버전 기록을 한 트랜잭션으로 — 중간에 실패하면 둘 다 되돌림
            conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {version};\nCOMMIT;")
        except sqlite3.Error:
            if conn.in_transaction:
                conn.rollback()
            raise
    return len(MIGRATIONS)
