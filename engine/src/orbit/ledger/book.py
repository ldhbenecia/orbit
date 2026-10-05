import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from orbit.db.migrations import migrate
from orbit.units import from_units, to_units

QTY_SCALE = 8  # 코인 수량 최소 단위
Mode = Literal["dry-run", "live"]
Side = Literal["buy", "sell"]
OrderStatus = Literal["unknown", "filled", "rejected"]


@dataclass(frozen=True, slots=True)
class Fill:
    client_order_id: str
    side: Side
    qty: Decimal
    price: Decimal  # 원
    fee: Decimal  # 원 — 원 단위로 올린 값


@dataclass(frozen=True, slots=True)
class SlotState:
    slot: str
    market: str
    budget: Decimal  # 설정에서 정한 이 칸의 배정 예산
    cash: Decimal  # 예산 + 매도 대금 − 매수 비용(수수료 포함)
    qty: Decimal  # 엔진이 자기 주문으로 산 수량만
    cost: Decimal  # 지금 보유분의 매수 원가 (수수료 포함, 평균 단가)
    realized: Decimal  # 판 만큼의 실현 손익

    def available(self, reinvest_profit: bool) -> Decimal:
        # 계좌 잔고가 아니라 장부로 — 수익을 다시 넣지 않으면 예산 − 보유 원가를 넘지 않음
        if reinvest_profit:
            return max(self.cash, Decimal(0))
        return max(min(self.cash, self.budget - self.cost), Decimal(0))


@dataclass(frozen=True, slots=True)
class OrderRow:
    client_order_id: str
    slot: str
    market: str
    side: Side
    qty: Decimal
    price: Decimal
    status: OrderStatus


class Ledger:
    def __init__(self, conn: sqlite3.Connection, mode: Mode) -> None:
        migrate(conn)
        self._conn = conn
        self._mode = mode

    def state(self, slot: str, market: str) -> SlotState:
        rows = self._conn.execute(
            "SELECT kind, side, qty, price_krw, fee_krw, budget_krw FROM ledger_events"
            " WHERE slot = ? AND mode = ? ORDER BY id",
            (slot, self._mode),
        ).fetchall()
        budget = cash_flow = qty = cost = realized = Decimal(0)
        for kind, side, qty_units, price_units, fee_units, budget_units in rows:
            if kind == "budget":
                budget = from_units(budget_units, 0)
                continue
            q = from_units(qty_units, QTY_SCALE)
            gross = q * from_units(price_units, 0)
            fee = from_units(fee_units, 0)
            if side == "buy":
                cash_flow -= gross + fee
                cost += gross + fee
                qty += q
            else:
                proceeds = gross - fee
                released = cost * q / qty  # 평균 단가로 판 만큼의 원가
                cash_flow += proceeds
                realized += proceeds - released
                cost -= released
                qty -= q
        return SlotState(slot, market, budget, budget + cash_flow, qty, cost, realized)

    def record_budget(self, slot: str, market: str, budget: Decimal, now: datetime) -> None:
        # 배정 예산은 설정에서만 바뀌고, 바뀔 때마다 장부에 남김
        if self.state(slot, market).budget == budget:
            return
        with self._conn:
            self._conn.execute(
                "INSERT INTO ledger_events (ts, mode, slot, kind, market, budget_krw)"
                " VALUES (?, ?, ?, 'budget', ?, ?)",
                (int(now.timestamp()), self._mode, slot, market, to_units(budget, 0)),
            )

    def slots(self) -> list[tuple[str, str]]:
        # 장부에 한 번이라도 나온 칸 — 설정에서 빠진 칸도 보유분이 남아 있을 수 있어 장부 기준
        rows = self._conn.execute(
            "SELECT slot, market FROM ledger_events WHERE mode = ? GROUP BY slot, market"
            " ORDER BY MIN(id)",
            (self._mode,),
        ).fetchall()
        return [(slot, market) for slot, market in rows]

    def recent_fills(self, slot: str, limit: int = 10) -> list[tuple[datetime, Fill, str]]:
        rows = self._conn.execute(
            "SELECT ts, client_order_id, side, qty, price_krw, fee_krw, reason FROM ledger_events"
            " WHERE kind = 'fill' AND mode = ? AND slot = ? ORDER BY id DESC LIMIT ?",
            (self._mode, slot, limit),
        ).fetchall()
        return [
            (
                datetime.fromtimestamp(ts, UTC),
                Fill(
                    cid, side, from_units(qty, QTY_SCALE), from_units(price, 0), from_units(fee, 0)
                ),
                reason,
            )
            for ts, cid, side, qty, price, fee, reason in rows
        ]

    def find_order(self, client_order_id: str) -> OrderRow | None:
        row = self._conn.execute(
            "SELECT client_order_id, slot, market, side, qty, price_krw, status FROM orders"
            " WHERE client_order_id = ?",
            (client_order_id,),
        ).fetchone()
        return _order(row) if row else None

    def unknown_orders(self) -> list[OrderRow]:
        rows = self._conn.execute(
            "SELECT client_order_id, slot, market, side, qty, price_krw, status FROM orders"
            " WHERE status = 'unknown' AND mode = ? ORDER BY created_ts",
            (self._mode,),
        ).fetchall()
        return [_order(r) for r in rows]

    def record_intent(self, order: OrderRow, now: datetime) -> None:
        # 보내기 전에 결과 불명으로 먼저 남김 — 보낸 뒤 죽어도 다음 실행이 재주문하지 않음
        ts = int(now.timestamp())
        with self._conn:
            self._conn.execute(
                "INSERT INTO orders (client_order_id, mode, slot, market, side, qty, price_krw,"
                " status, created_ts, updated_ts) VALUES (?, ?, ?, ?, ?, ?, ?, 'unknown', ?, ?)",
                (
                    order.client_order_id,
                    self._mode,
                    order.slot,
                    order.market,
                    order.side,
                    to_units(order.qty, QTY_SCALE),
                    to_units(order.price, 0),
                    ts,
                    ts,
                ),
            )

    def record_result(
        self, order: OrderRow, status: OrderStatus, fill: Fill | None, reason: str, now: datetime
    ) -> None:
        # 주문 상태와 체결 기록을 한 트랜잭션으로 — 하나만 남는 일이 없게
        ts = int(now.timestamp())
        with self._conn:
            self._conn.execute(
                "UPDATE orders SET status = ?, updated_ts = ? WHERE client_order_id = ?",
                (status, ts, order.client_order_id),
            )
            if fill is not None:
                self._conn.execute(
                    "INSERT INTO ledger_events (ts, mode, slot, kind, market, client_order_id,"
                    " side, qty, price_krw, fee_krw, reason)"
                    " VALUES (?, ?, ?, 'fill', ?, ?, ?, ?, ?, ?, ?)",
                    (
                        ts,
                        self._mode,
                        order.slot,
                        order.market,
                        fill.client_order_id,
                        fill.side,
                        to_units(fill.qty, QTY_SCALE),
                        to_units(fill.price, 0),
                        to_units(fill.fee, 0),
                        reason,
                    ),
                )


def _order(row: tuple[str, str, str, Side, int, int, OrderStatus]) -> OrderRow:
    cid, slot, market, side, qty, price, status = row
    return OrderRow(
        cid, slot, market, side, from_units(qty, QTY_SCALE), from_units(price, 0), status
    )
