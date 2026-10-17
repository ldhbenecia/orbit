import math
import random
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from orbit.fundamentals.snapshot import Snapshot
from orbit.marketdata.candle import ONE_DAY, Candle
from orbit.marketdata.instruments import COIN_MARKETS, Universe
from orbit.marketdata.names import InstrumentName

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


def demo_names(universe: Universe) -> list[InstrumentName]:
    # 가상 데이터 DB 의 이름 캐시 — 화면에 실제 종목 이름이 하나도 나가지 않게 예시 이름만
    names = [
        InstrumentName(market, market.split("-", 1)[1], f"예시 코인 {chr(65 + i)}", "DEMO", "KRW")
        for i, market in enumerate(COIN_MARKETS)
    ]
    dashboard = watch = 0
    for instrument in universe.instruments:
        if instrument.dashboard:
            dashboard += 1
            name = f"예시 종목 {dashboard}"
        else:
            watch += 1
            name = f"예시 관심 종목 {watch}"
        names.append(
            InstrumentName(instrument.market, instrument.symbol, name, "DEMO", instrument.currency)
        )
    return names


DEMO_SHARES = 1_000_000_000


def demo_snapshots(market: str, start: date, end: date) -> list[Snapshot]:
    # 가상 재무 — 분기마다 순이익이 무작위로 변하고, 분기 끝 40일 뒤 공시된다고 봄
    rng = random.Random(f"{market}:fundamentals")
    income = 4e9  # 가상 시세 100달러 × 10억 주 ÷ 이 값 ≈ PER 25
    out: list[Snapshot] = []
    quarter = start.year * 4
    while True:
        year, q = divmod(quarter, 4)
        period_end = date(year + (q == 3), (3 * (q + 1)) % 12 + 1, 1) - timedelta(1)
        filed = period_end + timedelta(40)
        if filed > end:
            return out
        income *= math.exp(rng.gauss(0.02, 0.08))
        ni = round(income)
        out.append(
            Snapshot(
                filed=filed,
                period_end=period_end,
                net_income=ni,
                revenue=ni * 5,
                revenue_prev=round(ni * 5 / 1.1),
                operating_cf=round(ni * 1.3),
                capex=round(ni * 0.3),
                equity=ni * 6,
                shares=DEMO_SHARES,
            )
        )
        quarter += 1
