from collections.abc import Sequence
from decimal import Decimal

from orbit.indicators.moving_average import sma
from orbit.marketdata.candle import Candle
from orbit.marketdata.price_format import format_price
from orbit.strategies.base import Decision, Strategy


def make_ma_filter(window: int) -> Strategy:
    def decide(candles: Sequence[Candle]) -> Decision:
        closes = [c.close for c in candles[-window:]]
        average = sma(closes, window)
        if average is None:
            return Decision(Decimal(0), f"최근 {window}일 평균을 계산하기엔 일봉 부족")
        close = closes[-1]
        market = candles[-1].market
        # 주식은 주말·휴장일이 빠져 N 개 봉이 N 거래일 — 코인은 그냥 N 일
        days = "거래일" if market.startswith(("US-", "KRX-")) else "일"
        gap = close / average - 1
        line = (
            f"종가 {format_price(market, close)} · 최근 {window}{days} 평균 "
            f"{format_price(market, average)} ({gap * 100:+.1f}%)"
        )
        if close > average:
            return Decision(Decimal(1), f"{line} — 평균보다 높아서 보유", reference=average)
        return Decision(Decimal(0), f"{line} — 평균보다 낮아서 현금", reference=average)

    return decide
