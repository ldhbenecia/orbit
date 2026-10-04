import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx

from orbit.marketdata.candle import Candle

BASE_URL = "https://api.upbit.com"
PAGE_SIZE = 200  # 업비트 캔들 API 한 번에 최대 200개
REQUEST_INTERVAL_SEC = 0.15  # 시세 API 의 IP 당 초당 요청 제한보다 여유 있게


def parse_candles(payload: str) -> list[Candle]:
    # float 를 거치면 가격에 이진 오차가 섞임 — 처음부터 Decimal 로 파싱
    rows: list[dict[str, Any]] = json.loads(payload, parse_float=Decimal)
    return [_to_candle(row) for row in rows]


def _to_candle(row: dict[str, Any]) -> Candle:
    return Candle(
        market=row["market"],
        start=datetime.fromisoformat(row["candle_date_time_utc"]).replace(tzinfo=UTC),
        open=Decimal(row["opening_price"]),
        high=Decimal(row["high_price"]),
        low=Decimal(row["low_price"]),
        close=Decimal(row["trade_price"]),
        volume=Decimal(row["candle_acc_trade_volume"]),
        value=Decimal(row["candle_acc_trade_price"]),
    )


def fetch_daily_candles(
    client: httpx.Client,
    market: str,
    since: datetime,
    sleep: Callable[[float], None] = time.sleep,
) -> list[Candle]:
    collected: list[Candle] = []
    to: datetime | None = None
    while True:
        params: dict[str, str | int] = {"market": market, "count": PAGE_SIZE}
        if to is not None:
            # to 시각 이전(미포함) 봉을 최신순으로 돌려줌
            params["to"] = to.strftime("%Y-%m-%dT%H:%M:%SZ")
        response = client.get("/v1/candles/days", params=params)
        response.raise_for_status()
        page = parse_candles(response.text)
        if not page:
            break
        collected.extend(c for c in page if c.start >= since)
        oldest = min(c.start for c in page)
        if oldest <= since or len(page) < PAGE_SIZE:
            break
        to = oldest
        sleep(REQUEST_INTERVAL_SEC)
    return sorted(collected, key=lambda c: c.start)
