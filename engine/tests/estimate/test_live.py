from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from orbit.estimate.live import build_view
from orbit.marketdata.candle import Candle
from orbit.marketdata.instruments import SEOUL
from orbit.marketdata.tiger_holdings import Holding


def _kr_day(day: str, regular: tuple[str, str] | None) -> dict[str, Any]:
    if regular is None:
        return {"date": day, "integrated": None}
    start, end = regular
    return {
        "date": day,
        "integrated": {
            "regularMarket": {"startTime": f"{day}T{start}+09:00", "endTime": f"{day}T{end}+09:00"}
        },
    }


# 일요일 10/4 — 금요일 10/2 장 마감, 월요일 10/5 대체공휴일, 다음 개장 10/6
SUNDAY_KR = {
    "today": _kr_day("2026-10-04", None),
    "previousBusinessDay": _kr_day("2026-10-02", ("09:00:00", "15:30:00")),
    "nextBusinessDay": _kr_day("2026-10-06", ("09:00:00", "15:30:00")),
}
# 미국 월요일 10/5 장이 한국 10/6 개장 전에 끝남
SUNDAY_US = {
    "today": {"date": "2026-10-04", "regularMarket": None},
    "nextBusinessDay": {
        "date": "2026-10-05",
        "regularMarket": {
            "startTime": "2026-10-05T22:30:00+09:00",
            "endTime": "2026-10-06T05:00:00+09:00",
        },
    },
}


def _candle(market: str, day: date, close: str) -> Candle:
    price = Decimal(close)
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    return Candle(market, start, price, price, price, price, Decimal(1))


class FakeSource:
    def __init__(self, kr: dict[str, Any], us: dict[str, Any], candles: dict[str, list[Candle]]):
        self.kr, self.us, self.candles = kr, us, candles
        self.fx_requests: list[dict[str, str | int]] = []

    def get(self, path: str, params: dict[str, str | int]) -> dict[str, Any]:
        if path.endswith("/KR"):
            return {"result": self.kr}
        if path.endswith("/US"):
            return {"result": self.us}
        self.fx_requests.append(params)
        mid = "1350" if "dateTime" in params else "1363.5"
        return {"result": {"midRate": mid}}

    def daily_candles(
        self, symbol: str, market: str, exchange_tz: ZoneInfo, since: date
    ) -> list[Candle]:
        if symbol not in self.candles:  # 토스에 없는 종목
            request = httpx.Request("GET", "https://openapi.tossinvest.com/api/v1/candles")
            raise httpx.HTTPStatusError("", request=request, response=httpx.Response(404))
        return self.candles[symbol]


NOW = datetime(2026, 10, 4, 12, tzinfo=SEOUL)


def _no_holdings(fund: str) -> list[Holding]:
    raise AssertionError("지수 근사 ETF 는 구성 종목을 받지 않음")


def test_주말에는_금요일_한국_종가에_금요일_밤_미국장과_환율을_반영해_화요일_개장을_추정() -> None:
    source = FakeSource(
        SUNDAY_KR,
        SUNDAY_US,
        {
            "367380": [
                _candle("KRX-367380", date(2026, 10, 1), "7000"),
                _candle("KRX-367380", date(2026, 10, 2), "7360"),
            ],
            "QQQ": [
                _candle("US-QQQ", date(2026, 10, 1), "100"),
                _candle("US-QQQ", date(2026, 10, 2), "103"),
            ],
        },
    )

    view = build_view("KRX-367380", source, _no_holdings, NOW)

    assert view.state == "ready" and view.result is not None
    assert view.next_open_day == date(2026, 10, 6)
    assert (view.kr_close_day, view.us_reference_day, view.us_latest_day) == (
        date(2026, 10, 2),
        date(2026, 10, 1),
        date(2026, 10, 2),
    )
    assert view.result.estimate == Decimal("7656.608")  # 7360 × 1.03 × 1.01
    # 환율 기준 시각은 한국 장 마감 15:30
    assert source.fx_requests[0]["dateTime"] == "2026-10-02T15:30:00+09:00"
    assert view.us_pending  # 월요일 미국장이 화요일 개장 전에 끝남


def test_한국장_중에는_종가가_없어_추정하지_않음() -> None:
    kr = {
        "today": _kr_day("2026-10-06", ("09:00:00", "15:30:00")),
        "previousBusinessDay": _kr_day("2026-10-02", ("09:00:00", "15:30:00")),
        "nextBusinessDay": _kr_day("2026-10-07", ("09:00:00", "15:30:00")),
    }

    view = build_view(
        "KRX-367380",
        FakeSource(kr, SUNDAY_US, {"367380": []}),
        _no_holdings,
        datetime(2026, 10, 6, 10, tzinfo=SEOUL),
    )

    assert view.state == "kr_open" and view.result is None


def test_구성_종목_중_시세가_없는_종목은_빼고_반영_비중으로_알림() -> None:
    holdings = [
        Holding("AAA US EQUITY", "AAA", "A Corp", Decimal("0.5"), False),
        Holding("BBB US EQUITY", "BBB", "B Corp", Decimal("0.2"), False),  # 시세 없음
        Holding("KRD010010001", None, "원화예금", Decimal("0.3"), True),
    ]
    source = FakeSource(
        SUNDAY_KR,
        SUNDAY_US,
        {
            "0183J0": [_candle("KRX-0183J0", date(2026, 10, 2), "10000")],
            "AAA": [
                _candle("US-AAA", date(2026, 10, 1), "100"),
                _candle("US-AAA", date(2026, 10, 2), "110"),
            ],
        },
    )

    view = build_view("KRX-0183J0", source, lambda fund: holdings, NOW)

    assert view.result is not None
    assert view.coverage == Decimal("0.8")
    assert [leg.symbol for leg in view.legs] == ["AAA"]
    # 남은 비중 0.5(+10%·환율 +1%) + 현금 0.3 을 비례로 — (0.5×1.1×1.01 + 0.3) / 0.8
    assert view.result.estimate == Decimal(10000) * (
        Decimal("0.5") * Decimal("1.1") * Decimal("1.01") + Decimal("0.3")
    ) / Decimal("0.8")


def test_옛_심볼은_확인된_새_심볼로_시세를_받음() -> None:
    holdings = [Holding("SATS US EQUITY", "SATS", "EchoStar Corp", Decimal(1), False)]
    source = FakeSource(
        SUNDAY_KR,
        SUNDAY_US,
        {
            "0183J0": [_candle("KRX-0183J0", date(2026, 10, 2), "10000")],
            "ECHO": [
                _candle("US-ECHO", date(2026, 10, 1), "100"),
                _candle("US-ECHO", date(2026, 10, 2), "105"),
            ],
        },
    )

    view = build_view("KRX-0183J0", source, lambda fund: holdings, NOW)

    assert [leg.symbol for leg in view.legs] == ["ECHO"] and view.coverage == 1


def test_한국_종가와_같은_날_기준가가_있으면_기준가에서도_추정() -> None:
    source = FakeSource(
        SUNDAY_KR,
        SUNDAY_US,
        {
            "367380": [_candle("KRX-367380", date(2026, 10, 2), "7360")],
            "QQQ": [
                _candle("US-QQQ", date(2026, 10, 1), "100"),
                _candle("US-QQQ", date(2026, 10, 2), "103"),
            ],
        },
    )

    same_day = build_view(
        "KRX-367380", source, _no_holdings, NOW, lambda k, f: (date(2026, 10, 2), Decimal(7300))
    )
    stale = build_view(
        "KRX-367380", source, _no_holdings, NOW, lambda k, f: (date(2026, 10, 1), Decimal(7400))
    )

    assert same_day.nav_estimate == Decimal("7594.19")  # 7300 × 1.03 × 1.01
    # 하루 늦게 올라온 기준가는 반영된 미국장이 달라 쓰지 않음 — 날짜만 알려 줌
    assert stale.nav_estimate is None and stale.nav_day == date(2026, 10, 1)
