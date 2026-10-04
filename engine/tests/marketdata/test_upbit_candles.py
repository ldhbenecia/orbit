import json
from datetime import UTC, datetime
from decimal import Decimal

from orbit.marketdata.upbit_candles import PAGE_SIZE, fetch_daily_candles, parse_candles
from tests.marketdata.fake_upbit import FakeUpbit, candle_row

D = datetime(2024, 1, 1, tzinfo=UTC)


def test_가격은_float_오차_없이_Decimal_로_파싱됨() -> None:
    payload = json.dumps([candle_row(D, close="115216000.1")])

    candle = parse_candles(payload)[0]

    assert candle.close == Decimal("115216000.1")
    assert isinstance(candle.volume, Decimal)


def test_봉_시각은_UTC_tz_aware() -> None:
    candle = parse_candles(json.dumps([candle_row(D)]))[0]

    assert candle.start == D
    assert candle.start.tzinfo is UTC


def test_200개가_넘으면_to_로_과거_방향_페이지를_넘겨_전부_오름차순으로_모음() -> None:
    fake = FakeUpbit(first=datetime(2023, 1, 1, tzinfo=UTC), last=datetime(2024, 3, 1, tzinfo=UTC))
    sleeps: list[float] = []

    candles = fetch_daily_candles(
        fake.client(), "KRW-BTC", since=datetime(2017, 1, 1, tzinfo=UTC), sleep=sleeps.append
    )

    assert [c.start for c in candles] == fake.starts
    assert len(fake.requests) == len(fake.starts) // PAGE_SIZE + 1
    assert "to" not in fake.requests[0].url.params
    assert len(sleeps) == len(fake.requests) - 1


def test_since_이전_봉은_버리고_since_에_닿으면_더_요청하지_않음() -> None:
    fake = FakeUpbit(first=datetime(2020, 1, 1, tzinfo=UTC), last=datetime(2024, 3, 1, tzinfo=UTC))
    since = datetime(2024, 2, 20, tzinfo=UTC)

    candles = fetch_daily_candles(fake.client(), "KRW-BTC", since=since, sleep=lambda _: None)

    assert candles[0].start == since
    assert candles[-1].start == datetime(2024, 3, 1, tzinfo=UTC)
    assert len(fake.requests) == 1
