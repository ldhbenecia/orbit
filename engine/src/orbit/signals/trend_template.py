from collections.abc import Mapping, Sequence
from decimal import Decimal
from enum import StrEnum

from orbit.indicators.moving_average import sma
from orbit.marketdata.candle import Candle

# 마크 미너비니의 추세 템플릿 — 사라는 신호가 아니라 "이미 상승 추세에 있는가" 를 거르는 체
# 숫자는 정리본마다 조금 다름 (52주 저점 대비 25~30%) — 결과를 보고 고르지 않은 고정값
YEAR_BARS = 252  # 52주 거래일
RISING_BARS = 21  # 200일 평균이 오르는지 보는 기간 (약 1개월)
ABOVE_LOW = Decimal("1.3")  # 52주 최저 종가의 1.3배 이상
NEAR_HIGH = Decimal("0.75")  # 52주 최고 종가의 75% 이상 (고점에서 25% 이내)
RS_MIN = Decimal("0.7")  # 상대강도 — 비교 종목 중 상위 30% 안 (IBD 점수 70 에 해당)
RS_MIN_PEERS = 5  # 비교할 종목이 이보다 적으면 상대강도는 모름


class Check(StrEnum):
    ABOVE_150_200 = "above_150_200"  # 종가 > 150일·200일 평균
    MA150_OVER_200 = "ma150_over_200"  # 150일 평균 > 200일 평균
    MA200_RISING = "ma200_rising"  # 200일 평균이 1개월 전보다 높음
    MA50_OVER_LONG = "ma50_over_long"  # 50일 평균 > 150일·200일 평균
    ABOVE_50 = "above_50"  # 종가 > 50일 평균
    ABOVE_LOW = "above_low"  # 52주 저점보다 30% 이상 위
    NEAR_HIGH = "near_high"  # 52주 고점에서 25% 이내
    STRONG = "strong"  # 상대강도 상위 30%


def trend_template(
    candles: Sequence[Candle], strength: Decimal | None
) -> dict[Check, bool | None] | None:
    # 확정 봉만 받음. 1년이 안 되면 판단하지 않음. strength 를 모르면 그 조건만 None
    closes = [c.close for c in candles]
    if len(closes) < YEAR_BARS:
        return None
    close = closes[-1]
    ma50, ma150, ma200 = (sma(closes, n) for n in (50, 150, 200))
    ma200_before = sma(closes[:-RISING_BARS], 200)
    assert ma50 and ma150 and ma200 and ma200_before  # 1년치면 모두 계산됨
    year = closes[-YEAR_BARS:]
    return {
        Check.ABOVE_150_200: close > ma150 and close > ma200,
        Check.MA150_OVER_200: ma150 > ma200,
        Check.MA200_RISING: ma200 > ma200_before,
        Check.MA50_OVER_LONG: ma50 > ma150 and ma50 > ma200,
        Check.ABOVE_50: close > ma50,
        Check.ABOVE_LOW: close >= min(year) * ABOVE_LOW,
        Check.NEAR_HIGH: close >= max(year) * NEAR_HIGH,
        Check.STRONG: None if strength is None else strength >= RS_MIN,
    }


def strength_ranks(returns: Mapping[str, Decimal]) -> dict[str, Decimal]:
    # 1년 수익률이 나보다 낮은 종목 비율 0~1 — 비교 종목이 적으면 비움
    if len(returns) < RS_MIN_PEERS:
        return {}
    n = len(returns) - 1
    return {
        market: Decimal(sum(1 for other in returns.values() if other < mine)) / n
        for market, mine in returns.items()
    }
