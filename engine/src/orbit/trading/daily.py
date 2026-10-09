import logging
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from pathlib import Path

from orbit.backtest.engine import DEFAULT_CONFIG, rebalance_order
from orbit.brokers.base import Broker
from orbit.brokers.dry_run import dry_run_fee
from orbit.ledger.book import Ledger, OrderRow
from orbit.marketdata.candle import ONE_DAY, Candle
from orbit.marketdata.upbit_ticker import Ticker
from orbit.risk.guard import KILL_SWITCH, check_order
from orbit.strategies.registry import build_strategy
from orbit.trading.config import TradingConfig

log = logging.getLogger(__name__)


@dataclass(slots=True)
class RunReport:
    lines: list[str] = field(default_factory=list)  # 규칙마다 무엇을 했는지 — 화면·로그에 그대로
    orders: int = 0
    stopped: str | None = None  # 멈춘 이유 — 있으면 새 주문 없음


def run_daily(
    conn: sqlite3.Connection,
    config: TradingConfig,
    broker: Broker,
    candles_for: Callable[[str], Sequence[Candle]],
    ticker_for: Callable[[str], Ticker | None],
    now: datetime,
    kill_switch: Path = KILL_SWITCH,
) -> RunReport:
    report = RunReport()
    mode = config.ledger_mode
    if broker.mode != mode:
        report.stopped = "설정 모드와 브로커 모드가 다름"
        return report
    if kill_switch.exists():
        report.stopped = "킬 스위치 켜짐 — 새 주문 없음"
        return report

    ledger = Ledger(conn, mode)
    # 결과를 모르는 주문이 있으면 먼저 확정 — 확정 전에 새 주문을 내면 이중 주문이 될 수 있음
    for pending in ledger.unknown_orders():
        result = broker.get_order(pending.client_order_id)
        if result.status == "unknown":
            report.stopped = f"결과를 모르는 주문 {pending.client_order_id} — 확인 전 새 주문 안 함"
            return report
        ledger.record_result(pending, result.status, result.fill, "나중에 확인", now)
        report.lines.append(f"{pending.client_order_id} 결과 확인: {result.status}")

    for rule in config.rules:
        slot, market = rule.slot, rule.market
        ledger.record_budget(slot, market, rule.budget(config.budget_krw), now)
        # 판단은 확정된 봉만 — 백테스트와 같은 전략 함수
        candles = [c for c in candles_for(market) if c.is_closed(now)]
        ticker = ticker_for(market)
        if not candles or ticker is None or ticker.day != candles[-1].start + ONE_DAY:
            report.lines.append(f"{slot}: 오늘 시가를 확인 못 해 건너뜀")
            continue
        cid = f"{slot}:{ticker.day.date().isoformat()}"
        if ledger.find_order(cid) is not None:
            report.lines.append(f"{slot}: 오늘 이미 처리함")
            continue

        strategy, _ = build_strategy(rule.strategy)
        decision = strategy(candles)
        state = ledger.state(slot, market)
        cash = state.available(config.reinvest_profit)
        # 수량 계산도 백테스트와 같은 함수 — 시가 체결, 슬리피지·호가·최소 주문
        trade = rebalance_order(
            ticker.day,
            ticker.open,
            cash,
            state.qty,
            decision.target_weight,
            decision.reason,
            DEFAULT_CONFIG,
        )
        if trade is None:
            report.lines.append(f"{slot}: 할 것 없음 — {decision.reason}")
            continue

        qty = trade.qty
        if trade.side == "buy":
            # 1회 상한을 넘는 매수는 나눠서 — 남은 만큼은 다음 날 같은 판단이면 이어서 삼
            limit = min(cash, config.limits.max_order_krw)
            if qty * trade.price > limit:
                qty = (limit / (trade.price * (1 + DEFAULT_CONFIG.fee_rate))).quantize(
                    DEFAULT_CONFIG.qty_step, ROUND_DOWN
                )
            # 수수료를 원 단위로 올리면 1원이라도 넘을 수 있음 — 넘으면 수량을 한 단계씩 줄임
            while qty > 0 and qty * trade.price + dry_run_fee(qty * trade.price) > limit:
                qty -= DEFAULT_CONFIG.qty_step
            if qty * trade.price < DEFAULT_CONFIG.min_order:
                report.lines.append(f"{slot}: 최소 주문 금액 미만이라 건너뜀")
                continue
        order = OrderRow(cid, slot, market, trade.side, qty, trade.price, "unknown")
        verdict = check_order(
            conn, order, dry_run_fee(qty * trade.price), config, mode, now, kill_switch
        )
        if not verdict.ok:
            report.lines.append(f"{slot}: 가드가 막음 — {verdict.reason}")
            continue

        ledger.record_intent(order, now)
        try:
            result = broker.place_limit_order(order)
        except Exception:
            # 돈 경로의 예상 못 한 예외 — 주문을 결과 불명으로 남겨 재주문을 막고 정지
            log.exception("주문 중 예외: %s", cid)
            report.stopped = f"주문 중 예외 {cid} — 결과 불명으로 남김"
            return report
        ledger.record_result(order, result.status, result.fill, decision.reason, now)
        report.orders += 1
        side = "매수" if order.side == "buy" else "매도"
        report.lines.append(
            f"{slot}: {side} {_fmt_qty(order.qty)} @ {order.price:,.0f}원 → {result.status}"
        )
        if result.status == "unknown":
            report.stopped = f"주문 {cid} 결과 불명 — 확인 전 새 주문 안 함"
            return report
    return report


def _fmt_qty(qty: Decimal) -> str:
    return f"{qty.normalize():f}"
