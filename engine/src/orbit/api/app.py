from collections.abc import Callable
from datetime import datetime
from decimal import Decimal

from fastapi import FastAPI
from pydantic import BaseModel

from orbit.marketdata.aggregate import Interval, aggregate
from orbit.marketdata.store import CandleStore
from orbit.marketdata.upbit_ticker import Ticker
from orbit.signals.today import Stance, today_signals


class CandleOut(BaseModel):
    start: datetime  # 봉 시작 시각, UTC
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


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


def _no_ticker(market: str) -> Ticker | None:
    return None


def create_app(
    open_store: Callable[[], CandleStore],
    get_ticker: Callable[[str], Ticker | None] = _no_ticker,
) -> FastAPI:
    app = FastAPI(title="orbit", docs_url=None, redoc_url=None)

    @app.get("/candles")
    def candles(market: str = "KRW-BTC", interval: Interval = Interval.DAY) -> list[CandleOut]:
        # sqlite 연결은 만든 스레드에서만 쓸 수 있음 — 의존성으로 열면 FastAPI 가
        # 의존성과 핸들러를 다른 작업 스레드에서 돌릴 수 있어 동시 요청 시 깨짐
        store = open_store()
        try:
            loaded = store.load(market)
        finally:
            store.close()
        return [
            CandleOut(
                start=c.start,
                open=c.open,
                high=c.high,
                low=c.low,
                close=c.close,
                volume=c.volume,
            )
            for c in aggregate(loaded, interval)
        ]

    @app.get("/signals")
    def signals(market: str = "KRW-BTC") -> SignalsOut:
        store = open_store()
        try:
            loaded = store.load(market)
        finally:
            store.close()
        ticker = get_ticker(market)
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
                for s in today_signals(loaded, ticker)
            ],
        )

    return app
