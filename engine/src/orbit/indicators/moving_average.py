from collections.abc import Sequence
from decimal import Decimal


def sma(values: Sequence[Decimal], window: int) -> Decimal | None:
    # 마지막 window 개만 씀 — 데이터가 모자라면 계산하지 않음
    if len(values) < window:
        return None
    return sum(values[-window:], Decimal(0)) / window
