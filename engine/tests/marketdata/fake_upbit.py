import json
from datetime import UTC, datetime, timedelta

import httpx


def candle_row(start: datetime, close: str = "100000000.0") -> dict[str, object]:
    return {
        "market": "KRW-BTC",
        "candle_date_time_utc": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "opening_price": 99000000.0,
        "high_price": 101000000.0,
        "low_price": 98000000.0,
        "trade_price": float(close),
        "candle_acc_trade_volume": 12.5,
        "candle_acc_trade_price": 1250000000.0,
    }


class FakeUpbit:
    """요청된 to·count 를 실제 API 처럼 처리 — to 이전 봉을 최신순으로"""

    def __init__(self, first: datetime, last: datetime) -> None:
        days = (last - first).days + 1
        self.starts = [first + timedelta(days=i) for i in range(days)]
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        count = int(request.url.params["count"])
        to_param = request.url.params.get("to")
        newest_first = sorted(self.starts, reverse=True)
        if to_param:
            to = datetime.strptime(to_param, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
            newest_first = [s for s in newest_first if s < to]
        rows = [candle_row(s) for s in newest_first[:count]]
        return httpx.Response(200, text=json.dumps(rows))

    def client(self) -> httpx.Client:
        return httpx.Client(
            base_url="https://api.upbit.com", transport=httpx.MockTransport(self.handler)
        )
