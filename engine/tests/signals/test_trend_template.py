from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from orbit.marketdata.candle import Candle
from orbit.signals.trend_template import (
    RISING_BARS,
    YEAR_BARS,
    Check,
    strength_ranks,
    trend_template,
)

START = datetime(2025, 1, 1, tzinfo=UTC)


def bars(closes: Sequence[Decimal | int | str]) -> list[Candle]:
    # 예시 종목, 가짜 가격 — 날짜 간격은 판단과 무관
    out = []
    for i, c in enumerate(closes):
        p = Decimal(c)
        out.append(Candle("US-EXA", START + timedelta(days=i), p, p, p, p, Decimal(1)))
    return out


def test_1년이_안_되면_판단하지_않음() -> None:
    assert trend_template(bars([100] * (YEAR_BARS - 1)), Decimal(1)) is None


def test_꾸준히_오르면_모든_조건_충족_꾸준히_내리면_가격_조건_모두_실패() -> None:
    up = trend_template(bars([100 + i for i in range(300)]), Decimal("0.9"))
    down = trend_template(bars([400 - i for i in range(300)]), Decimal("0.1"))

    assert up is not None and set(up) == set(Check)
    assert all(up.values())
    assert down is not None
    assert not any(down.values())


@pytest.mark.parametrize(("last", "passed"), [("130", True), ("129.99", False)])
def test_52주_저점보다_30퍼센트_이상_위(last: str, passed: bool) -> None:
    # 1년 최저 100 → 130 이상이어야 함
    result = trend_template(bars([100] * (YEAR_BARS - 1) + [last]), None)

    assert result is not None and result[Check.ABOVE_LOW] is passed


@pytest.mark.parametrize(("last", "passed"), [("150", True), ("149.99", False)])
def test_52주_고점에서_25퍼센트_이내(last: str, passed: bool) -> None:
    # 1년 최고 200 → 150 이상이어야 함
    result = trend_template(bars([200] + [180] * (YEAR_BARS - 2) + [last]), None)

    assert result is not None and result[Check.NEAR_HIGH] is passed


@pytest.mark.parametrize(("recent", "rising"), [(101, True), (99, False)])
def test_200일_평균이_한_달_전보다_높아야(recent: int, rising: bool) -> None:
    # 평평하다가 최근 한 달만 오르거나 내림 — 한 달 전 평균은 100
    result = trend_template(bars([100] * (YEAR_BARS - RISING_BARS) + [recent] * RISING_BARS), None)

    assert result is not None and result[Check.MA200_RISING] is rising


@pytest.mark.parametrize(
    ("strength", "passed"), [(Decimal("0.7"), True), (Decimal("0.69"), False), (None, None)]
)
def test_상대강도는_상위_30퍼센트_모르면_비움(
    strength: Decimal | None, passed: bool | None
) -> None:
    result = trend_template(bars([100 + i for i in range(300)]), strength)

    assert result is not None and result[Check.STRONG] is passed


def test_상대강도는_나보다_1년_수익률이_낮은_종목_비율() -> None:
    returns = {
        m: Decimal(r)
        for m, r in zip("ABCDEF", ("0.1", "0.2", "0.2", "-0.3", "0.5", "0.9"), strict=True)
    }

    ranks = strength_ranks(returns)

    # 나 빼고 5종목 중 나보다 낮은 수 — 같은 수익률끼리는 같은 순위
    assert ranks == {
        "D": Decimal(0),
        "A": Decimal(1) / 5,
        "B": Decimal(2) / 5,
        "C": Decimal(2) / 5,
        "E": Decimal(4) / 5,
        "F": Decimal(1),
    }


def test_비교_종목이_5개_미만이면_상대강도를_모름() -> None:
    assert strength_ranks({m: Decimal(i) for i, m in enumerate("ABCD")}) == {}
