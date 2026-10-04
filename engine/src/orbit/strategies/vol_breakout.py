from collections.abc import Sequence
from decimal import Decimal

from orbit.marketdata.candle import Candle
from orbit.strategies.base import Decision, Entry, Strategy


def make_vol_breakout(k: Decimal) -> Strategy:
    def decide(candles: Sequence[Candle]) -> Decision:
        prev = candles[-1]
        span = prev.high - prev.low
        return Decision(
            target_weight=Decimal(0),
            reason="전날 돌파로 산 물량은 시가에 정리",
            entry=Entry(
                breakout=span * k,
                weight=Decimal(1),
                reason=f"시가 + 전날 변동폭 {span:,.0f}원 × {k} 돌파",
            ),
        )

    return decide
