import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from orbit.ledger.book import QTY_SCALE, Mode, OrderRow
from orbit.settings import REPO_ROOT
from orbit.trading.config import ALLOWED_MARKETS, TradingConfig
from orbit.units import from_units

# 이 파일이 있으면 모든 주문을 막음 — 대시보드·알림·손으로 만들어도 됨
KILL_SWITCH = REPO_ROOT / "data" / "STOP"


@dataclass(frozen=True, slots=True)
class Verdict:
    ok: bool
    reason: str  # 거부 이유 — 로그·화면에 그대로


def check_order(
    conn: sqlite3.Connection,
    order: OrderRow,
    fee: Decimal,
    config: TradingConfig,
    mode: Mode,
    now: datetime,
    kill_switch: Path = KILL_SWITCH,
) -> Verdict:
    # 장부 계산을 믿지 않고 원본 기록을 직접 다시 셈 — 장부에 버그가 있어도 여기서 한 번 더 막음
    if mode != "dry-run":
        return Verdict(False, "실거래 경로 없음")
    if kill_switch.exists():
        return Verdict(False, "킬 스위치 켜짐")
    if order.market not in ALLOWED_MARKETS:
        return Verdict(False, f"허용되지 않은 종목 {order.market}")
    if order.qty <= 0 or order.price <= 0:
        return Verdict(False, "수량·가격이 0 이하")

    amount = order.qty * order.price
    # 매도는 상한을 두지 않음 — 상한 때문에 못 빠져나오는 게 더 위험. 매도는 보유분 검사로 막음
    if order.side == "buy" and amount + fee > config.limits.max_order_krw:
        return Verdict(False, "1회 주문 상한 초과")

    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    (today,) = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE mode = ? AND created_ts >= ? AND created_ts < ?",
        (mode, int(day_start.timestamp()), int((day_start + timedelta(days=1)).timestamp())),
    ).fetchone()
    if today >= config.limits.max_orders_per_day:
        return Verdict(False, "하루 주문 횟수 상한")

    if order.side == "buy":
        # 지금까지 넣은 돈(매수 − 매도 대금) 에 이번 매수를 더해도 총 예산 안
        invested = _net_invested(conn, mode)
        if invested + amount + fee > config.budget_krw:
            return Verdict(False, "총 예산 초과")
    else:
        # 엔진이 자기 주문으로 산 수량까지만 — 사용자가 직접 산 코인은 팔지 않음
        if order.qty > _engine_qty(conn, mode, order.slot):
            return Verdict(False, "엔진 보유분보다 많은 매도")
    return Verdict(True, "")


def _net_invested(conn: sqlite3.Connection, mode: Mode) -> Decimal:
    rows = conn.execute(
        "SELECT side, qty, price_krw, fee_krw FROM ledger_events WHERE kind = 'fill' AND mode = ?",
        (mode,),
    ).fetchall()
    total = Decimal(0)
    for side, qty, price, fee in rows:
        gross = from_units(qty, QTY_SCALE) * from_units(price, 0)
        total += gross + from_units(fee, 0) if side == "buy" else -(gross - from_units(fee, 0))
    return max(total, Decimal(0))


def _engine_qty(conn: sqlite3.Connection, mode: Mode, slot: str) -> Decimal:
    (units,) = conn.execute(
        "SELECT COALESCE(SUM(CASE side WHEN 'buy' THEN qty ELSE -qty END), 0) FROM ledger_events"
        " WHERE kind = 'fill' AND mode = ? AND slot = ?",
        (mode, slot),
    ).fetchone()
    return from_units(units, QTY_SCALE)
