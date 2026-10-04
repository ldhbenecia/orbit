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
    # 2: 백테스트 실행 기록 — 분석 산출물이라 원 미만 금액은 원 단위 반올림, 비율은 ppm
    """
    CREATE TABLE backtest_runs (
        id INTEGER PRIMARY KEY,
        created_ts INTEGER NOT NULL,
        code_version TEXT NOT NULL,     -- 실행한 코드의 git 커밋
        market TEXT NOT NULL,
        strategy TEXT NOT NULL,         -- 예: ma-120
        params TEXT NOT NULL,           -- JSON
        start_ts INTEGER NOT NULL,
        end_ts INTEGER NOT NULL,
        initial_krw INTEGER NOT NULL,
        monthly_krw INTEGER NOT NULL,
        fee_ppm INTEGER NOT NULL,
        slippage_ppm INTEGER NOT NULL,
        invested_krw INTEGER NOT NULL,
        final_equity_krw INTEGER NOT NULL,
        fees_krw INTEGER NOT NULL,
        slippage_krw INTEGER NOT NULL,
        return_ppm INTEGER NOT NULL,
        worst_ppm INTEGER NOT NULL,
        cagr_ppm INTEGER NOT NULL,
        mdd_ppm INTEGER NOT NULL,
        longest_underwater_days INTEGER NOT NULL,
        trades INTEGER NOT NULL
    ) STRICT;
    CREATE INDEX backtest_runs_by_strategy ON backtest_runs (market, strategy, created_ts);
    CREATE TABLE backtest_trades (
        run_id INTEGER NOT NULL REFERENCES backtest_runs (id) ON DELETE CASCADE,
        seq INTEGER NOT NULL,
        ts INTEGER NOT NULL,            -- 체결일 봉 시작, epoch 초 (UTC)
        side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
        qty INTEGER NOT NULL,           -- 코인 수량 × 10^8
        price_krw INTEGER NOT NULL,     -- 호가 단위로 맞춘 체결가
        fee_krw INTEGER NOT NULL,
        reason TEXT NOT NULL,
        PRIMARY KEY (run_id, seq)
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
