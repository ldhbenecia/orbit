from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from orbit.marketdata.candle import Candle
from orbit.signals.gap_events import AFTER_BARS, PRIOR_BARS, VOLUME_BARS, gap_ups

START = datetime(2024, 1, 1, tzinfo=UTC)


def bar(i: int, o: str, c: str, volume: str) -> Candle:
    # 예시 종목, 가짜 가격 — 고가·저가는 판단에 안 씀
    op, cl = Decimal(o), Decimal(c)
    return Candle(
        "US-EXA", START + timedelta(days=i), op, max(op, cl), min(op, cl), cl, Decimal(volume)
    )


def flat(n: int, start: int = 0, price: str = "100", volume: str = "10") -> list[Candle]:
    return [bar(start + i, price, price, volume) for i in range(n)]


def with_event(
    o: str, c: str, volume: str, before: int = VOLUME_BARS, after: int = 0
) -> list[Candle]:
    # 평평한 가격 100·거래량 10 뒤에 하루, 그 뒤 after 일 더
    return [*flat(before), bar(before, o, c, volume), *flat(after, before + 1, price=c)]


@pytest.mark.parametrize(
    ("o", "volume", "found"),
    [
        ("110", "30", True),  # 갭 10%, 거래량 평균 10 의 3배 — 둘 다 경계에서 포함
        ("109.99", "30", False),  # 갭이 10% 에 못 미침
        ("110", "29.99", False),  # 거래량이 3배에 못 미침
        ("90", "100", False),  # 갭 하락은 아님
    ],
)
def test_시가가_10퍼센트_이상_갭_상승하고_거래량이_3배_이상인_날(
    o: str, volume: str, found: bool
) -> None:
    assert bool(gap_ups(with_event(o, o, volume))) is found


def test_갭_크기와_거래량_배수와_당일_수익을_손으로_계산한_값() -> None:
    # 전날 종가 100 → 시가 120 (갭 20%), 종가 130 (당일 30%), 거래량 45 ÷ 직전 평균 10 = 4.5배
    (event,) = gap_ups(with_event("120", "130", "45"))

    assert (event.gap, event.day_return, event.volume_multiple) == (
        Decimal("0.2"),
        Decimal("0.3"),
        Decimal("4.5"),
    )
    assert event.day == (START + timedelta(days=VOLUME_BARS)).date()


def test_직전_6개월과_그_뒤_1개월은_기록이_있을_때만() -> None:
    short = gap_ups(with_event("120", "130", "45"))[0]
    # 직전 6개월 전 종가 50 → 전날 100 은 +100%, 그날 종가 130 → 1개월 뒤 143 은 +10%
    history = [*flat(1, price="50"), *flat(PRIOR_BARS, 1)]
    events = gap_ups(
        [
            *history,
            bar(len(history), "120", "130", "45"),
            *flat(AFTER_BARS - 1, len(history) + 1, price="130"),
            bar(len(history) + AFTER_BARS, "143", "143", "10"),
        ]
    )

    assert (short.prior, short.after) == (None, None)
    assert (events[0].prior, events[0].after) == (Decimal(1), Decimal("0.1"))


def test_직전_50일_거래량이_없으면_찾지_않음() -> None:
    assert gap_ups(with_event("150", "150", "1000", before=VOLUME_BARS - 1)) == []
