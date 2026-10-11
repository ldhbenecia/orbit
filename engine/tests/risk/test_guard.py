import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from orbit.ledger.book import Fill, Ledger, OrderRow, Side
from orbit.risk.guard import check_order
from orbit.trading.config import Limits, RuleConfig, TradingConfig

NOW = datetime(2026, 10, 5, 0, 5, tzinfo=UTC)
SLOT, MARKET = "KRW-BTC:ma-120", "KRW-BTC"
CONFIG = TradingConfig(
    budget_krw=Decimal(100000),
    limits=Limits(max_order_krw=Decimal(60000), max_orders_per_day=2),
    rules=[RuleConfig(market=MARKET, strategy="ma-120", weight=Decimal(1))],
)


def _order(side: Side, qty: str, price: int = 50_000_000, cid: str = "o1") -> OrderRow:
    return OrderRow(cid, SLOT, MARKET, side, Decimal(qty), Decimal(price), "unknown")


def _setup(tmp_path: Path) -> tuple[sqlite3.Connection, Ledger, Path]:
    conn = sqlite3.connect(tmp_path / "orbit.sqlite")
    return conn, Ledger(conn, "dry-run"), tmp_path / "STOP"


def _fill(ledger: Ledger, order: OrderRow) -> None:
    ledger.record_intent(order, NOW)
    fill = Fill(order.client_order_id, order.side, order.qty, order.price, Decimal(25))
    ledger.record_result(order, "filled", fill, "", NOW)


def test_예산_안의_매수는_통과(tmp_path: Path) -> None:
    conn, _, stop = _setup(tmp_path)

    verdict = check_order(conn, _order("buy", "0.001"), Decimal(25), CONFIG, "dry-run", NOW, stop)

    assert verdict.ok


def test_총_예산을_넘는_매수는_거부(tmp_path: Path) -> None:
    conn, ledger, stop = _setup(tmp_path)
    _fill(ledger, _order("buy", "0.001", cid="b1"))  # 50,025 원 투입

    verdict = check_order(
        conn, _order("buy", "0.001", cid="b2"), Decimal(25), CONFIG, "dry-run", NOW, stop
    )

    assert (verdict.ok, verdict.reason) == (False, "총 예산 초과")


def test_엔진이_산_것보다_많이_팔면_거부(tmp_path: Path) -> None:
    # 계좌에 사용자가 직접 산 코인이 있어도 엔진은 자기 주문으로 산 만큼만
    conn, ledger, stop = _setup(tmp_path)
    _fill(ledger, _order("buy", "0.001", cid="b1"))

    verdict = check_order(
        conn, _order("sell", "0.0011", cid="s1"), Decimal(25), CONFIG, "dry-run", NOW, stop
    )

    assert (verdict.ok, verdict.reason) == (False, "엔진 보유분보다 많은 매도")


def test_킬_스위치가_켜지면_모든_주문_거부(tmp_path: Path) -> None:
    conn, _, stop = _setup(tmp_path)
    stop.touch()

    verdict = check_order(conn, _order("buy", "0.0001"), Decimal(3), CONFIG, "dry-run", NOW, stop)

    assert (verdict.ok, verdict.reason) == (False, "킬 스위치 켜짐")


def test_1회_상한_하루_횟수_실거래_모드_허용_밖_종목은_거부(tmp_path: Path) -> None:
    conn, ledger, stop = _setup(tmp_path)

    too_big = check_order(conn, _order("buy", "0.0013"), Decimal(33), CONFIG, "dry-run", NOW, stop)
    live = check_order(conn, _order("buy", "0.0001"), Decimal(3), CONFIG, "live", NOW, stop)
    other = OrderRow("x", "KRW-XRP:ma-60", "KRW-XRP", "buy", Decimal(1), Decimal(1000), "unknown")
    not_allowed = check_order(conn, other, Decimal(1), CONFIG, "dry-run", NOW, stop)
    ledger.record_intent(_order("buy", "0.0001", cid="a"), NOW)
    ledger.record_intent(_order("buy", "0.0001", cid="b"), NOW)
    third = check_order(
        conn, _order("buy", "0.0001", cid="c"), Decimal(3), CONFIG, "dry-run", NOW, stop
    )

    assert too_big.reason == "1회 주문 상한 초과"
    assert live.reason == "실거래 경로 없음"
    assert not_allowed.reason == "허용되지 않은 종목 KRW-XRP"
    assert third.reason == "하루 주문 횟수 상한"


def test_매도는_1회_상한을_넘어도_엔진_보유분_안이면_통과(tmp_path: Path) -> None:
    conn, ledger, stop = _setup(tmp_path)
    _fill(ledger, _order("buy", "0.001", cid="b1"))
    big_price = 90_000_000  # 0.001 × 9천만 = 90,000 > 상한 60,000

    verdict = check_order(
        conn,
        _order("sell", "0.001", price=big_price, cid="s1"),
        Decimal(45),
        CONFIG,
        "dry-run",
        NOW,
        stop,
    )

    assert verdict.ok
