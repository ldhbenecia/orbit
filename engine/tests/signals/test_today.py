from datetime import UTC, datetime, timedelta
from decimal import Decimal

from orbit.marketdata.upbit_ticker import Ticker, parse_ticker
from orbit.signals.today import Stance, today_signal, today_signals
from tests.backtest.test_engine import candles

D0 = datetime(2024, 1, 1, tzinfo=UTC)


def _ticker(day: datetime, open_: int, high: int) -> Ticker:
    return Ticker(day=day, open=Decimal(open_), high=Decimal(high), price=Decimal(open_))


def test_이동평균_위면_보유_구간과_며칠째인지() -> None:
    # 3일선: 종가 10·10·10 다음 20·30·40 → 4일째부터 선 위
    history = candles([(10, 10)] * 3 + [(20, 20), (30, 30), (40, 40)])

    signal = today_signal("ma-3", history, None)

    assert signal.stance is Stance.HOLD
    assert signal.days == 3
    assert "평균보다 높아서 보유" in signal.reason
    assert signal.reference == Decimal(30)  # 최근 3일 평균 (20+30+40)/3


def test_이동평균_아래면_현금_구간() -> None:
    signal = today_signal("ma-3", candles([(40, 40), (30, 30), (20, 20), (10, 10)]), None)

    assert signal.stance is Stance.CASH


def test_변동성_돌파_기준선은_오늘_시가에_전날_변동폭_k배를_더함() -> None:
    history = candles([(100, 100), (100, 120)])  # 마지막 봉 고가 120 · 저가 100 → 변동폭 20
    today = history[-1].start + timedelta(days=1)

    waiting = today_signal("vb-0.5", history, _ticker(today, 130, 135))
    hit = today_signal("vb-0.5", history, _ticker(today, 130, 140))

    assert waiting.trigger == Decimal(140)
    assert waiting.stance is Stance.BREAKOUT_WAIT
    assert hit.stance is Stance.BREAKOUT_HIT


def test_시세가_다음_날_것이_아니면_돌파_여부를_계산하지_않음() -> None:
    history = candles([(100, 100), (100, 120)])
    stale = history[-1].start  # 마지막 확정 봉과 같은 날 — 동기화가 하루 밀린 상황

    signal = today_signal("vb-0.5", history, _ticker(stale, 130, 999))

    assert (signal.stance, signal.trigger) == (Stance.BREAKOUT_WAIT, None)


def test_업비트_ticker_를_Decimal_과_UTC_날짜로_파싱() -> None:
    payload = (
        '[{"trade_date": "20261004", "opening_price": 115216000.0,'
        ' "high_price": 115708000.0, "trade_price": 115600000.0}]'
    )

    ticker = parse_ticker(payload)

    assert ticker.day == datetime(2026, 10, 4, tzinfo=UTC)
    assert ticker.open == Decimal("115216000.0")


def test_기준선은_호가_단위로_올림() -> None:
    history = candles([(100_000_000, 100_000_000), (100_000_000, 100_663_000)])  # 변동폭 663,000
    today = history[-1].start + timedelta(days=1)

    signal = today_signal("vb-0.5", history, _ticker(today, 115_216_000, 0))

    assert signal.trigger == Decimal(115_548_000)  # 115,216,000 + 331,500 → 1,000원 호가로 올림


def test_주식은_이동평균_규칙만() -> None:
    history = candles([(10, 10)] * 3 + [(20, 20)])

    specs = [s.strategy for s in today_signals("US-QQQ", history, None)]

    assert specs == ["ma-60", "ma-120", "ma-200"]
