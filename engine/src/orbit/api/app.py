import sqlite3
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Literal

from fastapi import FastAPI, Query
from pydantic import BaseModel

from orbit.backtest.runs import latest_runs, load_trades
from orbit.marketdata.aggregate import Interval, aggregate
from orbit.marketdata.candle import Candle
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


def _no_ticker(market: str) -> Ticker | None:
    return None


def create_app(
    connect: Callable[[], sqlite3.Connection],
    get_ticker: Callable[[str], Ticker | None] = _no_ticker,
) -> FastAPI:
    app = FastAPI(title="orbit", docs_url=None, redoc_url=None)

    def load_candles(market: str) -> list[Candle]:
        # sqlite 연결은 만든 스레드에서만 쓸 수 있음 — 의존성으로 열면 FastAPI 가
        # 의존성과 핸들러를 다른 작업 스레드에서 돌릴 수 있어 동시 요청 시 깨짐
        conn = connect()
        try:
            return CandleStore(conn).load(market)
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
                )
                for s in today_signals(market, loaded, ticker)
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
