from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from orbit.marketdata.candle import Candle


@dataclass(frozen=True, slots=True)
class Entry:
    # 장중 진입 — 가격이 시가 + breakout 에 닿으면 weight 까지 매수
    # 기준을 시가로부터의 거리로 둠: 시가는 장이 열릴 때 알 수 있지만 판단 재료(확정 봉)에는 없음
    breakout: Decimal
    weight: Decimal
    reason: str


@dataclass(frozen=True, slots=True)
class Decision:
    target_weight: Decimal  # 시가에 맞출 코인 비중 0~1 — 금액은 장부·백테스터가 정함
    reason: str  # 대시보드에 그대로 보여줄 판단 근거
    entry: Entry | None = None


# 확정된 봉만 받음 — 마지막 원소가 판단 시점의 가장 최근 확정 봉
Strategy = Callable[[Sequence[Candle]], Decision]
