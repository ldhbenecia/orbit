import json
import threading
import time
from collections import deque
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
# 조회 경로 → 호출 한도 그룹. 이 표에 없는 경로(주문·계좌)는 요청 전에 거부
PATH_GROUPS = {
    "/api/v1/candles": "MARKET_DATA_CHART",
    "/api/v1/prices": "MARKET_DATA",
    "/api/v1/stocks": "STOCK",
    "/api/v1/exchange-rate": "MARKET_INFO",
    "/api/v1/market-calendar/KR": "MARKET_INFO",
    "/api/v1/market-calendar/US": "MARKET_INFO",
}
ALLOWED_PATHS = frozenset(PATH_GROUPS)
# 공식 문서의 클라이언트 × 그룹별 초당 한도 — 넘으면 429
GROUP_LIMITS = {"MARKET_DATA_CHART": 20, "MARKET_DATA": 15, "STOCK": 5, "MARKET_INFO": 3}
# 1초 경계에 딱 맞춰 보내면 도착 시각 차이로 서버가 한 구간에 넣어 셀 수 있음
RATE_WINDOW_SEC = 1.2
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
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client
        self._client_id = client_id
        self._client_secret = client_secret
        self._clock = clock
        self._token: _Token | None = None
        # 토큰은 클라이언트당 1개 — 여러 스레드가 동시에 재발급하면 서로의 토큰을 무효화함
        self._token_lock = threading.Lock()
        self._sleep = sleep
        self._sent: dict[str, deque[float]] = {group: deque() for group in GROUP_LIMITS}
        self._group_locks = {group: threading.Lock() for group in GROUP_LIMITS}

    def get(self, path: str, params: dict[str, str | int]) -> dict[str, Any]:
        if path not in ALLOWED_PATHS:
            raise ForbiddenPathError(f"토스 조회 허용 경로가 아님: {path}")
        self._wait_turn(PATH_GROUPS[path])
        response = self._client.get(path, params=params, headers=self._auth())
        if response.status_code == 401:
            # 다른 곳에서 재발급해 무효가 된 토큰일 수 있음 — 한 번만 새로 받고 재시도
            with self._token_lock:
                self._token = None
            response = self._client.get(path, params=params, headers=self._auth())
        if response.status_code == 429:
            # 같은 키를 쓰는 다른 프로세스(동기화 등)와 겹치면 한도를 넘음 — 한 번만 쉬고 재시도
            self._sleep(RATE_WINDOW_SEC)
            self._wait_turn(PATH_GROUPS[path])
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

    def kr_trading_day_for(self, day: date) -> date:
        # day 가 휴장이면 그 전 영업일 — 평일 공휴일(한글날 등)은 요일만으로 알 수 없음
        result = self.get("/api/v1/market-calendar/KR", {"date": day.isoformat()})["result"]
        if result["today"].get("integrated") is not None:
            return day
        return date.fromisoformat(result["previousBusinessDay"]["date"])

    def _wait_turn(self, group: str) -> None:
        # 최근 구간 안에 한도만큼 보냈으면 가장 오래된 요청이 구간을 벗어날 때까지 기다림
        limit, sent = GROUP_LIMITS[group], self._sent[group]
        with self._group_locks[group]:
            while True:
                now = self._clock()
                while sent and now - sent[0] >= RATE_WINDOW_SEC:
                    sent.popleft()
                if len(sent) < limit:
                    sent.append(now)
                    return
                self._sleep(RATE_WINDOW_SEC - (now - sent[0]))

    def _auth(self) -> dict[str, str]:
        with self._token_lock:
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
