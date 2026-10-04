import math
import random
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from orbit.marketdata.candle import ONE_DAY, Candle

# README 화면 캡처용 가상 시세 — 거래소 데이터는 약관상 공개 배포할 수 없음
# 실제 종목과 무관한 무작위 경로. 화면에서는 "가상 데이터"·예시 종목 이름으로만 보여줌


def demo_candles(market: str, start: datetime, end: datetime) -> list[Candle]:
    coin = market.startswith("KRW-")
    us = market.startswith("US-")
    rng = random.Random(market)  # 종목마다 다르지만 매번 같은 경로
    price = 50_000_000.0 if coin else 100.0 if us else 10_000.0
    drift, vol = (0.0008, 0.035) if coin else (0.0003, 0.012)
    step = Decimal("0.01") if us else Decimal(1)
    candles = []
    day = start
    while day <= end:
        # 주식은 주말 휴장
        if coin or day.weekday() < 5:
            open_ = price
            close = open_ * math.exp(rng.gauss(drift, vol))
            high = max(open_, close) * (1 + abs(rng.gauss(0, vol / 2)))
            low = min(open_, close) * (1 - abs(rng.gauss(0, vol / 2)))
            o, h, lo, c = (
                Decimal(str(v)).quantize(step, ROUND_HALF_UP) for v in (open_, high, low, close)
            )
            volume = Decimal(str(round(rng.uniform(100, 1000), 8)))
            candles.append(Candle(market, day, o, max(h, o, c), min(lo, o, c), c, volume))
            price = close
        day += ONE_DAY
    return candles
