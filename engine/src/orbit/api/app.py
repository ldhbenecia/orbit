from collections.abc import Callable, Iterator
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import Depends, FastAPI
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

    def store() -> Iterator[CandleStore]:
        # sqlite 연결은 스레드를 넘기면 안 됨 — 요청마다 열고 닫음
        s = open_store()
        try:
            yield s
        finally:
            s.close()

    @app.get("/candles")
    def candles(
        store: Annotated[CandleStore, Depends(store)], market: str = "KRW-BTC"
    ) -> list[CandleOut]:
        return [
            CandleOut(
                start=c.start,
                open=c.open,
                high=c.high,
                low=c.low,
                close=c.close,
                volume=c.volume,
            )
            for c in store.load(market)
        ]

    return app
