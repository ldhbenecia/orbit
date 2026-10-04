from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_DOWN, Decimal

from orbit.marketdata.candle import Candle

PAYDAY = 25  # 월급날 — 휴일이면 그 전 영업일에 들어와 그날 삼


@dataclass(frozen=True, slots=True)
class DcaBuy:
    day: datetime
    price: Decimal  # 그날 종가에 산 것으로 봄
    qty: int  # 국내 ETF 는 1주 단위
    cost: Decimal


@dataclass(slots=True)
class DcaResult:
    buys: list[DcaBuy] = field(default_factory=list)
    invested: Decimal = Decimal(0)  # 넣은 돈 합계
    spent: Decimal = Decimal(0)  # 실제 산 금액 (남은 돈은 다음 달로)
    qty: int = 0
    cash: Decimal = Decimal(0)
    final_value: Decimal = Decimal(0)  # 마지막 종가 기준 평가액 + 남은 현금
    worst_vs_invested: Decimal = Decimal(0)  # 넣은 돈 대비 가장 나빴던 순간


def payday_indices(candles: Sequence[Candle], payday: int = PAYDAY) -> list[int]:
    # 달마다 payday 일 이하 마지막 거래일 — 일봉이 있는 날이 거래일
    by_month: dict[tuple[int, int], int] = {}
    for i, c in enumerate(candles):
        if c.start.day <= payday:
            by_month[(c.start.year, c.start.month)] = i
    # 진행 중인 달은 뒤에 일봉이 더 생겨야 적립일이 확정됨 — 그전엔 아직 오지 않은 적립일
    last = len(candles) - 1
    return sorted(i for i in by_month.values() if i < last or candles[i].start.day == payday)


def run_dca(
    candles: Sequence[Candle], monthly: Decimal, fee_rate: Decimal = Decimal(0)
) -> DcaResult:
    result = DcaResult()
    paydays = set(payday_indices(candles))
    for i, c in enumerate(candles):
        if i in paydays:
            result.cash += monthly
            result.invested += monthly
            qty = int((result.cash / (c.close * (1 + fee_rate))).to_integral_value(ROUND_DOWN))
            if qty > 0:
                cost = c.close * qty
                fee = (cost * fee_rate).to_integral_value(ROUND_DOWN)  # 1원 미만 절사
                result.cash -= cost + fee
                result.spent += cost + fee
                result.qty += qty
                result.buys.append(DcaBuy(c.start, c.close, qty, cost + fee))
        if result.invested:
            value = result.cash + c.close * result.qty
            result.worst_vs_invested = min(result.worst_vs_invested, value / result.invested - 1)
    if candles:
        result.final_value = result.cash + candles[-1].close * result.qty
    return result


def next_payday(today: date, trading_day_for: Callable[[date], date]) -> date:
    # trading_day_for(d): d 가 휴장이면 그 전 영업일, 열리면 d — 장 캘린더로 판단
    this_month = trading_day_for(today.replace(day=PAYDAY))
    if this_month >= today:
        return this_month
    year, month = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
    return trading_day_for(date(year, month, PAYDAY))
