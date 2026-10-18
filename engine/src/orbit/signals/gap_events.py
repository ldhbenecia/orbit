from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from orbit.marketdata.candle import Candle

# 크리스티안 쿨라매기의 "에피소드 피벗" 에서 가져온 사실
# 예상 밖 소식에 크게 갭 상승하고 거래량이 터진 날
# 숫자는 2차 정리본 기준 추정 (공개된 원 규칙이 없음) — 결과를 보고 고르지 않은 고정값
GAP_MIN = Decimal("0.1")  # 시가가 전날 종가보다 10% 이상
VOLUME_MULTIPLE = Decimal(3)  # 거래량이 직전 평균의 3배 이상
VOLUME_BARS = 50  # 평균 거래량을 보는 직전 거래일 수
PRIOR_BARS = 126  # 직전 약 6개월 — 이미 많이 오른 뒤인지 보는 사실
AFTER_BARS = 20  # 그 뒤 약 1개월 — 지나고 보니 어땠는지


@dataclass(frozen=True, slots=True)
class GapEvent:
    day: date  # 갭 상승한 날 (거래소 날짜)
    gap: Decimal  # 시가 ÷ 전날 종가 − 1
    volume_multiple: Decimal  # 그날 거래량 ÷ 직전 50일 평균
    day_return: Decimal  # 그날 종가 ÷ 전날 종가 − 1
    prior: Decimal | None  # 전날 종가 ÷ 약 6개월 전 종가 − 1 — 기록이 짧으면 없음
    after: Decimal | None  # 약 1개월 뒤 종가 ÷ 그날 종가 − 1 — 아직 안 지났으면 없음


def gap_ups(candles: Sequence[Candle]) -> list[GapEvent]:
    # 확정 봉만 받음. 오래된 순
    events = []
    for i in range(VOLUME_BARS, len(candles)):
        prev, bar = candles[i - 1], candles[i]
        gap = bar.open / prev.close - 1
        if gap < GAP_MIN:
            continue
        average = sum((c.volume for c in candles[i - VOLUME_BARS : i]), Decimal(0)) / VOLUME_BARS
        if average <= 0 or bar.volume < average * VOLUME_MULTIPLE:
            continue
        before = candles[i - 1 - PRIOR_BARS].close if i - 1 - PRIOR_BARS >= 0 else None
        later = candles[i + AFTER_BARS].close if i + AFTER_BARS < len(candles) else None
        events.append(
            GapEvent(
                day=bar.start.date(),
                gap=gap,
                volume_multiple=bar.volume / average,
                day_return=bar.close / prev.close - 1,
                prior=prev.close / before - 1 if before else None,
                after=later / bar.close - 1 if later else None,
            )
        )
    return events
