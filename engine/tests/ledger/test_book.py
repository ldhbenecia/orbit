import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from orbit.ledger.book import Fill, Ledger, OrderRow, Side

T = datetime(2026, 10, 5, 0, 5, tzinfo=UTC)
SLOT, MARKET = "KRW-BTC:ma-120", "KRW-BTC"


def _ledger(tmp_path: Path) -> Ledger:
    return Ledger(sqlite3.connect(tmp_path / "orbit.sqlite"), "dry-run")


def _trade(ledger: Ledger, cid: str, side: Side, qty: str, price: int, fee: int) -> None:
    order = OrderRow(cid, SLOT, MARKET, side, Decimal(qty), Decimal(price), "unknown")
    ledger.record_intent(order, T)
    ledger.record_result(
        order, "filled", Fill(cid, order.side, order.qty, order.price, Decimal(fee)), "", T
    )


def test_사고_팔면_현금_수량_원가_실현손익이_맞음(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.record_budget(SLOT, MARKET, Decimal(100000), T)

    _trade(ledger, "b1", "buy", "0.001", 50_000_000, 25)  # 50,000 + 25
    _trade(ledger, "s1", "sell", "0.0005", 60_000_000, 15)  # 30,000 − 15

    state = ledger.state(SLOT, MARKET)
    assert state.qty == Decimal("0.0005")
    assert state.cash == Decimal(100000) - 50025 + 29985
    assert state.cost == Decimal("25012.5")  # 남은 절반의 원가
    assert state.realized == Decimal(29985) - Decimal("25012.5")


def test_수익을_다시_넣지_않으면_쓸_수_있는_돈은_예산_빼기_보유_원가(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.record_budget(SLOT, MARKET, Decimal(100000), T)
    _trade(ledger, "b1", "buy", "0.001", 50_000_000, 25)
    _trade(ledger, "s1", "sell", "0.001", 80_000_000, 40)  # 30,000 원 남짓 이익

    state = ledger.state(SLOT, MARKET)

    assert state.cash > Decimal(100000)
    assert state.available(reinvest_profit=False) == Decimal(100000)
    assert state.available(reinvest_profit=True) == state.cash


def test_손실이_나면_쓸_수_있는_돈도_줄어듦(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.record_budget(SLOT, MARKET, Decimal(100000), T)
    _trade(ledger, "b1", "buy", "0.001", 50_000_000, 25)
    _trade(ledger, "s1", "sell", "0.001", 40_000_000, 20)

    assert ledger.state(SLOT, MARKET).available(reinvest_profit=False) == Decimal(
        100000 - 50025 + 39980
    )


def test_예산은_바뀔_때만_기록(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.record_budget(SLOT, MARKET, Decimal(100000), T)
    ledger.record_budget(SLOT, MARKET, Decimal(100000), T)
    ledger.record_budget(SLOT, MARKET, Decimal(80000), T)

    count = ledger._conn.execute("SELECT COUNT(*) FROM ledger_events").fetchone()[0]
    assert count == 2 and ledger.state(SLOT, MARKET).budget == Decimal(80000)


def test_같은_주문_번호는_두_번_기록되지_않음(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _trade(ledger, "b1", "buy", "0.001", 50_000_000, 25)

    with pytest.raises(sqlite3.IntegrityError):
        _trade(ledger, "b1", "buy", "0.001", 50_000_000, 25)


def test_수량_자릿수가_넘치면_반올림하지_않고_거부(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    order = OrderRow("b1", SLOT, MARKET, "buy", Decimal("0.000000001"), Decimal(1), "unknown")

    with pytest.raises(ValueError):
        ledger.record_intent(order, T)
