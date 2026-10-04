from collections.abc import Callable
from datetime import datetime
from decimal import Decimal

from fastapi import FastAPI
from pydantic import BaseModel

from orbit.marketdata.store import CandleStore


class CandleOut(BaseModel):
    start: datetime  # 봉 시작 시각, UTC
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


def create_app(open_store: Callable[[], CandleStore]) -> FastAPI:
    app = FastAPI(title="orbit", docs_url=None, redoc_url=None)

    @app.get("/candles")
    def candles(market: str = "KRW-BTC") -> list[CandleOut]:
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
            for c in loaded
        ]

    return app
