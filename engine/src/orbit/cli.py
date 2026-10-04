import argparse
import json
import logging
import sqlite3
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import uvicorn

from orbit.api.app import create_app
from orbit.backtest.compare import compare_lump_vs_dca, select_period
from orbit.backtest.engine import DEFAULT_CONFIG, Funding, run_backtest
from orbit.backtest.metrics import Metrics, compute_metrics
from orbit.backtest.runs import RunSpec, save_run
from orbit.marketdata.store import CandleStore
from orbit.marketdata.sync import sync_daily_candles
from orbit.marketdata.upbit_candles import BASE_URL
from orbit.marketdata.upbit_ticker import try_fetch_ticker
from orbit.signals.today import Stance, today_signals
from orbit.strategies.registry import build_strategy

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

    signal = commands.add_parser("signal", help="오늘의 규칙 신호 — 규칙마다 보유·현금·돌파 여부")
    signal.add_argument("--market", default="KRW-BTC")
    signal.add_argument("--db", type=Path, default=DEFAULT_DB)

    commands.add_parser("openapi", help="API 명세(JSON)를 표준 출력으로 — 웹 타입 생성용")

    backtest = commands.add_parser("backtest", help="단순 보유 vs 적립식을 같은 총액으로 비교")
    backtest.add_argument("--market", default="KRW-BTC")
    backtest.add_argument("--start", type=_utc_date, default=_utc_date("2018-01-01"))
    backtest.add_argument("--end", type=_utc_date, default=datetime.max.replace(tzinfo=UTC))
    backtest.add_argument("--monthly", type=Decimal, default=Decimal(1_000_000))
    backtest.add_argument("--db", type=Path, default=DEFAULT_DB)

    strategies = commands.add_parser(
        "compare-strategies", help="여러 전략을 같은 조건으로 백테스트하고 결과를 기록"
    )
    strategies.add_argument("--market", default="KRW-BTC")
    strategies.add_argument("--strategies", default="hold,ma-60,ma-120,ma-200,vb-0.5")
    strategies.add_argument("--start", type=_utc_date, default=_utc_date("2018-01-01"))
    strategies.add_argument("--end", type=_utc_date, default=datetime.max.replace(tzinfo=UTC))
    strategies.add_argument("--initial", type=Decimal, default=Decimal(10_000_000))
    strategies.add_argument("--monthly", type=Decimal, default=Decimal(0))
    strategies.add_argument("--db", type=Path, default=DEFAULT_DB)

    args = parser.parse_args()
    if args.command == "sync-candles":
        _sync_candles(args.market, args.db)
    elif args.command == "serve":
        db = args.db
        # 외부 접속을 막기 위해 루프백에만 바인딩
        app = create_app(lambda: sqlite3.connect(db), get_ticker=try_fetch_ticker)
        uvicorn.run(app, host="127.0.0.1", port=args.port)
    elif args.command == "backtest":
        _backtest(args.market, args.start, args.end, args.monthly, args.db)
    elif args.command == "compare-strategies":
        _compare_strategies(args)
    elif args.command == "signal":
        _signal(args.market, args.db)
    elif args.command == "openapi":
        json.dump(
            create_app(lambda: sqlite3.connect(DEFAULT_DB)).openapi(),
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
    _print_table(results)


def _compare_strategies(args: argparse.Namespace) -> None:
    specs = [s.strip() for s in args.strategies.split(",") if s.strip()]
    built = {spec: build_strategy(spec) for spec in specs}
    store = CandleStore.open(args.db)
    candles = select_period(store.load(args.market), args.start, args.end)
    store.close()
    if len(candles) < 2:
        log.error("기간 안에 일봉이 없음 — 먼저 orbit sync-candles 실행")
        return

    funding = Funding(initial=args.initial, monthly=args.monthly)
    version = _code_version()
    now = datetime.now(UTC)
    results: dict[str, Metrics] = {}
    conn = sqlite3.connect(args.db)
    for spec, (strategy, params) in built.items():
        result = run_backtest(candles, strategy, funding, DEFAULT_CONFIG)
        results[spec] = compute_metrics(result)
        run_spec = RunSpec(
            market=args.market,
            strategy=spec,
            params=params,
            start=candles[1].start,
            end=candles[-1].start,
            funding=funding,
            config=DEFAULT_CONFIG,
            code_version=version,
        )
        save_run(conn, run_spec, results[spec], result.trades, now)
    conn.close()

    log.info(
        "%s %s ~ %s, 처음 %s원 + 매달 %s원 (수수료·슬리피지·호가 단위 반영, 코드 %s)\n",
        args.market,
        f"{candles[1].start:%Y-%m-%d}",
        f"{candles[-1].start:%Y-%m-%d}",
        f"{args.initial:,.0f}",
        f"{args.monthly:,.0f}",
        version,
    )
    _print_table(results)
    log.info("\n%d개 실행을 기록함", len(results))


def _print_table(results: dict[str, Metrics]) -> None:
    names = list(results)
    log.info("%-16s" + " %18s" * len(names), "", *names)
    for label, value in _ROWS:
        log.info("%-16s" + " %18s" * len(names), label, *(value(results[n]) for n in names))
    log.info("")
    for line in _GLOSSARY:
        log.info(line)


# 표 아래에 붙이는 용어 풀이 — 자세한 설명은 docs/knowledge/glossary.md
_GLOSSARY = [
    "용어",
    "  CAGR          1년에 평균 몇 %씩 불었나 (복리). 기간이 다른 결과끼리 비교할 때 씀",
    "  MDD           가장 비쌀 때 대비 가장 많이 떨어졌던 비율. 최악의 순간에 얼마나 아팠나",
    "  원금 대비 최악 넣은 돈 대비 평가액이 가장 나빴던 순간",
    "  최장 손실 기간 이전 고점을 회복하기까지 가장 오래 걸린 날 수",
    "  (기준가)      중간 입금 효과를 뺀 전략 자체의 성과",
    "  과거 데이터로 돌린 결과이며 앞으로도 같다는 뜻이 아님",
]


def _code_version() -> str:
    # 결과를 재현하려면 어떤 코드로 돌렸는지 알아야 함 — 커밋 안 된 변경이 있으면 -dirty
    try:
        out = subprocess.run(
            ["git", "describe", "--always", "--dirty"],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return out.stdout.strip()


def _won(v: Decimal) -> str:
    return f"{v:,.0f}원"


def _pct(v: Decimal) -> str:
    return f"{v * 100:+.2f}%"


_ROWS: list[tuple[str, Callable[[Metrics], str]]] = [
    ("총 투입", lambda m: _won(m.invested)),
    ("최종 평가액", lambda m: _won(m.final_equity)),
    ("손익", lambda m: _won(m.profit)),
    ("투입 대비 수익률", lambda m: _pct(m.return_on_invested)),
    ("원금 대비 최악", lambda m: _pct(m.worst_vs_invested) if m.worst_vs_invested else "손실 없음"),
    ("CAGR (기준가)", lambda m: _pct(m.cagr)),
    ("MDD (기준가)", lambda m: _pct(m.mdd)),
    ("최장 손실 기간", lambda m: f"{m.longest_underwater_days:,}일"),
    ("거래 횟수", lambda m: f"{m.trades:,}회"),
    ("수수료", lambda m: _won(m.fees)),
    ("슬리피지 비용", lambda m: _won(m.slippage)),
]


_STANCE_LABEL = {
    Stance.HOLD: "보유 구간",
    Stance.CASH: "현금 구간",
    Stance.BREAKOUT_WAIT: "돌파 대기",
    Stance.BREAKOUT_HIT: "돌파함",
}


def _signal(market: str, db: Path) -> None:
    store = CandleStore.open(db)
    candles = store.load(market)
    store.close()
    if len(candles) < 2:
        log.error("일봉이 없음 — 먼저 orbit sync-candles 실행")
        return
    ticker = try_fetch_ticker(market)
    price = f"현재가 {ticker.price:,.0f}원" if ticker else "현재가 조회 실패 — 돌파 여부 제외"
    log.info("%s 규칙 신호 (%s 확정 봉 기준, %s)\n", market, f"{candles[-1].start:%Y-%m-%d}", price)
    for s in today_signals(candles, ticker):
        extra = f" · {s.days}일째" if s.days else ""
        if s.trigger is not None:
            extra = f" · 기준선 {s.trigger:,.0f}원"
        log.info("  %-8s %-10s [%s]%s", s.strategy, _STANCE_LABEL[s.stance], s.status, extra)
        log.info("           %s", s.reason)
    log.info("\n규칙이 말하는 상태일 뿐 투자 권유가 아님. 실험 중 규칙은 검증 전")
