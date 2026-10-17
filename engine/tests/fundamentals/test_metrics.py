from datetime import UTC, date, datetime
from decimal import Decimal

from orbit.fundamentals.metrics import fundamentals, valuation
from orbit.fundamentals.snapshot import Snapshot
from orbit.marketdata.candle import Candle


def snap(filed: date = date(2020, 1, 15), **values: int | None) -> Snapshot:
    base: dict[str, int | None] = {
        "net_income": 2_500,
        "revenue": 1_200,
        "revenue_prev": 1_000,
        "operating_cf": 3_000,
        "capex": 1_000,
        "equity": 10_000,
        "shares": 1_000,
    }
    base.update(values)
    return Snapshot(filed=filed, period_end=date(2019, 12, 31), **base)


def test_지표는_시가총액과_재무값의_비율() -> None:
    v = valuation(snap(), Decimal(50))  # 시가총액 50 × 1000 = 50000

    assert v.per == Decimal(20)  # 50000 / 2500
    assert v.pbr == Decimal(5)  # 50000 / 10000
    assert v.roe == Decimal("0.25")  # 2500 / 10000
    assert v.fcf_yield == Decimal("0.04")  # (3000 − 1000) / 50000
    assert v.revenue_growth == Decimal("0.2")  # 1200 / 1000 − 1


def test_적자면_PER_없음_ROE_는_음수로() -> None:
    v = valuation(snap(net_income=-500), Decimal(50))

    assert v.per is None
    assert v.roe == Decimal("-0.05")


def test_자본이_0_이하면_PBR_ROE_없음() -> None:
    v = valuation(snap(equity=-1), Decimal(50))

    assert (v.pbr, v.roe) == (None, None)
    assert v.per == Decimal(20)


def test_주식수를_못_믿으면_시가총액_지표만_빠짐() -> None:
    v = valuation(snap(shares=None), Decimal(50))

    assert (v.per, v.pbr, v.fcf_yield) == (None, None, None)
    assert (v.roe, v.revenue_growth) == (Decimal("0.25"), Decimal("0.2"))


def candle(day: date, close: int) -> Candle:
    p = Decimal(close)
    return Candle("US-EXA", datetime(day.year, day.month, day.day, tzinfo=UTC), p, p, p, p, p)


def monthly(prices: list[int], first: date = date(2021, 1, 4)) -> list[Candle]:
    out = []
    for i, p in enumerate(prices):
        month = first.month - 1 + i
        out.append(candle(date(first.year + month // 12, month % 12 + 1, first.day), p))
    return out


def test_공시_당일_종가에는_그_보고서를_쓰지_않음() -> None:
    old = snap(filed=date(2020, 1, 15), net_income=1_000)
    new = snap(filed=date(2026, 5, 5), net_income=2_000)
    price = Decimal(10)  # 시가총액 10000

    on_day = fundamentals([old, new], [candle(date(2026, 5, 5), 10)])
    next_day = fundamentals([old, new], [candle(date(2026, 5, 6), 10)])

    assert on_day is not None and on_day.now.per == price * 1000 / 1_000
    assert next_day is not None and next_day.now.per == price * 1000 / 2_000


def test_5년_위치는_지금_달을_뺀_월말_PER_중_지금_이하인_비율() -> None:
    # 순이익 = 주식 수라 PER = 가격. 과거 40개월 100..139, 지금 120
    candles = monthly([*range(100, 140), 120])
    result = fundamentals([snap(net_income=1_000)], candles)

    assert result is not None and result.per_5y is not None
    assert result.now.per == 120
    assert (result.per_5y.low, result.per_5y.high, result.per_5y.months) == (
        Decimal(100),
        Decimal(139),
        40,
    )
    assert result.per_5y.percentile == Decimal(21) / 40  # 100..120 = 21개


def test_5년보다_오래된_달은_비교하지_않음() -> None:
    candles = monthly([100] * 80)
    result = fundamentals([snap(net_income=1_000)], candles)

    assert result is not None and result.per_5y is not None
    assert result.per_5y.months == 60


def test_비교할_달이_3년보다_적으면_위치_없음() -> None:
    result = fundamentals([snap(net_income=1_000)], monthly([100] * 36))

    assert result is not None
    assert result.per_5y is None  # 지금 달 빼면 35개월


def test_보고서_전의_달은_비교에서_빠짐() -> None:
    # 보고서가 40개월 시세 중간에 처음 나오면 그 뒤 달만
    candles = monthly([100] * 50)
    result = fundamentals([snap(filed=date(2022, 1, 1), net_income=1_000)], candles)

    assert result is not None and result.per_5y is not None
    assert result.per_5y.months == 49 - 12
