import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from pydantic import SecretStr

from orbit.marketdata.candle import Candle

BASE_URL = "https://openapi.tossinvest.com"
PAGE_SIZE = 200  # 토스 캔들 API 한 번에 최대 200개
TOKEN_MARGIN_SEC = 60  # 만료 직전 토큰으로 요청하다 끊기지 않게 여유

# 같은 키로 주문도 가능해서 조회 경로만 허용 — 주문·계좌 경로는 요청 전에 거부
ALLOWED_PATHS = frozenset(
    {
        "/api/v1/candles",
        "/api/v1/prices",
        "/api/v1/stocks",
        "/api/v1/exchange-rate",
        "/api/v1/market-calendar/KR",
        "/api/v1/market-calendar/US",
    }
)
ACCOUNT_HEADER = "X-Tossinvest-Account"


class ForbiddenPathError(Exception):
    pass


@dataclass(slots=True)
class _Token:
    value: str
    expires_at: float


class TossMarketData:
    def __init__(
        self,
        client: httpx.Client,
        client_id: SecretStr,
        client_secret: SecretStr,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._client_id = client_id
        self._client_secret = client_secret
        self._clock = clock
        self._token: _Token | None = None

    def get(self, path: str, params: dict[str, str | int]) -> dict[str, Any]:
        if path not in ALLOWED_PATHS:
            raise ForbiddenPathError(f"토스 조회 허용 경로가 아님: {path}")
        response = self._client.get(path, params=params, headers=self._auth())
        if response.status_code == 401:
            # 다른 곳에서 재발급해 무효가 된 토큰일 수 있음 — 한 번만 새로 받고 재시도
            self._token = None
            response = self._client.get(path, params=params, headers=self._auth())
        response.raise_for_status()
        body: dict[str, Any] = json.loads(response.text)
        return body

    def daily_candles(
        self, symbol: str, market: str, exchange_tz: ZoneInfo, since: date
    ) -> list[Candle]:
        collected: list[Candle] = []
        before: str | None = None
        while True:
            params: dict[str, str | int] = {"symbol": symbol, "interval": "1d", "count": PAGE_SIZE}
            if before is not None:
                params["before"] = before
            result = self.get("/api/v1/candles", params)["result"]
            page = [_to_candle(market, exchange_tz, row) for row in result["candles"]]
            collected.extend(c for c in page if c.start.date() >= since)
            before = result.get("nextBefore")
            if before is None or not page or min(c.start for c in page).date() <= since:
                break
        return sorted(collected, key=lambda c: c.start)

    def _auth(self) -> dict[str, str]:
        if self._token is None or self._clock() >= self._token.expires_at:
            self._token = self._issue_token()
        return {"Authorization": f"Bearer {self._token.value}"}

    def _issue_token(self) -> _Token:
        response = self._client.post(
            "/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id.get_secret_value(),
                "client_secret": self._client_secret.get_secret_value(),
            },
        )
        # 실패 응답 본문에 어떤 값이 틀렸는지가 담김 — 키 값 자체는 담기지 않음
        response.raise_for_status()
        body = response.json()
        return _Token(body["access_token"], self._clock() + body["expires_in"] - TOKEN_MARGIN_SEC)


def _to_candle(market: str, exchange_tz: ZoneInfo, row: dict[str, Any]) -> Candle:
    # 미국 일봉도 한국 시간 표기(뉴욕 0시 = 13:00+09:00)로 옴 — 거래소 시간대로 바꿔 거래일을 잡음
    # 거래일은 업비트 일봉처럼 UTC 0시에 날짜 키로 둠
    trading_day = datetime.fromisoformat(row["timestamp"]).astimezone(exchange_tz).date()
    return Candle(
        market=market,
        start=datetime(trading_day.year, trading_day.month, trading_day.day, tzinfo=UTC),
        open=Decimal(row["openPrice"]),
        high=Decimal(row["highPrice"]),
        low=Decimal(row["lowPrice"]),
        close=Decimal(row["closePrice"]),
        volume=Decimal(row["volume"]),
    )
