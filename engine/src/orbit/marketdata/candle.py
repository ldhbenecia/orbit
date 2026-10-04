from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

ONE_DAY = timedelta(days=1)


@dataclass(frozen=True, slots=True)
class Candle:
    market: str
    start: datetime  # 봉 시작 시각, UTC
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal  # 거래량 (코인 수량)
    value: Decimal  # 거래대금 (원화)

    def is_closed(self, now: datetime) -> bool:
        # 진행 중인 봉은 종가가 계속 바뀜 — 저장·판단에 쓰면 미래 데이터 참조와 같음
        return self.start + ONE_DAY <= now


def find_missing_days(starts: list[datetime]) -> list[datetime]:
    ordered = sorted(starts)
    missing: list[datetime] = []
    for prev, cur in zip(ordered, ordered[1:], strict=False):
        day = prev + ONE_DAY
        while day < cur:
            missing.append(day)
            day += ONE_DAY
    return missing
