from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_DOWN, Decimal

import pytest

from orbit.dca.payday import (
    WINDOW_MONTHS,
    YEAR_BARS,
    Spend,
    buy_the_dip,
    compare,
    decide,
    run_payday,
    wait_for_trend,
)
from orbit.dca.plan import payday_indices
from orbit.marketdata.candle import Candle
from orbit.strategies.registry import build_strategy

START = date(2010, 1, 4)
NO_FEE = lambda amount: Decimal(0)  # noqa: E731


def weekdays(prices: list[Decimal]) -> list[Candle]:
    # 주말을 뺀 거래일마다 한 봉 — 예시 종목, 가짜 가격
    out = []
    day = START
    for p in prices:
        while day.weekday() >= 5:
            day += timedelta(days=1)
        out.append(
            Candle(
                "US-EXA", datetime(day.year, day.month, day.day, tzinfo=UTC), p, p, p, p, Decimal(1)
            )
        )
        day += timedelta(days=1)
    return out


def flat(n: int, price: int = 100) -> list[Candle]:
    return weekdays([Decimal(price)] * n)


# 상태마다 두 번의 월급날(가격 100, 월 1000)에서 산 주식 수·남은 돈 — 손으로 계산
EXPECTED = {
    Spend.ALL: (20, Decimal(0)),  # 10주 + 10주
    Spend.HALF_SALARY: (10, Decimal(1000)),  # 500원어치 5주씩, 절반씩 남음
    Spend.NONE: (0, Decimal(2000)),
}


@pytest.mark.parametrize("spend", list(Spend))
def test_월급날_상태마다_쓰는_돈(spend: Spend) -> None:
    candles = flat(3)
    result = run_payday(candles, [0, 2], {0: spend, 2: spend}, Decimal(1000), NO_FEE)

    assert (result.qty, result.cash) == EXPECTED[spend]
    assert result.invested == 2000


def test_수수료까지_예산_안에서_1주_단위로() -> None:
    # 1000 으로 100짜리 10주면 수수료 1% 포함 1010 — 9주 (909)
    result = run_payday(flat(1), [0], {0: Spend.ALL}, Decimal(1000), lambda a: a / 100)

    assert result.qty == 9
    assert result.fees == 9
    assert result.cash == 1000 - 900 - 9


def test_평가액은_남은_돈과_보유분의_합_남은_돈은_넣은_돈에서_쓴_돈을_뺀_것() -> None:
    prices = [Decimal(p) for p in (100, 80, 120, 60, 90, 150)]
    candles = weekdays(prices)
    choices = {0: Spend.HALF_SALARY, 1: Spend.ALL, 3: Spend.NONE, 4: Spend.ALL}
    fee = lambda a: (a * Decimal("0.003")).quantize(Decimal(1), ROUND_DOWN)  # noqa: E731

    r = run_payday(candles, [0, 1, 3, 4], choices, Decimal(777), fee)

    # 0일 절반 388.5 → 100×3 (수수료 0), 남음 477
    # 1일 전부 1254 → 80×15 = 1200 + 수수료 3, 남음 51
    # 3일 안 삼 → 828, 4일 전부 1605 → 90×17 = 1530 + 수수료 4, 남음 71
    assert (r.qty, r.cash, r.fees, r.buys) == (35, Decimal(71), Decimal(7), 3)
    assert r.final_value == r.cash + 150 * r.qty == 5321
    assert r.cash == r.invested - (300 + 1200 + 1530) - r.fees


@pytest.mark.parametrize(
    ("last", "spend"),
    [(80, Spend.ALL), (Decimal("80.01"), Spend.HALF_SALARY)],  # 고점 100 대비 −20% 와 그 직전
)
def test_52주_고점_대비_20퍼센트_이하면_모아_둔_돈까지(last: Decimal, spend: Spend) -> None:
    history = weekdays([Decimal(100)] * 10 + [Decimal(last)])

    assert buy_the_dip(history).spend is spend


def test_추세_규칙은_대시보드_신호와_같은_판단() -> None:
    # 오르다 내리는 가격 — 200일 평균 위·아래가 모두 나옴
    prices = [Decimal(100 + i) for i in range(300)] + [Decimal(400 - 2 * i) for i in range(200)]
    candles = weekdays(prices)
    signal, _ = build_strategy("ma-200")

    for i in range(200, len(candles), 37):
        holding = signal(candles[:i]).target_weight > 0
        assert (wait_for_trend(candles[:i]).spend is Spend.ALL) == holding


def test_월급날_판단은_그날과_이후_봉이_바뀌어도_같음() -> None:
    prices = [Decimal(100 + (i % 50)) for i in range(600)]
    candles = weekdays(prices)
    paydays = [i for i in payday_indices(candles) if i >= YEAR_BARS]
    before = decide(candles, paydays)
    target = paydays[3]
    # 월급날 당일부터 폭락으로 바꿔도 그날 판단은 그대로여야 함
    crashed = candles[:target] + [
        Candle(c.market, c.start, *(Decimal(1),) * 4, c.volume) for c in candles[target:]
    ]

    after = decide(crashed, paydays)

    assert {n: d[target] for n, d in before.items()} == {n: d[target] for n, d in after.items()}


def test_1년_지나기_전_월급날은_비교에서_빠짐() -> None:
    candles = flat(YEAR_BARS + 130)
    result = compare(candles, Decimal(1000), NO_FEE)
    counted = [i for i in payday_indices(candles) if i >= YEAR_BARS]

    assert result is not None
    assert all(r.invested == 1000 * len(counted) for r in result.full.values())


def test_계속_오르면_구간마다_단순_적립이_가장_많음() -> None:
    # 떨어진 적이 없어 "떨어지면 더" 는 절반을 놀리고, 추세 규칙은 단순 적립과 똑같이 삼
    # — 둘 다 이기지 못함
    prices = [
        Decimal(100) * Decimal("1.0005") ** i for i in range(YEAR_BARS + 21 * (WINDOW_MONTHS + 6))
    ]
    candles = weekdays([p.quantize(Decimal("0.01")) for p in prices])
    result = compare(candles, Decimal(1000), NO_FEE)

    assert result is not None
    paydays = [i for i in payday_indices(candles) if i >= YEAR_BARS]
    assert result.windows == len(paydays) - WINDOW_MONTHS > 0
    assert result.beat_plain == {"dip": 0, "trend": 0}
    assert result.full["trend"].final_value == result.full["plain"].final_value
