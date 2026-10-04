from collections.abc import Sequence
from decimal import Decimal

from orbit.indicators.moving_average import sma
from orbit.marketdata.candle import Candle
from orbit.strategies.base import Decision, Strategy


def make_ma_filter(window: int) -> Strategy:
    def decide(candles: Sequence[Candle]) -> Decision:
        closes = [c.close for c in candles[-window:]]
        average = sma(closes, window)
        if average is None:
            return Decision(Decimal(0), f"{window}일선 계산에 필요한 일봉 부족")
        close = closes[-1]
        line = f"종가 {close:,.0f}원 · {window}일선 {average:,.0f}원"
        if close > average:
            return Decision(Decimal(1), f"{line} — 선 위라서 보유")
        return Decision(Decimal(0), f"{line} — 선 아래라서 현금")

    return decide
