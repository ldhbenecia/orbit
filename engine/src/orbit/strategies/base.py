from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from orbit.marketdata.candle import Candle


@dataclass(frozen=True, slots=True)
class Decision:
    target_weight: Decimal  # 평가액 중 코인 비중 0~1 — 금액은 장부·백테스터가 정함
    reason: str  # 대시보드에 그대로 보여줄 판단 근거


# 확정된 봉만 받음 — 마지막 원소가 판단 시점의 가장 최근 확정 봉
Strategy = Callable[[Sequence[Candle]], Decision]
