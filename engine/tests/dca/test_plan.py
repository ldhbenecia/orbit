from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from orbit.dca.plan import next_payday, payday_indices, run_dca
from orbit.marketdata.candle import Candle


def _candles(days: list[date], prices: list[int]) -> list[Candle]:
    return [
        Candle(
            "KRX-367380",
            datetime(d.year, d.month, d.day, tzinfo=UTC),
            *(Decimal(p),) * 4,
            Decimal(1),
        )
        for d, p in zip(days, prices, strict=True)
    ]


def test_25일이_없으면_그_전_마지막_거래일() -> None:
    # 2026-10-24·25 주말이라 일봉 없음 → 10-23(금)
    days = [
        date(2026, 10, 22),
        date(2026, 10, 23),
        date(2026, 10, 26),
        date(2026, 11, 24),
        date(2026, 11, 25),
    ]

    picked = [days[i] for i in payday_indices(_candles(days, [1] * 5))]

    assert picked == [date(2026, 10, 23), date(2026, 11, 25)]


def test_진행_중인_달은_적립일이_아직_오지_않음() -> None:
    # 데이터가 10-02 에서 끝남 — 10월 적립일(10-23)은 아직
    days = [date(2026, 9, 25), date(2026, 9, 30), date(2026, 10, 2)]

    assert [days[i] for i in payday_indices(_candles(days, [1] * 3))] == [date(2026, 9, 25)]


def test_상장일이_25일_뒤면_그달은_건너뜀() -> None:
    days = [date(2020, 10, 29), date(2020, 10, 30), date(2020, 11, 25)]

    assert [days[i] for i in payday_indices(_candles(days, [1] * 3))] == [date(2020, 11, 25)]


def test_1주_단위로_사고_남은_돈은_다음_달로() -> None:
    days = [date(2026, 1, 23), date(2026, 2, 25), date(2026, 2, 26)]
    result = run_dca(_candles(days, [30_000, 40_000, 50_000]), monthly=Decimal(100_000))

    # 1월: 10만원 → 3주(9만) 남음 1만 / 2월: 11만 → 2주(8만) 남음 3만
    assert [(b.qty, b.cost) for b in result.buys] == [(3, Decimal(90_000)), (2, Decimal(80_000))]
    assert (result.invested, result.qty, result.cash) == (Decimal(200_000), 5, Decimal(30_000))
    assert result.final_value == Decimal(30_000 + 5 * 50_000)


def test_넣은_돈_대비_최악() -> None:
    days = [date(2026, 1, 23), date(2026, 1, 26)]
    result = run_dca(_candles(days, [10_000, 5_000]), monthly=Decimal(100_000))

    assert result.worst_vs_invested == Decimal("-0.5")


def test_다음_적립일_이번달_지났으면_다음달() -> None:
    closed = {date(2026, 10, 24), date(2026, 10, 25)}

    def trading_day_for(d: date) -> date:
        while d in closed:
            d -= timedelta(days=1)
        return d

    assert next_payday(date(2026, 10, 4), trading_day_for) == date(2026, 10, 23)
    assert next_payday(date(2026, 10, 24), trading_day_for) == date(2026, 11, 25)
    assert next_payday(date(2026, 12, 26), trading_day_for) == date(2027, 1, 25)
