from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from orbit.fundamentals.snapshot import Snapshot
from orbit.marketdata.candle import Candle

HISTORY_YEARS = 5
MIN_HISTORY_MONTHS = 36  # 이보다 짧으면 "지난 몇 년 중 어디쯤" 이 의미가 약해 보이지 않음


@dataclass(frozen=True, slots=True)
class Valuation:
    per: Decimal | None  # 시가총액 ÷ 최근 4분기 순이익 — 적자면 없음
    pbr: Decimal | None  # 시가총액 ÷ 자본총계 — 자본이 0 이하면 없음
    roe: Decimal | None  # 최근 4분기 순이익 ÷ 자본총계
    fcf_yield: Decimal | None  # (영업현금흐름 − 설비투자) ÷ 시가총액
    revenue_growth: Decimal | None  # 최근 4분기 매출 ÷ 1년 전 최근 4분기 매출 − 1


@dataclass(frozen=True, slots=True)
class Position:
    low: Decimal
    high: Decimal
    percentile: Decimal  # 과거 값 중 지금 이하인 비율 0~1 — 낮을수록 과거보다 싸게 매겨짐
    months: int  # 비교한 월말 개수


@dataclass(frozen=True, slots=True)
class Fundamentals:
    as_of: date  # 가격 기준일
    period_end: date  # 재무 기준 (보고서의 분기·연도 끝)
    filed: date
    now: Valuation
    per_5y: Position | None
    pbr_5y: Position | None


def _ratio(top: Decimal | int | None, bottom: Decimal | int | None) -> Decimal | None:
    # 분모가 0 이하면 비율이 뜻이 없음 — 적자 PER, 자본 잠식 PBR·ROE
    if top is None or bottom is None or bottom <= 0:
        return None
    return Decimal(top) / Decimal(bottom)


def valuation(snap: Snapshot, price: Decimal) -> Valuation:
    cap = price * snap.shares if snap.shares is not None else None
    fcf = (
        snap.operating_cf - snap.capex
        if snap.operating_cf is not None and snap.capex is not None
        else None
    )
    growth = _ratio(snap.revenue, snap.revenue_prev)
    return Valuation(
        per=_ratio(cap, snap.net_income),
        pbr=_ratio(cap, snap.equity),
        roe=_ratio(snap.net_income, snap.equity),
        fcf_yield=_ratio(fcf, cap),
        revenue_growth=growth - 1 if growth is not None else None,
    )


def _known(snapshots: list[Snapshot], day: date) -> Snapshot | None:
    # 공시 당일 장중에 나온 보고서일 수 있어 다음 날 종가부터 반영
    return max((s for s in snapshots if s.filed < day), key=lambda s: s.filed, default=None)


def _month_ends(candles: list[Candle], since: date) -> list[Candle]:
    last: dict[tuple[int, int], Candle] = {}
    for c in candles:
        day = c.start.date()
        if day >= since:
            last[(day.year, day.month)] = c
    return list(last.values())


def _position(history: list[Decimal], current: Decimal | None) -> Position | None:
    if current is None or len(history) < MIN_HISTORY_MONTHS:
        return None
    below = sum(1 for v in history if v <= current)
    return Position(
        low=min(history),
        high=max(history),
        percentile=Decimal(below) / len(history),
        months=len(history),
    )


def fundamentals(snapshots: list[Snapshot], candles: list[Candle]) -> Fundamentals | None:
    if not candles:
        return None
    last = candles[-1]
    today = last.start.date()
    latest = _known(snapshots, today)
    if latest is None:
        return None
    now = valuation(latest, last.close)
    since = today.replace(year=today.year - HISTORY_YEARS)
    pers: list[Decimal] = []
    pbrs: list[Decimal] = []
    # 지금 달은 빼고 과거 월말끼리 — 지금 값이 비교 대상에 섞이지 않게
    for c in _month_ends(candles, since):
        if (c.start.year, c.start.month) == (today.year, today.month):
            continue
        snap = _known(snapshots, c.start.date())
        if snap is None:
            continue
        past = valuation(snap, c.close)
        if past.per is not None:
            pers.append(past.per)
        if past.pbr is not None:
            pbrs.append(past.pbr)
    return Fundamentals(
        as_of=today,
        period_end=latest.period_end,
        filed=latest.filed,
        now=now,
        per_5y=_position(pers, now.per),
        pbr_5y=_position(pbrs, now.pbr),
    )
