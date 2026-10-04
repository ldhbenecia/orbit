from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from orbit.backtest.engine import BacktestConfig, run_backtest
from orbit.marketdata.candle import Candle
from orbit.strategies.ma_filter import make_ma_filter
from orbit.strategies.registry import build_strategy
from orbit.strategies.vol_breakout import make_vol_breakout
from tests.backtest.test_engine import FREE, LUMP, candles

D0 = datetime(2024, 1, 1, tzinfo=UTC)
VB_HALF = make_vol_breakout(Decimal("0.5"))


def bar(day: int, o: int, h: int, low: int, c: int) -> Candle:
    return Candle(
        "KRW-BTC",
        D0 + timedelta(days=day),
        Decimal(o),
        Decimal(h),
        Decimal(low),
        Decimal(c),
        Decimal(1),
    )


def test_이동평균_데이터가_모자라면_현금() -> None:
    decision = make_ma_filter(3)(candles([(100, 100), (100, 110)]))

    assert decision.target_weight == 0
    assert "부족" in decision.reason


def test_이동평균_위면_보유_아래면_현금() -> None:
    ma3 = make_ma_filter(3)

    above = ma3(candles([(100, 100), (100, 100), (100, 130)]))  # 평균 110 < 130
    below = ma3(candles([(100, 130), (100, 130), (100, 100)]))  # 평균 120 > 100

    assert above.target_weight == 1
    assert "130원" in above.reason and "110원" in above.reason
    assert below.target_weight == 0


def test_변동성_돌파는_기준선에_닿은_날만_기준선_가격에_체결() -> None:
    # 전날 변동폭 100 × 0.5 = 50 → 기준선 = 오늘 시가 1000 + 50
    prev = bar(0, 1000, 1050, 950, 1000)

    traded = run_backtest([prev, bar(1, 1000, 1060, 990, 1040)], VB_HALF, LUMP, FREE)
    idle = run_backtest([prev, bar(1, 1000, 1049, 990, 1040)], VB_HALF, LUMP, FREE)

    assert [(t.side, t.price) for t in traded.trades] == [("buy", Decimal(1050))]
    assert idle.trades == []


def test_변동성_돌파_체결가에_슬리피지와_호가_올림() -> None:
    config = BacktestConfig(fee_rate=Decimal(0), slippage_rate=Decimal("0.0005"))
    prices = [
        bar(0, 1_000_000, 1_100_000, 1_000_000, 1_000_000),
        bar(1, 1_000_000, 1_200_000, 990_000, 1_100_000),
    ]

    result = run_backtest(prices, VB_HALF, LUMP, config)

    # 기준선 1,050,000 × 1.0005 = 1,050,525 → 1,000원 호가로 올림
    assert result.trades[0].price == Decimal(1_051_000)


def test_변동성_돌파로_산_물량은_다음_날_시가에_정리() -> None:
    prices = [
        bar(0, 100_000, 110_000, 90_000, 100_000),
        bar(1, 100_000, 120_000, 99_000, 115_000),
        bar(2, 130_000, 131_000, 120_000, 125_000),
    ]

    result = run_backtest(prices, VB_HALF, LUMP, FREE)

    assert [(t.side, t.day, t.price) for t in result.trades][:2] == [
        ("buy", prices[1].start, Decimal(110_000)),
        ("sell", prices[2].start, Decimal(130_000)),
    ]


@pytest.mark.parametrize("spec", ["ma-5", "vb-0.5"])
def test_미래_봉을_바꿔도_과거_거래는_그대로(spec: str) -> None:
    base = [bar(i, 100, 110 + i % 7 * 3, 95, 100 + i % 5 * 4) for i in range(40)]
    changed = base[:30] + [bar(i, 999, 1000, 1, 1) for i in range(30, 40)]
    strategy, _ = build_strategy(spec)

    a = run_backtest(base, strategy, LUMP, FREE)
    b = run_backtest(changed, strategy, LUMP, FREE)

    cutoff = D0 + timedelta(days=29)
    assert [t for t in a.trades if t.day <= cutoff] == [t for t in b.trades if t.day <= cutoff]
    assert any(t.day <= cutoff for t in a.trades)


@pytest.mark.parametrize(
    "spec", ["ma", "ma-0", "ma-x", "vb", "vb-0", "vb-2", "vb-abc", "hold-1", "rsi-14"]
)
def test_잘못된_전략_이름은_거부(spec: str) -> None:
    with pytest.raises(ValueError):
        build_strategy(spec)


def test_전략_이름에서_파라미터를_읽음() -> None:
    assert build_strategy("ma-120")[1] == {"window": "120"}
    assert build_strategy("vb-0.5")[1] == {"k": "0.5"}
    assert build_strategy("hold")[1] == {}
