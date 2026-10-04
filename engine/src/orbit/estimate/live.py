import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Literal, Protocol
from zoneinfo import ZoneInfo

import httpx

from orbit.estimate.next_open import Leg, NextOpen, estimate_next_open, us_closes_around
from orbit.marketdata.candle import Candle
from orbit.marketdata.fund_nav import Nav
from orbit.marketdata.instruments import NEW_YORK, SEOUL, find_instrument
from orbit.marketdata.tiger_holdings import Holding

log = logging.getLogger(__name__)

KR_REGULAR_CLOSE = time(15, 30)  # 장 캘린더에 그날 정보가 없을 때만 씀
LOOKBACK = timedelta(days=14)  # 연휴가 길어도 직전 종가가 들어올 만큼


@dataclass(frozen=True, slots=True)
class Basket:
    # 같은 지수를 따르는 미국 ETF 하나로 근사하거나, 운용사가 공개한 구성 종목으로 계산
    proxy: str | None = None
    holdings_fund: str | None = None  # TIGER 운용사 펀드 코드 (ksdFund) — 구성 종목 출처
    nav_source: tuple[Literal["tiger", "ace"], str] | None = None  # 기준가 공시 운용사·펀드 코드


# 이름에 (H) 가 없는 환노출 ETF 만 — 환헤지 ETF 는 환율을 곱하면 틀림
# 펀드 코드는 운용사 사이트에서 토스 종목 정보의 ISIN 으로 찾은 값
NEXT_OPEN_BASKETS = {
    # 나스닥100 추종 — QQQ 로 근사
    "KRX-367380": Basket(proxy="QQQ", nav_source=("ace", "K55101DB1182")),
    # S&P500 추종 — SPY 로 근사
    "KRX-360750": Basket(proxy="SPY", nav_source=("tiger", "KR7360750004")),
    # 미국 우주 종목 10개 — 구성 종목으로
    "KRX-0183J0": Basket(holdings_fund="KR70183J0002", nav_source=("tiger", "KR70183J0002")),
}


# 운용사 구성 종목 표가 옛 심볼을 쓰는 경우 — 토스 종목 정보(ISIN)로 같은 회사임을 확인한 것만
SYMBOL_ALIASES = {
    "SATS": "ECHO",  # EchoStar, 2026-06 심볼 변경 (ISIN US2787681061)
}


class MarketSource(Protocol):
    def get(self, path: str, params: dict[str, str | int]) -> dict[str, Any]: ...

    def daily_candles(
        self, symbol: str, market: str, exchange_tz: ZoneInfo, since: date
    ) -> list[Candle]: ...


@dataclass(frozen=True, slots=True)
class PricedLeg:
    symbol: str
    name: str
    weight: Decimal
    change: Decimal


@dataclass(frozen=True, slots=True)
class NextOpenView:
    state: Literal["ready", "kr_open"]  # 한국장 중에는 종가가 아직 없어 계산하지 않음
    next_open_day: date
    kr_close_day: date | None = None
    result: NextOpen | None = None
    fx_reference: Decimal | None = None
    fx_latest: Decimal | None = None
    us_reference_day: date | None = None
    us_latest_day: date | None = None
    us_pending: bool = False  # 다음 개장 전에 끝날 미국장이 아직 남음 — 값이 더 바뀜
    coverage: Decimal = Decimal(1)  # 시세를 반영한 비중 (현금 포함)
    legs: tuple[PricedLeg, ...] = ()
    basis: Literal["proxy", "holdings"] = "proxy"
    nav_day: date | None = None  # 운용사가 올린 최신 기준가의 날짜
    nav: Decimal | None = None
    # 한국 종가와 같은 날 기준가에서 출발한 추정 — 종가의 괴리(프리미엄)가 사라진다고 보는 쪽
    nav_estimate: Decimal | None = None


def _at(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _regular(entry: dict[str, Any] | None) -> tuple[datetime, datetime] | None:
    session = ((entry or {}).get("integrated") or {}).get("regularMarket")
    if not session:
        return None
    return _at(session["startTime"]), _at(session["endTime"])


def _us_regular_end(entry: dict[str, Any] | None) -> datetime | None:
    session = (entry or {}).get("regularMarket")
    return _at(session["endTime"]) if session else None


def build_view(
    market: str,
    source: MarketSource,
    holdings_for: Callable[[str], list[Holding]],
    now: datetime,
    nav_for: Callable[[str, str], Nav | None] = lambda kind, fund: None,
) -> NextOpenView:
    basket = NEXT_OPEN_BASKETS[market]
    instrument = find_instrument(market)
    calendar = source.get("/api/v1/market-calendar/KR", {})["result"]
    today = _regular(calendar["today"])
    if today is not None and today[0] <= now < today[1]:
        return NextOpenView(state="kr_open", next_open_day=now.astimezone(SEOUL).date())
    if today is not None and now < today[0]:
        next_open = now.astimezone(SEOUL).date()
        next_open_at = today[0]
    else:
        nxt = calendar["nextBusinessDay"]
        next_open = date.fromisoformat(nxt["date"])
        session = _regular(nxt)
        # 캘린더에 시간이 없으면 정규장 개장 9시로 봄
        next_open_at = session[0] if session else datetime.combine(next_open, time(9), SEOUL)

    # 한국 종가 — 오늘 장이 끝났으면 오늘 봉, 아니면 그 전 봉
    kr_today = now.astimezone(SEOUL).date()
    kr_candles = [
        c
        for c in source.daily_candles(instrument.symbol, market, SEOUL, kr_today - LOOKBACK)
        if c.start.date() < kr_today or (today is not None and now >= today[1])
    ]
    kr_last = kr_candles[-1]
    kr_day = kr_last.start.date()
    ends = {
        date.fromisoformat(e["date"]): r[1]
        for e in (calendar["today"], calendar["previousBusinessDay"])
        if (r := _regular(e)) is not None
    }
    kr_close_at = ends.get(kr_day, datetime.combine(kr_day, KR_REGULAR_CLOSE, SEOUL))

    if basket.proxy is not None:
        targets = [(basket.proxy, basket.proxy, Decimal(1))]
        cash = Decimal(0)
        unpriced = Decimal(0)
    else:
        assert basket.holdings_fund is not None
        holdings = holdings_for(basket.holdings_fund)
        targets = [
            (SYMBOL_ALIASES.get(h.symbol, h.symbol), h.name, h.weight)
            for h in holdings
            if h.symbol is not None
        ]
        cash = sum((h.weight for h in holdings if h.is_cash), Decimal(0))
        unpriced = sum(
            (h.weight for h in holdings if h.symbol is None and not h.is_cash), Decimal(0)
        )

    total_weight = sum((w for _, _, w in targets), Decimal(0)) + cash + unpriced
    legs: list[Leg] = []
    reference_days: set[date] = set()
    latest_days: set[date] = set()
    for symbol, name, weight in targets:
        try:
            candles = source.daily_candles(symbol, f"US-{symbol}", NEW_YORK, kr_day - LOOKBACK)
        except httpx.HTTPStatusError as error:
            # 토스에 없는 종목(404) — 그 비중만 빼고 반영 비중으로 알림. 그 밖의 오류는 전체 실패
            if error.response.status_code != 404:
                raise
            candles = []
        closes = us_closes_around(candles, kr_close_at, now)
        if closes is None:
            log.warning("미국 종가를 못 찾아 추정에서 뺌: %s", symbol)
            unpriced += weight
            continue
        legs.append(Leg(symbol, name, weight, closes.reference.close, closes.latest.close))
        reference_days.add(closes.reference.start.date())
        latest_days.add(closes.latest.start.date())

    fx_reference = _mid_rate(source, kr_close_at)
    fx_latest = _mid_rate(source, None)
    result = estimate_next_open(kr_last.close, legs, cash, fx_reference, fx_latest)

    us_calendar = source.get("/api/v1/market-calendar/US", {})["result"]
    us_ends = [_us_regular_end(us_calendar.get(k)) for k in ("today", "nextBusinessDay")]
    us_pending = any(end is not None and now < end <= next_open_at for end in us_ends)

    nav = nav_for(*basket.nav_source) if basket.nav_source else None
    # 다른 날 기준가를 쓰면 반영된 미국장이 달라져 틀림 — 한국 종가와 같은 날 것만
    nav_estimate = nav[1] * (1 + result.change) if nav is not None and nav[0] == kr_day else None

    return NextOpenView(
        state="ready",
        next_open_day=next_open,
        kr_close_day=kr_day,
        result=result,
        fx_reference=fx_reference,
        fx_latest=fx_latest,
        us_reference_day=max(reference_days, default=None),
        us_latest_day=max(latest_days, default=None),
        us_pending=us_pending,
        coverage=1 - unpriced / total_weight,
        legs=tuple(PricedLeg(leg.symbol, leg.name, leg.weight, leg.change) for leg in legs),
        basis="proxy" if basket.proxy is not None else "holdings",
        nav_day=nav[0] if nav else None,
        nav=nav[1] if nav else None,
        nav_estimate=nav_estimate,
    )


def _mid_rate(source: MarketSource, at: datetime | None) -> Decimal:
    # 매매기준율 — 토스 매수 환율(rate)은 스프레드가 붙어 있어 순자산 계산과 다름
    params: dict[str, str | int] = {"baseCurrency": "USD", "quoteCurrency": "KRW"}
    if at is not None:
        params["dateTime"] = at.isoformat()
    return Decimal(source.get("/api/v1/exchange-rate", params)["result"]["midRate"])
