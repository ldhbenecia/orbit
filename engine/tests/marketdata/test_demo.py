from datetime import UTC, date, datetime

from orbit.marketdata.demo import demo_candles, demo_snapshots


def test_가상_일봉은_같은_시드면_같고_고저가가_시종가를_감쌈() -> None:
    start, end = datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 3, 1, tzinfo=UTC)

    first = demo_candles("KRW-BTC", start, end)
    again = demo_candles("KRW-BTC", start, end)

    assert first == again
    assert all(c.low <= min(c.open, c.close) and c.high >= max(c.open, c.close) for c in first)
    assert all(c.close == c.close.to_integral_value() for c in first)  # 원화는 원 단위


def test_주식은_주말이_없고_달러는_센트_단위() -> None:
    start, end = datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 2, 1, tzinfo=UTC)

    candles = demo_candles("US-QQQ", start, end)

    assert all(c.start.weekday() < 5 for c in candles)
    assert all(c.close == round(c.close, 2) for c in candles)


def test_가상_재무는_분기_끝_뒤에_공시되고_끝날_뒤는_없음() -> None:
    snaps = demo_snapshots("US-QQQ", date(2024, 1, 1), date(2025, 1, 1))

    # 4분기(12월 31일) 보고서는 40일 뒤 공시라 끝날 뒤 — 빠짐
    assert [s.period_end for s in snaps] == [
        date(2024, 3, 31),
        date(2024, 6, 30),
        date(2024, 9, 30),
    ]
    assert all(s.filed > s.period_end for s in snaps)
    assert snaps == demo_snapshots("US-QQQ", date(2024, 1, 1), date(2025, 1, 1))
