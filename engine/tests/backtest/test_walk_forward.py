from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from orbit.backtest.engine import BacktestResult, DailyRecord, Trade
from orbit.backtest.walk_forward import TEST, TRAIN, walk_forward

START = datetime(2018, 1, 1, tzinfo=UTC)
ONE = Decimal(1)
TINY = Decimal("1e-20")  # 날마다 나눴다 곱하는 Decimal 반올림 오차


def result(
    daily: Callable[[int], str], days: int, trade_days: tuple[int, ...] = ()
) -> BacktestResult:
    # 날마다 기준가가 daily(i) 만큼 곱해지는 가짜 백테스트 — 날짜 i 는 START + i일
    out = BacktestResult()
    nav = ONE
    for i in range(days):
        if i:
            nav *= Decimal(daily(i))
        day = START + timedelta(days=i)
        out.records.append(DailyRecord(day, Decimal(0), ONE, ONE, ONE, ONE, nav))
    for i in trade_days:
        out.trades.append(Trade(START + timedelta(days=i), "buy", ONE, ONE, ONE, ONE, ""))
    return out


T1 = TRAIN.days  # 첫 시험 시작일 (i)
DAYS = T1 + 2 * TEST.days  # 시험 두 번


def test_직전_3년에_가장_좋았던_값을_다음_1년에_씀() -> None:
    # A 는 처음 3년만 오르고, B 는 그 뒤부터 오름
    # 첫 해는 A 를 고름 — B 의 그해 상승은 고를 때 모름
    results = {
        "A": result(lambda i: "1.001" if i < T1 else "0.999", DAYS),
        "B": result(lambda i: "1.0005" if i < T1 else "1.002", DAYS),
    }

    walk = walk_forward(results, ["A", "B"], START, START + timedelta(days=DAYS - 1))

    assert walk is not None
    assert [p.spec for p in walk.picks] == ["A", "B"]  # 둘째 해의 직전 3년엔 B 가 앞섬
    # 첫 해는 A 의 하락(0.999)을 그대로 씀 — 지나고 보니 좋았던 B 로 바꿔 끼우지 않음
    first_year = walk.navs[TEST.days][1]
    assert abs(first_year - Decimal("0.999") ** TEST.days) < TINY


def test_이어_붙인_기준가는_고른_값의_날마다_수익을_곱한_것() -> None:
    results = {"A": result(lambda i: "1.001", DAYS), "B": result(lambda i: "1.0005", DAYS)}

    walk = walk_forward(results, ["A", "B"], START, START + timedelta(days=DAYS - 1))

    assert walk is not None
    assert walk.navs[0] == (START + timedelta(days=T1 - 1), ONE)  # 시작 전날 1
    assert abs(walk.navs[-1][1] - Decimal("1.001") ** (2 * TEST.days)) < TINY
    assert len(walk.navs) == 1 + 2 * TEST.days


def test_다음_1년의_성과를_바꿔도_그해_고른_값은_같음() -> None:
    base = {"A": result(lambda i: "1.001", DAYS), "B": result(lambda i: "1.0005", DAYS)}
    # B 의 시험 기간만 폭등시켜도 첫 해 선택은 그대로여야 함
    boosted = {**base, "B": result(lambda i: "1.0005" if i < T1 else "1.05", DAYS)}

    a = walk_forward(base, ["A", "B"], START, START + timedelta(days=DAYS - 1))
    b = walk_forward(boosted, ["A", "B"], START, START + timedelta(days=DAYS - 1))

    assert a is not None and b is not None
    assert a.picks[0] == b.picks[0]


def test_같으면_앞쪽_값을_고르고_고른_값의_시험_기간_매매만_셈() -> None:
    results = {
        "A": result(lambda i: "1.001", DAYS, trade_days=(10, T1 + 5)),  # 훈련 기간 매매는 안 셈
        "B": result(lambda i: "1.001", DAYS, trade_days=(T1 + 6,)),
    }

    walk = walk_forward(results, ["A", "B"], START, START + timedelta(days=DAYS - 1))

    assert walk is not None
    assert {p.spec for p in walk.picks} == {"A"}
    assert walk.trades == 1


def test_3년_뒤_시험할_날이_없으면_없음() -> None:
    results = {"A": result(lambda i: "1.001", T1)}

    assert walk_forward(results, ["A"], START, START + timedelta(days=T1 - 1)) is None


def test_반년이_안_되는_마지막_기간은_한_해로_치지_않음() -> None:
    # 시험 한 번 + 3주 — 3주짜리는 빼고 한 번만
    days = T1 + TEST.days + 21
    results = {"A": result(lambda i: "1.001", days)}

    walk = walk_forward(results, ["A"], START, START + timedelta(days=days - 1))

    assert walk is not None and len(walk.picks) == 1
    assert walk.navs[-1][0] == START + timedelta(days=T1 + TEST.days - 1)
