import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
import pytest
from pydantic import SecretStr

from orbit.marketdata.instruments import NEW_YORK
from orbit.marketdata.toss import ACCOUNT_HEADER, ForbiddenPathError, TossMarketData, _to_candle


def _candle(day: str, close: str = "500.25") -> dict[str, str]:
    return {
        "timestamp": f"{day}T13:00:00.000+09:00",  # 실제 응답 형식 — 뉴욕 0시를 한국 시간으로
        "openPrice": "499.10",
        "highPrice": "501.00",
        "lowPrice": "498.00",
        "closePrice": close,
        "volume": "1200",
        "currency": "USD",
    }


class FakeToss:
    def __init__(self, pages: list[tuple[list[str], str | None]] | None = None) -> None:
        self.pages = pages or [([], None)]
        self.requests: list[httpx.Request] = []
        self.tokens_issued = 0
        self.reject_next_with_401 = False
        self.slept: list[float] = []
        self.reject_next_with_429 = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path == "/oauth2/token":
            self.tokens_issued += 1
            return httpx.Response(
                200,
                json={
                    "access_token": f"t{self.tokens_issued}",
                    "token_type": "Bearer",
                    "expires_in": 86400,
                },
            )
        if self.reject_next_with_429:
            self.reject_next_with_429 = False
            return httpx.Response(429, json={"error": {"code": "rate-limit-exceeded"}})
        if self.reject_next_with_401:
            self.reject_next_with_401 = False
            return httpx.Response(401, json={"error": {"code": "expired-token"}})
        before = request.url.params.get("before")
        index = 0 if before is None else int(before)
        days, next_before = self.pages[index]
        body = {"result": {"candles": [_candle(d) for d in days], "nextBefore": next_before}}
        return httpx.Response(200, text=json.dumps(body))

    def api(self, clock: list[float] | None = None) -> TossMarketData:
        now = clock or [0.0]
        client = httpx.Client(
            base_url="https://openapi.tossinvest.com", transport=httpx.MockTransport(self.handler)
        )

        def sleep(seconds: float) -> None:
            self.slept.append(seconds)
            now[0] += seconds

        return TossMarketData(
            client, SecretStr("id"), SecretStr("secret"), clock=lambda: now[0], sleep=sleep
        )


@pytest.mark.parametrize(
    "path", ["/api/v1/orders", "/api/v1/accounts", "/api/v1/holdings", "/api/v1/conditional-orders"]
)
def test_주문·계좌_경로는_요청을_보내기_전에_거부(path: str) -> None:
    fake = FakeToss()

    with pytest.raises(ForbiddenPathError):
        fake.api().get(path, {})

    assert fake.requests == []


def test_계좌_헤더는_절대_붙이지_않음() -> None:
    fake = FakeToss()

    fake.api().get("/api/v1/candles", {"symbol": "QQQ", "interval": "1d"})

    assert all(ACCOUNT_HEADER not in r.headers for r in fake.requests)


def test_토큰은_재사용하고_만료_직전에만_새로_받음() -> None:
    fake = FakeToss()
    now = [0.0]
    api = fake.api(now)

    api.get("/api/v1/candles", {"symbol": "QQQ"})
    api.get("/api/v1/candles", {"symbol": "SPY"})
    now[0] = 86400 - 30  # 만료 30초 전 — 여유 60초 안
    api.get("/api/v1/candles", {"symbol": "QQQ"})

    assert fake.tokens_issued == 2


def test_401_이면_토큰을_한_번_새로_받아_재시도() -> None:
    fake = FakeToss()
    api = fake.api()
    api.get("/api/v1/candles", {"symbol": "QQQ"})
    fake.reject_next_with_401 = True

    api.get("/api/v1/candles", {"symbol": "QQQ"})

    assert fake.tokens_issued == 2
    assert fake.requests[-1].headers["Authorization"] == "Bearer t2"


def test_일봉을_nextBefore_로_넘겨_오름차순으로_모으고_since_에서_멈춤() -> None:
    fake = FakeToss(
        [
            (["2026-10-02", "2026-10-01"], "1"),
            (["2026-09-30", "2026-09-29"], "2"),
            (["2026-09-28"], None),
        ]
    )

    candles = fake.api().daily_candles("QQQ", "US-QQQ", NEW_YORK, since=date(2026, 9, 29))

    assert [c.start for c in candles] == [datetime(2026, 9, d, tzinfo=UTC) for d in (29, 30)] + [
        datetime(2026, 10, d, tzinfo=UTC) for d in (1, 2)
    ]
    assert len([r for r in fake.requests if r.url.path == "/api/v1/candles"]) == 2


def test_가격은_문자열에서_Decimal_로_날짜는_거래소_현지_거래일() -> None:
    fake = FakeToss([(["2026-10-02"], None)])

    (candle,) = fake.api().daily_candles("QQQ", "US-QQQ", NEW_YORK, since=date(2026, 1, 1))

    assert candle.close == Decimal("500.25")
    assert candle.start == datetime(2026, 10, 2, tzinfo=UTC)


def test_서머타임이_끝나도_뉴욕_거래일로_날짜를_잡음() -> None:
    # 겨울에는 뉴욕 0시가 한국 14시
    row = _candle("2026-12-01") | {"timestamp": "2026-12-01T14:00:00.000+09:00"}

    assert _to_candle("US-QQQ", NEW_YORK, row).start == datetime(2026, 12, 1, tzinfo=UTC)


def test_여러_스레드가_동시에_불러도_토큰은_한_번만_발급() -> None:
    fake = FakeToss()
    api = fake.api()

    with ThreadPoolExecutor(8) as pool:
        list(pool.map(lambda _: api.get("/api/v1/candles", {"symbol": "QQQ"}), range(32)))

    assert fake.tokens_issued == 1


def test_그룹별_초당_한도를_넘기_전에_기다림() -> None:
    # 장 캘린더·환율은 같은 그룹, 초당 3회
    fake = FakeToss()
    api = fake.api()

    for _ in range(3):
        api.get("/api/v1/market-calendar/KR", {})
    assert fake.slept == []

    api.get("/api/v1/exchange-rate", {})
    assert fake.slept == [1.2]  # 첫 요청이 구간(1초 + 여유)을 벗어날 때까지

    api.get("/api/v1/candles", {})  # 다른 그룹은 따로 셈
    assert fake.slept == [1.2]


def test_429_면_한_번만_쉬고_재시도() -> None:
    fake = FakeToss()
    fake.reject_next_with_429 = True
    api = fake.api()

    api.get("/api/v1/candles", {"symbol": "QQQ"})

    assert fake.slept == [1.2]
    assert [r.url.path for r in fake.requests].count("/api/v1/candles") == 2
