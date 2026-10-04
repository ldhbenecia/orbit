import argparse
import json
import logging
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import uvicorn

from orbit.api.app import create_app
from orbit.backtest.compare import compare_lump_vs_dca, select_period
from orbit.backtest.metrics import Metrics
from orbit.marketdata.store import CandleStore
from orbit.marketdata.sync import sync_daily_candles
from orbit.marketdata.upbit_candles import BASE_URL

log = logging.getLogger("orbit")

# 실행 위치와 무관하게 레포 루트 data/ (gitignore) 에 저장
DEFAULT_DB = Path(__file__).resolve().parents[3] / "data" / "orbit.sqlite"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # 요청 URL 을 그대로 찍음 — 주문·계좌 요청이 생기면 식별자가 로그에 남음
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(prog="orbit")
    commands = parser.add_subparsers(dest="command", required=True)

    sync = commands.add_parser("sync-candles", help="업비트 일봉을 받아 로컬 DB 에 저장")
    sync.add_argument("--market", default="KRW-BTC")
    sync.add_argument("--db", type=Path, default=DEFAULT_DB)

    serve = commands.add_parser("serve", help="대시보드용 조회 API 실행 (이 기기에서만 접속)")
    serve.add_argument("--db", type=Path, default=DEFAULT_DB)
    serve.add_argument("--port", type=int, default=8000)

    commands.add_parser("openapi", help="API 명세(JSON)를 표준 출력으로 — 웹 타입 생성용")

    backtest = commands.add_parser("backtest", help="단순 보유 vs 적립식을 같은 총액으로 비교")
    backtest.add_argument("--market", default="KRW-BTC")
    backtest.add_argument("--start", type=_utc_date, default=_utc_date("2018-01-01"))
    backtest.add_argument("--end", type=_utc_date, default=datetime.max.replace(tzinfo=UTC))
    backtest.add_argument("--monthly", type=Decimal, default=Decimal(1_000_000))
    backtest.add_argument("--db", type=Path, default=DEFAULT_DB)

    args = parser.parse_args()
    if args.command == "sync-candles":
        _sync_candles(args.market, args.db)
    elif args.command == "serve":
        db = args.db
        # 외부 접속을 막기 위해 루프백에만 바인딩
        uvicorn.run(create_app(lambda: CandleStore.open(db)), host="127.0.0.1", port=args.port)
    elif args.command == "backtest":
        _backtest(args.market, args.start, args.end, args.monthly, args.db)
    elif args.command == "openapi":
        json.dump(
            create_app(lambda: CandleStore.open(DEFAULT_DB)).openapi(),
            sys.stdout,
            ensure_ascii=False,
            indent=2,
        )


def _sync_candles(market: str, db: Path) -> None:
    store = CandleStore.open(db)
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        result = sync_daily_candles(client, store, market, now=datetime.now(UTC))

    period = f"{result.first:%Y-%m-%d} ~ {result.last:%Y-%m-%d}" if result.first else "없음"
    log.info(
        "%s 일봉 %d개 저장 (진행 중인 봉 %d개 제외)", market, result.saved, result.skipped_open
    )
    log.info("누적 %d개, 기간 %s", result.total, period)
    if result.missing_days:
        days = ", ".join(f"{d:%Y-%m-%d}" for d in result.missing_days[:10])
        log.warning("빠진 날 %d일: %s", len(result.missing_days), days)


def _utc_date(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def _backtest(market: str, start: datetime, end: datetime, monthly: Decimal, db: Path) -> None:
    store = CandleStore.open(db)
    candles = select_period(store.load(market), start, end)
    store.close()
    if len(candles) < 2:
        log.error("기간 안에 일봉이 없음 — 먼저 orbit sync-candles 실행")
        return

    results = compare_lump_vs_dca(candles, monthly)
    log.info(
        "%s %s ~ %s, 매달 %s원 기준 (수수료·슬리피지·호가 단위 반영)\n",
        market,
        f"{candles[1].start:%Y-%m-%d}",
        f"{candles[-1].start:%Y-%m-%d}",
        f"{monthly:,.0f}",
    )
    names = list(results)
    log.info("%-18s %20s %20s", "", *names)
    for label, value in _ROWS:
        log.info("%-18s %20s %20s", label, *(value(results[n]) for n in names))


def _won(v: Decimal) -> str:
    return f"{v:,.0f}원"


def _pct(v: Decimal) -> str:
    return f"{v * 100:+.2f}%"


_ROWS: list[tuple[str, Callable[[Metrics], str]]] = [
    ("총 투입", lambda m: _won(m.invested)),
    ("최종 평가액", lambda m: _won(m.final_equity)),
    ("손익", lambda m: _won(m.profit)),
    ("투입 대비 수익률", lambda m: _pct(m.return_on_invested)),
    ("원금 대비 최악", lambda m: _pct(m.worst_vs_invested)),
    ("CAGR (기준가)", lambda m: _pct(m.cagr)),
    ("MDD (기준가)", lambda m: _pct(m.mdd)),
    ("최장 손실 기간", lambda m: f"{m.longest_underwater_days:,}일"),
    ("거래 횟수", lambda m: f"{m.trades:,}회"),
    ("수수료", lambda m: _won(m.fees)),
    ("슬리피지 비용", lambda m: _won(m.slippage)),
]
