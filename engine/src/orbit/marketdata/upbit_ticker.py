import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx

from orbit.marketdata.upbit_candles import BASE_URL

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Ticker:
    day: datetime  # 진행 중인 일봉의 시작 (UTC 0시)
    open: Decimal  # 오늘 시가
    high: Decimal  # 지금까지의 오늘 고가
    price: Decimal  # 현재가


def parse_ticker(payload: str) -> Ticker:
    row: dict[str, Any] = json.loads(payload, parse_float=Decimal)[0]
    return Ticker(
        day=datetime.strptime(row["trade_date"], "%Y%m%d").replace(tzinfo=UTC),
        open=Decimal(row["opening_price"]),
        high=Decimal(row["high_price"]),
        price=Decimal(row["trade_price"]),
    )


def fetch_ticker(client: httpx.Client, market: str) -> Ticker:
    response = client.get("/v1/ticker", params={"markets": market})
    response.raise_for_status()
    return parse_ticker(response.text)


def try_fetch_ticker(market: str) -> Ticker | None:
    # 시세를 못 받아도 확정 봉 기반 신호는 보여줄 수 있음 — 돌파 여부만 빠짐
    try:
        with httpx.Client(base_url=BASE_URL, timeout=5) as client:
            return fetch_ticker(client, market)
    except httpx.HTTPError as error:
        log.warning("업비트 시세 조회 실패: %s", type(error).__name__)
        return None
