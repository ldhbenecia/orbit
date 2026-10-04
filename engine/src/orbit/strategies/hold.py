from collections.abc import Sequence
from decimal import Decimal

from orbit.marketdata.candle import Candle
from orbit.strategies.base import Decision


def always_hold(candles: Sequence[Candle]) -> Decision:
    return Decision(target_weight=Decimal(1), reason="항상 전액 보유")
