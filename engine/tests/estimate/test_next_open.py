from datetime import UTC, date, datetime
from decimal import Decimal

from orbit.estimate.next_open import Leg, estimate_next_open, us_closes_around
from orbit.marketdata.candle import Candle
from orbit.marketdata.instruments import SEOUL


def _us(day: date, close: str) -> Candle:
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)  # 거래일 날짜 키
    price = Decimal(close)
    return Candle("US-QQQ", start, price, price, price, price, Decimal(1))


def test_환노출_ETF_추정가는_미국_등락과_환율_변동을_곱함() -> None:
    legs = [Leg("QQQ", "QQQ", Decimal(1), Decimal(100), Decimal(102))]

    result = estimate_next_open(Decimal(10000), legs, Decimal(0), Decimal(1350), Decimal("1363.5"))

    assert result.basket_change == Decimal("0.02")
    assert result.fx_change == Decimal("0.01")
    assert result.estimate == Decimal("10302")  # 10000 × 1.02 × 1.01


def test_원화_현금은_환율_영향을_받지_않음() -> None:
    legs = [
        Leg("A", "A", Decimal("0.6"), Decimal(100), Decimal(110)),
        Leg("B", "B", Decimal("0.39"), Decimal(100), Decimal(90)),
    ]

    flat = estimate_next_open(Decimal(10000), legs, Decimal("0.01"), Decimal(1000), Decimal(1000))
    fx_up = estimate_next_open(Decimal(10000), legs, Decimal("0.01"), Decimal(1000), Decimal(1100))

    assert flat.estimate == Decimal("10210")  # 0.6×1.1 + 0.39×0.9 + 0.01
    assert fx_up.estimate == Decimal("11221")  # 달러 쪽 1.011 만 ×1.1, 현금 0.01 은 그대로


def test_비중_합이_1이_아니면_비율로_맞춤() -> None:
    # 시세를 못 받은 종목을 빼면 남은 비중 합이 1보다 작음 — 남은 종목으로 비례 추정
    legs = [Leg("A", "A", Decimal("0.3"), Decimal(100), Decimal(110))]

    result = estimate_next_open(Decimal(10000), legs, Decimal(0), Decimal(1000), Decimal(1000))

    assert result.estimate == Decimal("11000")


def test_기준은_한국_종가_전에_끝난_미국장_최신은_지금까지_끝난_미국장() -> None:
    candles = [
        _us(date(2026, 9, 30), "98"),
        _us(date(2026, 10, 1), "100"),
        _us(date(2026, 10, 2), "103"),
    ]
    kr_close_at = datetime(2026, 10, 2, 15, 30, tzinfo=SEOUL)  # 뉴욕 10/2 02:30 — 10/1 장만 끝남

    weekend = us_closes_around(candles, kr_close_at, now=datetime(2026, 10, 4, 12, tzinfo=SEOUL))
    before_us_close = us_closes_around(
        candles, kr_close_at, now=datetime(2026, 10, 2, 22, tzinfo=SEOUL)
    )

    assert weekend is not None and before_us_close is not None
    assert (weekend.reference.close, weekend.latest.close) == (Decimal(100), Decimal(103))
    # 10/2 미국장은 아직 진행 중 — 진행 중인 봉 종가는 쓰지 않음
    assert before_us_close.latest.close == Decimal(100)


def test_겨울에도_뉴욕_시간대로_마감을_판단() -> None:
    # 1월 뉴욕 16시 = 한국 다음 날 6시 (여름은 5시)
    candles = [_us(date(2026, 1, 14), "100"), _us(date(2026, 1, 15), "101")]
    kr_close_at = datetime(2026, 1, 15, 15, 30, tzinfo=SEOUL)  # 1/14 장 반영

    at_5 = us_closes_around(candles, kr_close_at, now=datetime(2026, 1, 16, 5, 30, tzinfo=SEOUL))
    at_6 = us_closes_around(candles, kr_close_at, now=datetime(2026, 1, 16, 6, 0, tzinfo=SEOUL))

    assert at_5 is not None and at_6 is not None
    assert at_5.latest.close == Decimal(100)
    assert at_6.latest.close == Decimal(101)


def test_한국_종가_전에_끝난_미국장이_없으면_계산하지_않음() -> None:
    candles = [_us(date(2026, 10, 2), "103")]
    kr_close_at = datetime(2026, 10, 2, 15, 30, tzinfo=SEOUL)

    assert us_closes_around(candles, kr_close_at, now=datetime(2026, 10, 4, tzinfo=SEOUL)) is None
