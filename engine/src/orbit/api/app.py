import logging
import sqlite3
from collections.abc import Callable
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal

import httpx
from fastapi import FastAPI, Query
from pydantic import BaseModel

from orbit.backtest.runs import latest_runs, load_trades
from orbit.dca.plan import next_payday, run_dca
from orbit.estimate.live import NEXT_OPEN_BASKETS, NextOpenView
from orbit.indicators.moving_average import sma
from orbit.marketdata.aggregate import Interval, aggregate
from orbit.marketdata.candle import Candle
from orbit.marketdata.instruments import SEOUL
from orbit.marketdata.store import CandleStore
from orbit.marketdata.upbit_ticker import Ticker
from orbit.signals.today import Stance, is_upbit_market, today_signals


class CandleOut(BaseModel):
    start: datetime  # 봉 시작 시각, UTC
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


class CandlesSummaryOut(BaseModel):
    first: datetime  # 첫 일봉, UTC
    last: datetime
    count: int  # 일봉 개수


class SignalOut(BaseModel):
    strategy: str
    status: str
    stance: Stance
    reason: str
    days: int | None
    trigger: Decimal | None
    close: Decimal  # 판단에 쓴 마지막 확정 봉 종가
    reference: Decimal | None  # 판단 기준 가격 (이동평균 등)


class SignalsOut(BaseModel):
    as_of: datetime  # 판단에 쓴 마지막 확정 봉, UTC
    price: Decimal | None  # 현재가 — 시세를 못 받으면 없음
    signals: list[SignalOut]


class RunOut(BaseModel):
    id: int
    strategy: str
    created_at: datetime
    code_version: str
    start: datetime
    end: datetime
    cagr: Decimal
    mdd: Decimal
    trades: int


class TradeOut(BaseModel):
    # 차트 매수·매도 표시용 — 백테스트 매매와 이후 장부 체결이 같은 모양
    day: datetime  # 체결일 봉 시작, UTC
    side: Literal["buy", "sell"]
    qty: Decimal
    price: Decimal
    reason: str


class PricePositionOut(BaseModel):
    window: int  # 거래일
    average: Decimal
    gap: Decimal  # 종가 ÷ 평균 − 1


class DcaOut(BaseModel):
    as_of: datetime  # 마지막 확정 봉
    close: Decimal
    next_payday: date
    days_until: int  # 한국 날짜 기준 다음 적립일까지 남은 날
    holidays_checked: bool  # 장 캘린더로 공휴일까지 확인했는지 — 아니면 주말만 피함
    positions: list[PricePositionOut]
    monthly: Decimal  # 백테스트 예시 금액 (개인 금액 아님)
    first_buy: datetime | None
    months: int
    invested: Decimal
    final_value: Decimal
    return_on_invested: Decimal
    worst_vs_invested: Decimal
    average_cost: Decimal | None  # 산 금액 ÷ 산 수량


class NextOpenLegOut(BaseModel):
    symbol: str
    name: str
    weight: Decimal  # 순자산 대비 비중 0~1
    change: Decimal  # 한국 종가 이후 미국 등락 (달러 기준)


class NextOpenOut(BaseModel):
    state: Literal["ready", "kr_open"]  # 한국장 중에는 종가가 없어 계산하지 않음
    next_open_day: date
    kr_close_day: date | None
    kr_close: Decimal | None
    estimate: Decimal | None  # 다음 개장 추정가 — 원 미만 포함 계산값
    change: Decimal | None  # 추정가 ÷ 한국 종가 − 1
    basket_change: Decimal | None  # 달러 자산 가중 등락
    fx_change: Decimal | None  # 한국 종가 시점 대비 원/달러
    fx_reference: Decimal | None
    fx_latest: Decimal | None
    us_reference_day: date | None  # 한국 종가에 반영된 미국 거래일
    us_latest_day: date | None  # 지금까지 끝난 최근 미국 거래일
    us_pending: bool  # 다음 개장 전에 끝날 미국장이 남음
    coverage: Decimal  # 시세를 반영한 비중 (현금 포함)
    basis: Literal["proxy", "holdings"]  # 같은 지수 미국 ETF 로 근사 / 구성 종목으로 계산
    legs: list[NextOpenLegOut]


log = logging.getLogger(__name__)

DCA_EXAMPLE_MONTHLY = Decimal(1_000_000)
POSITION_WINDOWS = (60, 120)


def _weekday_only(day: date) -> date:
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def _no_ticker(market: str) -> Ticker | None:
    return None


def create_app(
    connect: Callable[[], sqlite3.Connection],
    get_ticker: Callable[[str], Ticker | None] = _no_ticker,
    kr_trading_day_for: Callable[[date], date] | None = None,
    today: Callable[[], date] = lambda: datetime.now(SEOUL).date(),
    next_open: Callable[[str], NextOpenView] | None = None,
) -> FastAPI:
    app = FastAPI(title="orbit", docs_url=None, redoc_url=None)

    # 전 기간 일봉을 Decimal 로 바꾸는 게 요청 비용 대부분 — DB 가 그대로면 읽어 둔 걸 씀
    cache: dict[str, tuple[tuple[int, int | None], list[Candle]]] = {}

    def load_candles(market: str) -> list[Candle]:
        # sqlite 연결은 만든 스레드에서만 쓸 수 있음 — 의존성으로 열면 FastAPI 가
        # 의존성과 핸들러를 다른 작업 스레드에서 돌릴 수 있어 동시 요청 시 깨짐
        conn = connect()
        try:
            store = CandleStore(conn)
            version = store.version(market)
            cached = cache.get(market)
            if cached is None or cached[0] != version:
                cached = (version, store.load(market))
                cache[market] = cached
            return list(cached[1])
        finally:
            conn.close()

    @app.get("/candles")
    def candles(
        market: str = "KRW-BTC",
        interval: Interval = Interval.DAY,
        limit: int | None = Query(None, ge=1),  # 최근 N 개만 — 첫 화면은 일부만 보냄
    ) -> list[CandleOut]:
        bars = aggregate(load_candles(market), interval)
        if limit is not None:
            bars = bars[-limit:]
        return [
            CandleOut(
                start=c.start,
                open=c.open,
                high=c.high,
                low=c.low,
                close=c.close,
                volume=c.volume,
            )
            for c in bars
        ]

    @app.get("/candles/summary")
    def candles_summary(market: str = "KRW-BTC") -> CandlesSummaryOut | None:
        loaded = load_candles(market)
        if not loaded:
            return None
        return CandlesSummaryOut(first=loaded[0].start, last=loaded[-1].start, count=len(loaded))

    @app.get("/signals")
    def signals(market: str = "KRW-BTC") -> SignalsOut:
        loaded = load_candles(market)
        # 오늘 시가·현재가는 업비트 코인만 — 주식은 확정 일봉 기반 신호만
        ticker = get_ticker(market) if is_upbit_market(market) else None
        return SignalsOut(
            as_of=loaded[-1].start,
            price=ticker.price if ticker else None,
            signals=[
                SignalOut(
                    strategy=s.strategy,
                    status=s.status,
                    stance=s.stance,
                    reason=s.reason,
                    days=s.days,
                    trigger=s.trigger,
                    close=s.close,
                    reference=s.reference,
                )
                for s in today_signals(market, loaded, ticker)
            ],
        )

    @app.get("/dca")
    def dca(market: str) -> DcaOut | None:
        # 코어 ETF 적립식 분석 — 매달 25일(휴일이면 직전 영업일)에 산다고 봄
        loaded = load_candles(market)
        if not loaded:
            return None
        result = run_dca(loaded, DCA_EXAMPLE_MONTHLY)
        last = loaded[-1]
        closes = [c.close for c in loaded]
        positions = []
        for window in POSITION_WINDOWS:
            average = sma(closes[-window:], window)
            if average is not None:
                positions.append(
                    PricePositionOut(window=window, average=average, gap=last.close / average - 1)
                )
        now = today()
        payday, checked = next_payday(now, _weekday_only), False
        if kr_trading_day_for is not None:
            try:
                payday, checked = next_payday(now, kr_trading_day_for), True
            except httpx.HTTPError as error:
                # 허용 IP 가 바뀌는 등으로 장 캘린더를 못 받으면 주말만 피하고 미확인으로 표시
                log.warning("장 캘린더 조회 실패: %s", type(error).__name__)
        return DcaOut(
            as_of=last.start,
            close=last.close,
            next_payday=payday,
            days_until=(payday - now).days,
            holidays_checked=checked,
            positions=positions,
            monthly=DCA_EXAMPLE_MONTHLY,
            first_buy=result.buys[0].day if result.buys else None,
            months=int(result.invested / DCA_EXAMPLE_MONTHLY),  # 적립한 달 수 (못 산 달 포함)
            invested=result.invested,
            final_value=result.final_value,
            return_on_invested=result.final_value / result.invested - 1
            if result.invested
            else Decimal(0),
            worst_vs_invested=result.worst_vs_invested,
            average_cost=result.spent / result.qty if result.qty else None,
        )

    @app.get("/next-open")
    def next_open_estimate(market: str) -> NextOpenOut | None:
        # 국내 상장 미국 ETF — 한국 종가 뒤 미국장·환율 변동으로 다음 개장가를 추정
        if next_open is None or market not in NEXT_OPEN_BASKETS:
            return None
        try:
            view = next_open(market)
        except httpx.HTTPError as error:
            # 허용 IP 가 바뀌었거나 운용사 화면이 바뀌면 실패 — 화면은 "계산 못 함"으로
            log.warning("다음 개장 추정 실패 %s: %s", market, type(error).__name__)
            return None
        r = view.result
        return NextOpenOut(
            state=view.state,
            next_open_day=view.next_open_day,
            kr_close_day=view.kr_close_day,
            kr_close=r.kr_close if r else None,
            estimate=r.estimate if r else None,
            change=r.change if r else None,
            basket_change=r.basket_change if r else None,
            fx_change=r.fx_change if r else None,
            fx_reference=view.fx_reference,
            fx_latest=view.fx_latest,
            us_reference_day=view.us_reference_day,
            us_latest_day=view.us_latest_day,
            us_pending=view.us_pending,
            coverage=view.coverage,
            basis=view.basis,
            legs=[
                NextOpenLegOut(
                    symbol=leg.symbol, name=leg.name, weight=leg.weight, change=leg.change
                )
                for leg in view.legs
            ],
        )

    @app.get("/backtests")
    def backtests(market: str = "KRW-BTC") -> list[RunOut]:
        conn = connect()
        try:
            runs = latest_runs(conn, market)
        finally:
            conn.close()
        return [
            RunOut(
                id=r.id,
                strategy=r.strategy,
                created_at=r.created_at,
                code_version=r.code_version,
                start=r.start,
                end=r.end,
                cagr=r.cagr,
                mdd=r.mdd,
                trades=r.trades,
            )
            for r in runs
        ]

    @app.get("/backtests/{run_id}/trades")
    def backtest_trades(run_id: int) -> list[TradeOut]:
        conn = connect()
        try:
            trades = load_trades(conn, run_id)
        finally:
            conn.close()
        return [
            TradeOut(day=t.day, side=t.side, qty=t.qty, price=t.price, reason=t.reason)
            for t in trades
        ]

    return app
