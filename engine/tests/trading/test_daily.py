import sqlite3
from collections.abc import Sequence
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from orbit.brokers.base import Broker, BrokerResult
from orbit.brokers.dry_run import DryRunBroker
from orbit.db.migrations import migrate
from orbit.ledger.book import Fill, Ledger, Mode, OrderRow
from orbit.marketdata.candle import ONE_DAY, Candle
from orbit.marketdata.upbit_ticker import Ticker
from orbit.trading.config import Limits, RuleConfig, TradingConfig
from orbit.trading.daily import RunReport, run_daily
from tests.backtest.test_engine import candles

BUDGET = Decimal(100000)
CONFIG = TradingConfig(
    budget_krw=BUDGET,
    limits=Limits(max_order_krw=BUDGET, max_orders_per_day=5),
    rules=[RuleConfig(market="KRW-BTC", strategy="ma-2", weight=Decimal(1))],
)
RISING = candles([(50_000_000, 50_000_000), (50_000_000, 51_000_000), (51_000_000, 52_000_000)])
FALLING = RISING + candles([(52_000_000, 40_000_000)], start=RISING[-1].start + ONE_DAY)


class Env:
    def __init__(self, tmp_path: Path, history: Sequence[Candle]) -> None:
        self.conn = sqlite3.connect(tmp_path / "orbit.sqlite")
        migrate(self.conn)
        self.stop = tmp_path / "STOP"
        self.history = list(history)

    def run(self, broker: Broker, open_price: int = 52_000_000) -> RunReport:
        today = self.history[-1].start + ONE_DAY
        ticker = Ticker(
            day=today, open=Decimal(open_price), high=Decimal(open_price), price=Decimal(open_price)
        )
        now = today + timedelta(minutes=5)
        return run_daily(
            self.conn,
            CONFIG,
            broker,
            lambda m: self.history,
            lambda m: ticker,
            now,
            self.stop,
        )

    def orders(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0])


def test_평균_위면_예산_안에서_사고_같은_날_다시_돌려도_주문은_한_번(tmp_path: Path) -> None:
    env = Env(tmp_path, RISING)
    broker = DryRunBroker()

    first = env.run(broker)
    second = env.run(broker)

    assert first.orders == 1 and second.orders == 0
    assert "오늘 이미 처리함" in second.lines[0]
    state = Ledger(env.conn, "dry-run").state("KRW-BTC:ma-2", "KRW-BTC")
    assert Decimal(0) < BUDGET - state.cash  # 실제로 샀고
    assert state.cash >= 0  # 수수료를 원 단위로 올려도 예산을 넘지 않음


def test_평균_아래로_내려가면_엔진이_산_수량만_판다(tmp_path: Path) -> None:
    env = Env(tmp_path, RISING)
    env.run(DryRunBroker())
    bought = Ledger(env.conn, "dry-run").state("KRW-BTC:ma-2", "KRW-BTC").qty

    env.history = FALLING
    report = env.run(DryRunBroker(), open_price=40_000_000)

    assert report.orders == 1 and "매도" in report.lines[0]
    sold = env.conn.execute("SELECT qty FROM orders WHERE side = 'sell'").fetchone()[0]
    assert Decimal(sold).scaleb(-8) == bought
    assert Ledger(env.conn, "dry-run").state("KRW-BTC:ma-2", "KRW-BTC").qty == 0


def test_킬_스위치가_켜지면_주문_0(tmp_path: Path) -> None:
    env = Env(tmp_path, RISING)
    env.stop.touch()

    report = env.run(DryRunBroker())

    assert report.stopped is not None and env.orders() == 0


class UnknownBroker:
    # 응답이 없는 거래소 흉내 — 주문은 보냈는지 모르는 상태
    mode: Mode = "dry-run"

    def __init__(self) -> None:
        self.resolved: BrokerResult | None = None
        self.placed = 0

    def place_limit_order(self, order: OrderRow) -> BrokerResult:
        self.placed += 1
        return BrokerResult("unknown", None, "타임아웃")

    def get_order(self, client_order_id: str) -> BrokerResult:
        return self.resolved or BrokerResult("unknown", None)


def test_결과를_모르는_주문이_있으면_확인될_때까지_새_주문을_내지_않음(tmp_path: Path) -> None:
    env = Env(tmp_path, RISING)
    broker = UnknownBroker()

    first = env.run(broker)
    env.history = FALLING  # 다음 날 — 원래라면 매도 판단
    second = env.run(broker)

    assert first.stopped and second.stopped
    assert broker.placed == 1 and env.orders() == 1  # 재주문 없음

    cid = env.conn.execute("SELECT client_order_id, qty, price_krw FROM orders").fetchone()
    broker.resolved = BrokerResult(
        "filled", Fill(cid[0], "buy", Decimal(cid[1]).scaleb(-8), Decimal(cid[2]), Decimal(30))
    )
    third = env.run(broker)

    assert any("결과 확인: filled" in line for line in third.lines)


def test_오늘_시가를_모르면_주문하지_않음(tmp_path: Path) -> None:
    env = Env(tmp_path, RISING)
    stale = Ticker(day=RISING[-1].start, open=Decimal(1), high=Decimal(1), price=Decimal(1))
    now = RISING[-1].start + ONE_DAY + timedelta(minutes=5)

    report = run_daily(
        env.conn, CONFIG, DryRunBroker(), lambda m: RISING, lambda m: stale, now, env.stop
    )

    assert report.orders == 0 and "시가를 확인 못 해" in report.lines[0]


def test_설정_모드와_브로커_모드가_다르면_멈춤(tmp_path: Path) -> None:
    env = Env(tmp_path, RISING)
    broker = DryRunBroker()
    broker.mode = "live"

    assert env.run(broker).stopped == "설정 모드와 브로커 모드가 다름"
    assert env.orders() == 0


def test_1회_상한을_넘는_매수는_상한까지만_사고_남은_건_다음_날(tmp_path: Path) -> None:
    capped = CONFIG.model_copy(
        update={"limits": Limits(max_order_krw=Decimal(30000), max_orders_per_day=5)}
    )
    env = Env(tmp_path, RISING)
    today = RISING[-1].start + ONE_DAY
    ticker = Ticker(day=today, open=Decimal(52_000_000), high=Decimal(1), price=Decimal(1))

    report = run_daily(
        env.conn,
        capped,
        DryRunBroker(),
        lambda m: RISING,
        lambda m: ticker,
        today + timedelta(minutes=5),
        env.stop,
    )

    state = Ledger(env.conn, "dry-run").state("KRW-BTC:ma-2", "KRW-BTC")
    assert report.orders == 1
    assert Decimal(0) < BUDGET - state.cash <= Decimal(30000)
