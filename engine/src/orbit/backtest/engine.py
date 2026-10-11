from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from typing import Literal

from orbit.marketdata.candle import Candle
from orbit.marketdata.upbit_rules import FEE_RATE_KRW, MIN_ORDER_KRW, round_to_tick
from orbit.strategies.base import Strategy

QTY_STEP = Decimal("1e-8")  # 코인 수량 최소 단위


@dataclass(frozen=True, slots=True)
class Funding:
    initial: Decimal  # 첫 거래일에 한 번
    monthly: Decimal  # 매달 첫 거래일마다 (첫 거래일 포함)


def _rate_fee(rate: Decimal) -> Callable[[Decimal, Literal["buy", "sell"]], Decimal]:
    return lambda amount, side: amount * rate


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    # 기본값은 업비트 원화 마켓 코인
    fee_rate: Decimal = FEE_RATE_KRW
    # 거래소 공식 값이 아닌 가정 — KRW-BTC 실측 스프레드 약 0.03% 의 여유를 둔 보수값
    slippage_rate: Decimal = Decimal("0.0005")
    min_order: Decimal = MIN_ORDER_KRW
    qty_step: Decimal = QTY_STEP  # 수량 최소 단위 — 주식은 1주
    round_price: Callable[[Decimal, bool], Decimal] = round_to_tick  # 호가 단위 (매수 올림)
    # 체결 금액 → 수수료. 없으면 금액 × fee_rate. 주식은 절사·매도 세금이 있어 따로 줌
    fee: Callable[[Decimal, Literal["buy", "sell"]], Decimal] | None = None

    def fee_for(self, amount: Decimal, side: Literal["buy", "sell"]) -> Decimal:
        return (self.fee or _rate_fee(self.fee_rate))(amount, side)


DEFAULT_CONFIG = BacktestConfig()


@dataclass(frozen=True, slots=True)
class Trade:
    day: datetime
    side: Literal["buy", "sell"]
    qty: Decimal
    price: Decimal  # 슬리피지·호가 단위 반영 체결가
    fee: Decimal
    slippage_cost: Decimal
    reason: str


@dataclass(frozen=True, slots=True)
class DailyRecord:
    day: datetime
    deposit: Decimal
    invested: Decimal  # 누적 투입 원금
    cash: Decimal
    qty: Decimal
    equity: Decimal  # 종가 기준 평가액
    nav: Decimal  # 기준가 — 입금 효과를 뺀 전략 성과 (시작 1)


@dataclass(slots=True)
class BacktestResult:
    records: list[DailyRecord] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)


def run_backtest(
    candles: Sequence[Candle],
    strategy: Strategy,
    funding: Funding,
    config: BacktestConfig = DEFAULT_CONFIG,
) -> BacktestResult:
    result = BacktestResult()
    cash = Decimal(0)
    qty = Decimal(0)
    units = Decimal(0)
    invested = Decimal(0)

    # 첫 봉은 판단 재료로만 씀 — i 일 판단은 i-1 일까지 확정 봉, 체결은 i 일 시가
    for i in range(1, len(candles)):
        today = candles[i]
        decision = strategy(candles[:i])

        deposit = _deposit(funding, candles, i)
        if deposit:
            equity_at_open = cash + qty * today.open
            nav_at_open = equity_at_open / units if units else Decimal(1)
            units += deposit / nav_at_open
            cash += deposit
            invested += deposit

        orders = [(today.open, decision.target_weight, decision.reason)]
        entry = decision.entry
        if entry is not None:
            trigger = today.open + entry.breakout
            # 고가가 기준선에 닿은 날만 체결 — 닿은 시각은 모르므로 기준선 가격 체결로 가정
            if today.high >= trigger:
                orders.append((trigger, entry.weight, entry.reason))
        for price, weight, reason in orders:
            trade = rebalance_order(today.start, price, cash, qty, weight, reason, config)
            if trade is None:
                continue
            result.trades.append(trade)
            if trade.side == "buy":
                cash -= trade.qty * trade.price + trade.fee
                qty += trade.qty
            else:
                cash += trade.qty * trade.price - trade.fee
                qty -= trade.qty

        equity = cash + qty * today.close
        result.records.append(
            DailyRecord(
                day=today.start,
                deposit=deposit,
                invested=invested,
                cash=cash,
                qty=qty,
                equity=equity,
                nav=equity / units if units else Decimal(1),
            )
        )
    return result


def _deposit(funding: Funding, candles: Sequence[Candle], i: int) -> Decimal:
    first_day = i == 1
    new_month = candles[i].start.month != candles[i - 1].start.month
    amount = funding.initial if first_day else Decimal(0)
    if first_day or new_month:
        amount += funding.monthly
    return amount


def rebalance_order(
    day: datetime,
    price: Decimal,
    cash: Decimal,
    qty: Decimal,
    target_weight: Decimal,
    reason: str,
    config: BacktestConfig,
) -> Trade | None:
    equity = cash + qty * price
    diff = target_weight * equity - qty * price
    if abs(diff) < config.min_order:
        return None

    if diff > 0:
        exec_price = config.round_price(price * (1 + config.slippage_rate), True)
        # 수수료까지 현금 안에서 내도록 수량을 내림 — 예산을 넘는 쪽으로 반올림하지 않음
        budget = min(diff, cash)
        buy_qty = (budget / (exec_price * (1 + config.fee_rate))).quantize(
            config.qty_step, ROUND_DOWN
        )
        if buy_qty <= 0 or buy_qty * exec_price < config.min_order:
            return None
        return Trade(
            day=day,
            side="buy",
            qty=buy_qty,
            price=exec_price,
            fee=config.fee_for(buy_qty * exec_price, "buy"),
            slippage_cost=buy_qty * (exec_price - price),
            reason=reason,
        )

    exec_price = config.round_price(price * (1 - config.slippage_rate), False)
    sell_qty = min(qty, -diff / price).quantize(config.qty_step, ROUND_DOWN)
    if sell_qty <= 0 or sell_qty * exec_price < config.min_order:
        return None
    return Trade(
        day=day,
        side="sell",
        qty=sell_qty,
        price=exec_price,
        fee=config.fee_for(sell_qty * exec_price, "sell"),
        slippage_cost=sell_qty * (price - exec_price),
        reason=reason,
    )
