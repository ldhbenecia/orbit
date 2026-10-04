from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal

from orbit.marketdata.candle import Candle
from orbit.marketdata.instruments import NEW_YORK

# 뉴욕 정규장 마감 — 조기 폐장일(13시)도 이보다 이르므로 "끝났나" 판단이 늦는 쪽으로 보수적
US_REGULAR_CLOSE = time(16, 0)


def us_close_at(trading_day: date) -> datetime:
    return datetime.combine(trading_day, US_REGULAR_CLOSE, NEW_YORK)


@dataclass(frozen=True, slots=True)
class UsCloses:
    reference: Candle  # 한국 종가에 이미 반영된 미국 정규장
    latest: Candle  # 지금까지 끝난 가장 최근 미국 정규장


def us_closes_around(
    candles: Sequence[Candle], kr_close_at: datetime, now: datetime
) -> UsCloses | None:
    # 미국 일봉은 거래일 날짜 키 — 장이 끝난 봉만 씀. 진행 중인 봉 종가는 아직 정해지지 않음
    closed = [c for c in candles if us_close_at(c.start.date()) <= now]
    before = [c for c in closed if us_close_at(c.start.date()) <= kr_close_at]
    if not before:
        return None
    return UsCloses(reference=before[-1], latest=closed[-1])


@dataclass(frozen=True, slots=True)
class Leg:
    symbol: str
    name: str
    weight: Decimal  # 순자산 대비 비중 — 합이 1 이 아니어도 비율로 맞춤
    reference: Decimal  # 한국 종가에 반영된 미국 종가 (달러)
    latest: Decimal

    @property
    def change(self) -> Decimal:
        return self.latest / self.reference - 1


@dataclass(frozen=True, slots=True)
class NextOpen:
    kr_close: Decimal
    estimate: Decimal
    basket_change: Decimal  # 달러 자산의 가중 등락
    fx_change: Decimal  # 한국 종가 시점 대비 원/달러 변동
    change: Decimal  # 추정가 ÷ 한국 종가 − 1


def estimate_next_open(
    kr_close: Decimal,
    legs: Sequence[Leg],
    cash_weight: Decimal,
    fx_reference: Decimal,
    fx_latest: Decimal,
) -> NextOpen:
    # 환노출 ETF — 달러 자산은 미국 등락 × 환율 변동, 원화 현금은 그대로
    usd_weight = sum((leg.weight for leg in legs), Decimal(0))
    grown = sum((leg.weight * leg.latest / leg.reference for leg in legs), Decimal(0))
    fx_ratio = fx_latest / fx_reference
    factor = (grown * fx_ratio + cash_weight) / (usd_weight + cash_weight)
    estimate = kr_close * factor
    return NextOpen(
        kr_close=kr_close,
        estimate=estimate,
        basket_change=grown / usd_weight - 1,
        fx_change=fx_ratio - 1,
        change=factor - 1,
    )
