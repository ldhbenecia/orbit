import argparse
import json
import logging
import sqlite3
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import uvicorn

from orbit.api.app import create_app
from orbit.backtest.compare import compare_lump_vs_dca, select_period
from orbit.backtest.engine import DEFAULT_CONFIG, Funding, run_backtest
from orbit.backtest.metrics import Metrics, compute_metrics
from orbit.backtest.runs import RunSpec, save_run
from orbit.backtest.validate import check_rules, save_checks, specs_for
from orbit.brokers.dry_run import DryRunBroker
from orbit.dca.payday import RuleName, compare
from orbit.estimate.live import NextOpenView, build_view
from orbit.fundamentals.edgar import edgar_symbol, fetch_facts, fetch_tickers, has_share_class
from orbit.fundamentals.snapshot import snapshots
from orbit.fundamentals.store import fetched_since, save_snapshots
from orbit.ledger.book import Ledger
from orbit.marketdata.candle import Candle
from orbit.marketdata.demo import demo_candles, demo_names, demo_snapshots
from orbit.marketdata.fund_nav import Nav, fetch_ace_nav, fetch_tiger_nav
from orbit.marketdata.instruments import (
    COIN_MARKETS,
    DEFAULT_MARKETS_PATH,
    EXAMPLE_MARKETS_PATH,
    SEOUL,
    Universe,
    load_universe,
)
from orbit.marketdata.names import from_toss, save_names
from orbit.marketdata.store import CandleStore
from orbit.marketdata.sync import sync_daily_candles, sync_stock_daily
from orbit.marketdata.tiger_holdings import TIGER_BASE_URL, Holding, fetch_holdings
from orbit.marketdata.toss import BASE_URL as TOSS_BASE_URL
from orbit.marketdata.toss import TossMarketData
from orbit.marketdata.toss_rules import us_fee
from orbit.marketdata.upbit_candles import BASE_URL
from orbit.marketdata.upbit_ticker import try_fetch_ticker
from orbit.settings import Settings
from orbit.signals.today import Stance, is_upbit_market, today_signals
from orbit.strategies.registry import build_strategy
from orbit.trading.config import DEFAULT_CONFIG_PATH, load_config
from orbit.trading.daily import run_daily

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

    stocks = commands.add_parser(
        "sync-stocks", help="토스증권에서 등록한 주식·ETF 일봉을 받아 저장"
    )
    stocks.add_argument("--db", type=Path, default=DEFAULT_DB)

    fundamentals = commands.add_parser(
        "sync-fundamentals", help="SEC 공시에서 등록한 미국 종목의 재무를 받아 저장"
    )
    fundamentals.add_argument("--db", type=Path, default=DEFAULT_DB)

    serve = commands.add_parser("serve", help="대시보드용 조회 API 실행 (이 기기에서만 접속)")
    serve.add_argument("--db", type=Path, default=DEFAULT_DB)
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument(
        "--demo",
        action="store_true",
        help="외부 시세(업비트 현재가·토스)를 부르지 않음 — 가상 데이터 DB 와 함께",
    )

    demo = commands.add_parser(
        "demo-data", help="README 캡처용 가상 시세 DB 만들기 (실제 거래소 데이터 아님)"
    )
    demo.add_argument("--db", type=Path, default=DEFAULT_DB.with_name("demo.sqlite"))

    signal = commands.add_parser("signal", help="오늘의 규칙 신호 — 규칙마다 보유·현금·돌파 여부")
    signal.add_argument("--market", default="KRW-BTC")
    signal.add_argument("--db", type=Path, default=DEFAULT_DB)

    payday = commands.add_parser(
        "payday", help="미국 주식 월급날 규칙 비교 — 단순 적립·떨어지면 더·추세 아래면 대기"
    )
    payday.add_argument("--market", required=True, help="예: US-SPY")
    payday.add_argument("--monthly", type=Decimal, default=Decimal(1000), help="달러, 예시 금액")
    payday.add_argument("--db", type=Path, default=DEFAULT_DB)

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
    strategies.add_argument("--strategies", default="hold,ma-60,ma-120,ma-200,mom-365,vb-0.5")
    strategies.add_argument("--start", type=_utc_date, default=_utc_date("2018-01-01"))
    strategies.add_argument("--end", type=_utc_date, default=datetime.max.replace(tzinfo=UTC))
    strategies.add_argument("--initial", type=Decimal, default=Decimal(10_000_000))
    strategies.add_argument("--monthly", type=Decimal, default=Decimal(0))
    strategies.add_argument("--db", type=Path, default=DEFAULT_DB)

    dry = commands.add_parser(
        "dry-run", help="오늘 규칙대로 가상 장부에 사고팔기 (실제 주문 없음, 하루 한 번)"
    )
    dry.add_argument("--db", type=Path, default=DEFAULT_DB)
    dry.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)

    wallet = commands.add_parser("wallet", help="가상 장부 — 규칙 칸마다 예산·현금·보유·손익")
    wallet.add_argument("--db", type=Path, default=DEFAULT_DB)

    validate = commands.add_parser(
        "validate", help="규칙 검증 — 기간을 나눈 성과와 파라미터 민감도를 기록 (코인·미국주식)"
    )
    validate.add_argument("--market", action="append", help="여러 번 줄 수 있음. 없으면 전부")
    validate.add_argument("--db", type=Path, default=DEFAULT_DB)

    args = parser.parse_args()
    if args.command == "sync-candles":
        _sync_candles(args.market, args.db)
    elif args.command == "sync-stocks":
        _sync_stocks(args.db)
    elif args.command == "sync-fundamentals":
        _sync_fundamentals(args.db)
    elif args.command == "serve":
        db = args.db
        # 가상 데이터 화면은 예시 종목 목록으로 — 내 목록이 캡처에 섞이지 않게
        universe = load_universe(EXAMPLE_MARKETS_PATH if args.demo else DEFAULT_MARKETS_PATH)
        toss = None if args.demo else _toss_api()
        # 외부 접속을 막기 위해 루프백에만 바인딩
        app = create_app(
            lambda: sqlite3.connect(db),
            get_ticker=(lambda market: None) if args.demo else try_fetch_ticker,
            kr_trading_day_for=_kr_calendar(toss) if toss else None,
            next_open=_next_open(toss, universe) if toss else None,
            universe=universe,
        )
        uvicorn.run(app, host="127.0.0.1", port=args.port)
    elif args.command == "backtest":
        _backtest(args.market, args.start, args.end, args.monthly, args.db)
    elif args.command == "dry-run":
        _dry_run(args.db, args.config)
    elif args.command == "wallet":
        _wallet(args.db)
    elif args.command == "demo-data":
        _demo_data(args.db)
    elif args.command == "validate":
        _validate(args.market or validated_markets(load_universe()), args.db)
    elif args.command == "compare-strategies":
        _compare_strategies(args)
    elif args.command == "signal":
        _signal(args.market, args.db)
    elif args.command == "payday":
        _payday(args.market, args.monthly, args.db)
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


def _dry_run(db: Path, config_path: Path) -> None:
    config = load_config(config_path)
    if config is None:
        return
    conn = sqlite3.connect(db)
    try:
        report = run_daily(
            conn,
            config,
            DryRunBroker(),
            CandleStore(conn).load,
            try_fetch_ticker,
            datetime.now(UTC),
        )
    finally:
        conn.close()
    for line in report.lines:
        log.info("  %s", line)
    if report.stopped:
        log.error("정지: %s", report.stopped)
    log.info("dry-run — 실제 주문 없음. 주문 %d건 기록", report.orders)


def _wallet(db: Path) -> None:
    conn = sqlite3.connect(db)
    try:
        ledger = Ledger(conn, "dry-run")
        store = CandleStore(conn)
        for slot, market in ledger.slots():
            state = ledger.state(slot, market)
            candles = store.load(market)
            close = candles[-1].close if candles else Decimal(0)
            value = state.cash + state.qty * close
            log.info(
                "%s 예산 %s원 · 현금 %s원 · 보유 %s · 평가 %s원 (%+.1f%%) · 실현 %s원",
                slot,
                f"{state.budget:,.0f}",
                f"{state.cash:,.0f}",
                f"{state.qty.normalize():f}",
                f"{value:,.0f}",
                (value / state.budget - 1) * 100 if state.budget else 0,
                f"{state.realized:,.0f}",
            )
    finally:
        conn.close()


def _demo_data(db: Path) -> None:
    # 거래소 약관상 실제 시세는 공개 배포 금지 — README 화면은 이 가상 데이터로 찍음
    end = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    # 예시 종목 목록으로 — 가상 데이터 화면에 내 목록이 섞이지 않게
    universe = load_universe(EXAMPLE_MARKETS_PATH)
    markets = COIN_MARKETS + universe.markets
    store = CandleStore.open(db)
    for market in markets:
        start = (
            datetime(2018, 1, 1, tzinfo=UTC)
            if market.startswith("KRW-")
            else datetime(2016, 1, 1, tzinfo=UTC)
        )
        store.upsert(demo_candles(market, start, end), fetched_at=datetime.now(UTC))
    store.close()
    conn = sqlite3.connect(db)
    try:
        save_names(conn, demo_names(universe), datetime.now(UTC))
        for instrument in universe.instruments:
            if instrument.currency == "USD":
                snaps = demo_snapshots(instrument.market, date(2016, 1, 1), end.date())
                save_snapshots(conn, instrument.market, snaps, datetime.now(UTC))
    finally:
        conn.close()
    _validate(validated_markets(universe), db)
    log.info("가상 시세 DB: %s — uv run orbit serve --demo --db %s", db, db)


def validated_markets(universe: Universe) -> list[str]:
    # 코인 + 대시보드의 미국 종목. 국내 ETF 는 호가 단위를 공식 확인하기 전이라 제외
    us = [i.market for i in universe.instruments if i.dashboard and i.market.startswith("US-")]
    return COIN_MARKETS + us


def _validate(markets: list[str], db: Path) -> None:
    version = _code_version()
    now = datetime.now(UTC)
    conn = sqlite3.connect(db)
    try:
        for market in markets:
            candles = CandleStore(conn).load(market)
            rows = check_rules(market, candles, specs_for(market))
            save_checks(conn, market, rows, now, version)
            table = {(r.strategy, r.period): r for r in rows}
            whole = table[("hold", "all")]
            log.info(
                "%s 평가 %s ~ %s (코드 %s)",
                market,
                f"{whole.start:%Y-%m-%d}",
                f"{whole.end:%Y-%m-%d}",
                version,
            )
            log.info(
                "%-10s %9s %9s %9s %8s %6s %6s %8s",
                "",
                "CAGR 전체",
                "앞 절반",
                "뒤 절반",
                "MDD",
                "거래",
                "샤프",
                "우연 아님",
            )
            for spec in specs_for(market):
                a, f, b = (table[(spec, p)] for p in ("all", "first", "second"))
                log.info(
                    "%-10s %9s %9s %9s %8s %6d %6s %8s",
                    spec,
                    f"{a.cagr:+.1%}",
                    f"{f.cagr:+.1%}",
                    f"{b.cagr:+.1%}",
                    f"{a.mdd:.1%}",
                    a.trades,
                    f"{a.sharpe:.2f}",
                    "—" if a.edge_prob is None else f"{a.edge_prob:.0%}",
                )
    finally:
        conn.close()
    log.info("\n우연 아님: 시험한 규칙 수를 감안해도 샤프가 단순 보유보다 높은 게 우연이 아닐 확률")
    log.info("과거 데이터로 돌린 결과이며 앞으로도 같다는 뜻이 아님")


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


_STANCE_LABEL: dict[Stance, str] = {
    Stance.HOLD: "보유 구간",
    Stance.CASH: "현금 구간",
    Stance.BREAKOUT_WAIT: "돌파 대기",
    Stance.BREAKOUT_HIT: "돌파함",
    Stance.NOT_ENOUGH: "데이터 부족",
}


def _signal(market: str, db: Path) -> None:
    store = CandleStore.open(db)
    candles = store.load(market)
    store.close()
    if len(candles) < 2:
        log.error("일봉이 없음 — 먼저 orbit sync-candles 실행")
        return
    ticker = try_fetch_ticker(market) if is_upbit_market(market) else None
    if ticker:
        price = f"현재가 {ticker.price:,.0f}원"
    elif is_upbit_market(market):
        price = "현재가 조회 실패 — 돌파 여부 제외"
    else:
        price = "주식은 확정 일봉 기준"
    log.info("%s 규칙 신호 (%s 확정 봉 기준, %s)\n", market, f"{candles[-1].start:%Y-%m-%d}", price)
    for s in today_signals(market, candles, ticker):
        extra = f" · {s.days}일째" if s.days else ""
        if s.trigger is not None:
            extra = f" · 기준선 {s.trigger:,.0f}원"
        log.info("  %-8s %-10s [%s]%s", s.strategy, _STANCE_LABEL[s.stance], s.status, extra)
        log.info("           %s", s.reason)
    log.info("\n규칙이 말하는 상태일 뿐 투자 권유가 아님. 실험 중 규칙은 검증 전")


_PAYDAY_LABEL: dict[RuleName, str] = {
    "plain": "단순 적립",
    "dip": "떨어지면 더",
    "trend": "추세 아래면 대기",
}


def _payday(market: str, monthly: Decimal, db: Path) -> None:
    if not market.startswith("US-"):
        log.error("미국 주식만 — 예: --market US-SPY")
        return
    store = CandleStore.open(db)
    candles = store.load(market)
    store.close()
    result = compare(candles, monthly, lambda amount: us_fee(amount, "buy"))
    if result is None:
        log.error("일봉이 1년치보다 적음 — 먼저 orbit sync-stocks")
        return
    log.info(
        "%s 월급날(25일) 매달 $%s — %s ~ %s, 수수료 0.1%%\n",
        market,
        monthly,
        f"{result.start:%Y-%m-%d}",
        f"{candles[-1].start:%Y-%m-%d}",
    )
    log.info(
        "  %-14s %12s %12s %8s %8s  %s", "규칙", "넣은 돈", "평가액", "수익", "최악", "5년 구간"
    )
    for name, r in result.full.items():
        beat = result.beat_plain.get(name)
        log.info(
            "  %-14s %12s %12s %8s %8s  %s",
            _PAYDAY_LABEL[name],
            f"${r.invested:,.0f}",
            f"${r.final_value:,.0f}",
            _pct(r.final_value / r.invested - 1),
            _pct(r.worst_vs_invested),
            "기준"
            if name == "plain"
            else "구간 부족"
            if beat is None
            else f"단순 적립보다 나음 {beat * 100:.0f}%",
        )
    log.info("\n5년 구간 %d개 (매달 시작) 중 평가액이 단순 적립보다 컸던 비율", result.windows)
    log.info("다음 월급날 (%s 종가 기준)", f"{candles[-1].start:%Y-%m-%d}")
    for name, choice in result.latest.items():
        log.info("  %-14s %s", _PAYDAY_LABEL[name], choice.reason)
    log.info("\n과거 데이터에서 이랬다는 것 — 앞으로도 같다는 뜻이 아니고 투자 권유가 아님")


def _sync_stocks(db: Path) -> None:
    settings = Settings()
    if settings.toss_client_id is None or settings.toss_client_secret is None:
        log.error(".env 에 TOSS_CLIENT_ID · TOSS_CLIENT_SECRET 이 없음")
        return
    universe = load_universe()
    if not universe.instruments:
        return
    store = CandleStore.open(db)
    with httpx.Client(base_url=TOSS_BASE_URL, timeout=10) as client:
        api = TossMarketData(client, settings.toss_client_id, settings.toss_client_secret)
        # 이름·거래소는 토스 종목 정보에서 — 종목 목록에는 코드만 적으면 되게
        by_symbol = {i.symbol: i for i in universe.instruments}
        symbols = list(by_symbol)
        names = []
        for start in range(0, len(symbols), TOSS_BATCH):
            batch = ",".join(symbols[start : start + TOSS_BATCH])
            for row in api.get("/api/v1/stocks", {"symbols": batch})["result"]:
                if row["symbol"] in by_symbol:
                    names.append(from_toss(by_symbol[row["symbol"]], row))
        conn = sqlite3.connect(db)
        try:
            save_names(conn, names, datetime.now(UTC))
        finally:
            conn.close()
        missing = set(symbols) - {n.symbol for n in names}
        if missing:
            log.warning("토스에 없는 종목코드: %s", ", ".join(sorted(missing)))
        names_by_market = {n.market: n.name for n in names}
        for instrument in universe.instruments:
            if instrument.symbol in missing:
                continue
            result = sync_stock_daily(api, store, instrument, now=datetime.now(UTC))
            period = f"{result.first:%Y-%m-%d} ~ {result.last:%Y-%m-%d}" if result.first else "없음"
            if result.replaced:
                log.info(
                    "%s 수정주가가 바뀜 (액면분할 등) — 전 기간을 다시 받음", instrument.market
                )
            log.info(
                "%s %s 일봉 %d개 저장 (진행 중 %d개 제외), 누적 %d개 %s",
                instrument.market,
                names_by_market.get(instrument.market, instrument.symbol),
                result.saved,
                result.skipped_open,
                result.total,
                period,
            )
    store.close()


SEC_INTERVAL = 0.15  # SEC 는 초당 10회 이하만 허용
# 분기 공시라 하루 안에 다시 받을 일이 거의 없음 — 대시보드를 열 때마다 수십 MB 를 받지 않게
FUNDAMENTALS_FRESH = timedelta(days=1)


def _sync_fundamentals(db: Path) -> None:
    settings = Settings()
    if settings.sec_user_agent is None:
        log.error(".env 에 SEC_USER_AGENT 가 없음 — SEC 는 연락처(이름 이메일)를 요구함")
        return
    headers = {"User-Agent": settings.sec_user_agent.get_secret_value()}
    conn = sqlite3.connect(db)
    try:
        fresh = fetched_since(conn, datetime.now(UTC) - FUNDAMENTALS_FRESH)
        stocks = [
            i for i in load_universe().instruments if i.currency == "USD" and i.market not in fresh
        ]
        if not stocks:
            log.info("재무는 하루 안에 받은 것 그대로")
            return
        with httpx.Client(headers=headers, timeout=30) as client:
            ciks = fetch_tickers(client)
            for instrument in stocks:
                cik = ciks.get(edgar_symbol(instrument.symbol))
                if cik is None:
                    log.info("%s 재무 없음 (SEC 공시 회사 아님 — ETF 등)", instrument.market)
                    save_snapshots(conn, instrument.market, [], datetime.now(UTC))
                    continue
                time.sleep(SEC_INTERVAL)
                try:
                    # 주식 종류가 붙은 상장주는 회사 전체 가중평균 주식 수와 가격을 곱하지 않음
                    snaps = snapshots(
                        fetch_facts(client, cik),
                        weighted_fallback=not has_share_class(instrument.symbol),
                    )
                except httpx.HTTPError as error:
                    # 한 회사가 실패해도 나머지는 받음 — 시세와 무관한 참고 정보
                    log.warning("%s 재무 받기 실패 (%s)", instrument.market, type(error).__name__)
                    continue
                save_snapshots(conn, instrument.market, snaps, datetime.now(UTC))
                if snaps:
                    log.info(
                        "%s 보고서 %d개, 최근 %s 공시 (%s 기준)",
                        instrument.market,
                        len(snaps),
                        snaps[-1].filed,
                        snaps[-1].period_end,
                    )
                else:
                    log.info("%s 재무 없음 (미국 기업 연간·분기 보고서 없음)", instrument.market)
    finally:
        conn.close()


def _toss_api() -> TossMarketData | None:
    # 토큰은 클라이언트당 하나만 유효 — 서버 안에서는 이 클라이언트 하나만 씀
    settings = Settings()
    if settings.toss_client_id is None or settings.toss_client_secret is None:
        return None
    return TossMarketData(
        httpx.Client(base_url=TOSS_BASE_URL, timeout=10),
        settings.toss_client_id,
        settings.toss_client_secret,
    )


def _kr_calendar(api: TossMarketData) -> Callable[[date], date]:
    # 같은 날짜는 한 번만 물음
    cache: dict[date, date] = {}

    def trading_day_for(day: date) -> date:
        if day not in cache:
            cache[day] = api.kr_trading_day_for(day)
        return cache[day]

    return trading_day_for


# 토스 호출이 종목당 10번 넘게 일어남 — 시세 갱신 주기(1분)만큼만 재사용
TOSS_BATCH = 200  # 토스 종목 정보 한 번에 최대 200개
NEXT_OPEN_TTL = timedelta(minutes=1)
NAV_TTL = timedelta(minutes=10)
NEXT_OPEN_STALE = timedelta(minutes=5)  # 이보다 오래된 미리 계산 값은 쓰지 않음


class _SharedGets:
    # 장 캘린더·지금 환율은 세 ETF 가 똑같이 부름 — 초당 3회 그룹이라 같은 요청은 1분간 재사용
    def __init__(self, api: TossMarketData) -> None:
        self._api = api
        self._cache: dict[str, tuple[datetime, dict[str, Any]]] = {}

    def get(self, path: str, params: dict[str, str | int]) -> dict[str, Any]:
        key = f"{path}?{sorted(params.items())}"
        now = datetime.now(UTC)
        cached = self._cache.get(key)
        if cached is None or now - cached[0] >= NEXT_OPEN_TTL:
            cached = (now, self._api.get(path, params))
            self._cache[key] = cached
        return cached[1]

    def daily_candles(
        self, symbol: str, market: str, exchange_tz: ZoneInfo, since: date
    ) -> list[Candle]:
        return self._api.daily_candles(symbol, market, exchange_tz, since)


def _next_open(api: TossMarketData, universe: Universe) -> Callable[[str], NextOpenView]:
    targets = {i.market: i for i in universe.instruments if i.next_open is not None}
    source = _SharedGets(api)
    tiger = httpx.Client(base_url=TIGER_BASE_URL, timeout=10)
    fund_sites = httpx.Client(timeout=10)  # 운용사 기준가 (TIGER·ACE)
    holdings: dict[tuple[str, date], list[Holding]] = {}
    views: dict[str, tuple[datetime, NextOpenView]] = {}
    lock = threading.Lock()

    def holdings_for(fund: str) -> list[Holding]:
        # 운용사 구성 종목은 하루 한 번 바뀜
        key = (fund, datetime.now(SEOUL).date())
        if key not in holdings:
            holdings[key] = fetch_holdings(tiger, fund)
        return holdings[key]

    navs: dict[tuple[str, str], tuple[datetime, Nav | None]] = {}

    def nav_for(kind: str, fund: str) -> Nav | None:
        # 운용사 기준가는 장 마감 뒤 한 번 바뀜 — 10분마다만 다시 받음
        now = datetime.now(UTC)
        cached = navs.get((kind, fund))
        if cached is None or now - cached[0] >= NAV_TTL:
            fetch = fetch_tiger_nav if kind == "tiger" else fetch_ace_nav
            try:
                nav = fetch(fund_sites, fund)
            except (httpx.HTTPError, ValueError, TypeError, KeyError) as error:
                # 기준가는 보조 정보 — 운용사 응답이 바뀌어도 종가 기준 추정은 그대로 보임
                log.warning("기준가 조회 실패 %s %s: %s", kind, fund, type(error).__name__)
                nav = None
            cached = (now, nav)
            navs[(kind, fund)] = cached
        return cached[1]

    def refresh(market: str) -> NextOpenView:
        # 같은 종목을 백그라운드와 요청이 동시에 계산해 토스를 중복 호출하지 않게
        with lock:
            now = datetime.now(UTC)
            cached = views.get(market)
            if cached is None or now - cached[0] >= NEXT_OPEN_TTL:
                cached = (now, build_view(targets[market], source, holdings_for, now, nav_for))
                views[market] = cached
            return cached[1]

    def keep_fresh() -> None:
        # 요청이 토스 호출(1~2초)을 기다리지 않게 미리 계산해 둠
        while True:
            for market in targets:
                try:
                    refresh(market)
                except httpx.HTTPError as error:
                    log.warning("다음 개장 미리 계산 실패 %s: %s", market, type(error).__name__)
            time.sleep(NEXT_OPEN_TTL.total_seconds())

    threading.Thread(target=keep_fresh, name="next-open", daemon=True).start()

    def view_for(market: str) -> NextOpenView:
        # 백그라운드가 막혔으면(토스 오류 등) 오래된 값 대신 요청에서 다시 계산
        cached = views.get(market)
        if cached is not None and datetime.now(UTC) - cached[0] < NEXT_OPEN_STALE:
            return cached[1]
        return refresh(market)

    return view_for
