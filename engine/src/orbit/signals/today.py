from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from orbit.marketdata.candle import ONE_DAY, Candle
from orbit.marketdata.upbit_rules import round_to_tick
from orbit.marketdata.upbit_ticker import Ticker
from orbit.strategies.base import Strategy
from orbit.strategies.registry import build_strategy, strategy_status

STREAK_LIMIT = 400  # 며칠째인지 거슬러 세는 최대 일수
COIN_SIGNAL_STRATEGIES = ("ma-60", "ma-120", "ma-200", "vb-0.5")
# 주식 변동성 돌파는 장중 시가·달러 호가 단위가 필요해 아직 제외
STOCK_SIGNAL_STRATEGIES = ("ma-60", "ma-120", "ma-200")


class Stance(StrEnum):
    HOLD = "hold"  # 규칙상 보유 구간
    CASH = "cash"  # 규칙상 현금 구간
    BREAKOUT_WAIT = "breakout_wait"  # 기준선에 닿으면 매수
    BREAKOUT_HIT = "breakout_hit"  # 오늘 기준선에 닿음


@dataclass(frozen=True, slots=True)
class Signal:
    strategy: str
    status: str  # 기준선 · 실험 중 · 채택
    stance: Stance
    reason: str
    days: int | None  # 오늘 포함 같은 판단이 이어진 일수, 돌파형은 매일 새로 판단해 없음
    trigger: Decimal | None  # 돌파 기준선 가격 — 오늘 시가를 모르면 없음
    close: Decimal  # 판단에 쓴 마지막 확정 봉 종가
    reference: Decimal | None  # 판단 기준 가격 (이동평균 등)


def today_signal(spec: str, candles: Sequence[Candle], ticker: Ticker | None) -> Signal:
    strategy, _ = build_strategy(spec)
    status = strategy_status(spec)
    decision = strategy(candles)
    close = candles[-1].close
    entry = decision.entry
    if entry is not None:
        # 시세가 마지막 확정 봉 바로 다음 날 것이 아니면 기준선이 틀어짐 — 계산하지 않음
        if ticker is None or ticker.day != candles[-1].start + ONE_DAY:
            return Signal(spec, status, Stance.BREAKOUT_WAIT, entry.reason, None, None, close, None)
        # 실제로 걸 수 있는 지정가 — 백테스트 체결처럼 매수 쪽(올림)으로 호가에 맞춤
        trigger = round_to_tick(ticker.open + entry.breakout, up=True)
        stance = Stance.BREAKOUT_HIT if ticker.high >= trigger else Stance.BREAKOUT_WAIT
        return Signal(spec, status, stance, entry.reason, None, trigger, close, None)

    stance = Stance.HOLD if decision.target_weight > 0 else Stance.CASH
    days = _streak(strategy, candles, decision.target_weight)
    return Signal(spec, status, stance, decision.reason, days, None, close, decision.reference)


def signal_strategies(market: str) -> tuple[str, ...]:
    return COIN_SIGNAL_STRATEGIES if is_upbit_market(market) else STOCK_SIGNAL_STRATEGIES


def is_upbit_market(market: str) -> bool:
    return market.startswith("KRW-")


def today_signals(market: str, candles: Sequence[Candle], ticker: Ticker | None) -> list[Signal]:
    return [today_signal(spec, candles, ticker) for spec in signal_strategies(market)]


def _streak(strategy: Strategy, candles: Sequence[Candle], weight: Decimal) -> int:
    days = 1
    for end in range(len(candles) - 1, max(len(candles) - STREAK_LIMIT, 1), -1):
        if strategy(candles[:end]).target_weight != weight:
            break
        days += 1
    return days
