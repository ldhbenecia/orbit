from collections.abc import Sequence
from decimal import Decimal

from orbit.marketdata.candle import Candle
from orbit.marketdata.price_format import format_price
from orbit.strategies.base import Decision, Strategy


def make_momentum(lookback: int) -> Strategy:
    # 시계열 모멘텀 — 지금 종가가 lookback 봉 전 종가보다 높으면 보유 (Moskowitz·Ooi·Pedersen 2012)
    def decide(candles: Sequence[Candle]) -> Decision:
        if len(candles) <= lookback:
            return Decision(Decimal(0), f"{lookback}봉 전 종가가 없어 판단 전", enough_data=False)
        before = candles[-lookback - 1].close
        close = candles[-1].close
        market = candles[-1].market
        # 주식은 주말·휴장일이 빠져 N 개 봉이 N 거래일 — 코인은 그냥 N 일
        days = "거래일" if market.startswith(("US-", "KRX-")) else "일"
        line = (
            f"{lookback}{days} 전 종가 {format_price(market, before)} → "
            f"종가 {format_price(market, close)} ({(close / before - 1) * 100:+.1f}%)"
        )
        if close > before:
            return Decision(Decimal(1), f"{line} — 올라서 보유", reference=before)
        return Decision(Decimal(0), f"{line} — 오르지 않아 현금", reference=before)

    return decide
