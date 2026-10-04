from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from orbit.backtest.engine import BacktestConfig, Funding, run_backtest
from orbit.backtest.metrics import compute_metrics
from orbit.marketdata.candle import Candle
from orbit.strategies.base import Decision
from orbit.strategies.hold import always_hold

D0 = datetime(2024, 1, 1, tzinfo=UTC)
FREE = BacktestConfig(fee_rate=Decimal(0), slippage_rate=Decimal(0), min_order=Decimal(5000))
LUMP = Funding(initial=Decimal(1_000_000), monthly=Decimal(0))


def candles(prices: list[tuple[int, int]], start: datetime = D0) -> list[Candle]:
    out = []
    for i, (o, c) in enumerate(prices):
        op, cl = Decimal(o), Decimal(c)
        out.append(
            Candle(
                "KRW-BTC", start + timedelta(days=i), op, max(op, cl), min(op, cl), cl, Decimal(1)
            )
        )
    return out


def test_판단은_전날까지_확정_봉으로_체결은_다음_날_시가() -> None:
    seen: list[int] = []

    def spy(history: Sequence[Candle]) -> Decision:
        seen.append(len(history))
        return always_hold(history)

    result = run_backtest(candles([(100, 100), (200, 210), (300, 300)]), spy, LUMP, FREE)

    assert seen == [1, 2]
    first = result.trades[0]
    assert (first.day, first.price, first.qty) == (
        D0 + timedelta(days=1),
        Decimal(200),
        Decimal(5000),
    )


def test_미래_봉을_바꿔도_과거_판단과_거래는_그대로() -> None:
    def momentum(history: Sequence[Candle]) -> Decision:
        up = len(history) > 1 and history[-1].close > history[-2].close
        return Decision(Decimal(1) if up else Decimal(0), "상승" if up else "하락")

    base = [(100, 100), (100, 110), (110, 120), (120, 100), (100, 90), (90, 95)]
    changed = base[:4] + [(500, 900), (900, 10)]

    a = run_backtest(candles(base), momentum, LUMP, FREE)
    b = run_backtest(candles(changed), momentum, LUMP, FREE)

    cutoff = D0 + timedelta(days=3)
    assert [t for t in a.trades if t.day <= cutoff] == [t for t in b.trades if t.day <= cutoff]
    assert a.records[:3] == b.records[:3]


def test_적립식은_매달_첫_거래일에_입금() -> None:
    start = datetime(2024, 1, 30, tzinfo=UTC)
    prices = [(100, 100)] * 33  # 1/30 ~ 3/2
    funding = Funding(initial=Decimal(0), monthly=Decimal(100_000))

    result = run_backtest(candles(prices, start), always_hold, funding, FREE)

    deposit_days = [r.day.date().isoformat() for r in result.records if r.deposit]
    assert deposit_days == ["2024-01-31", "2024-02-01", "2024-03-01"]
    assert result.records[-1].invested == Decimal(300_000)


def test_수수료를_내도_현금이_음수가_되지_않음() -> None:
    config = BacktestConfig(fee_rate=Decimal("0.0005"), slippage_rate=Decimal("0.0005"))

    result = run_backtest(candles([(100, 100), (137, 141), (141, 150)]), always_hold, LUMP, config)

    trade = result.trades[0]
    assert trade.price == Decimal(138)  # 137 × 1.0005 = 137.0685 → 1원 호가로 올림
    assert trade.fee > 0
    assert all(r.cash >= 0 for r in result.records)
    assert result.records[-1].cash < config.min_order


def test_최소_주문_금액_미만이면_거래하지_않음() -> None:
    tiny = Funding(initial=Decimal(3000), monthly=Decimal(0))

    result = run_backtest(candles([(100, 100), (100, 100)]), always_hold, tiny, FREE)

    assert result.trades == []


def test_목표_비중이_0이면_보유분을_매도() -> None:
    def exit_after_first(history: Sequence[Candle]) -> Decision:
        return Decision(Decimal(1) if len(history) == 1 else Decimal(0), "")

    result = run_backtest(
        candles([(100, 100), (100, 100), (200, 200)]), exit_after_first, LUMP, FREE
    )

    assert [t.side for t in result.trades] == ["buy", "sell"]
    assert result.records[-1].qty == 0
    assert result.records[-1].cash == Decimal(2_000_000)


def test_입금은_기준가를_바꾸지_않음() -> None:
    start = datetime(2024, 1, 30, tzinfo=UTC)
    funding = Funding(initial=Decimal(0), monthly=Decimal(100_000))

    result = run_backtest(candles([(100, 100)] * 40, start), always_hold, funding, FREE)

    assert {r.nav for r in result.records} == {Decimal(1)}


def test_지표_손계산과_일치() -> None:
    # 기준가 1 → 0.5 → 1.5 → 1.2
    prices = [(100, 100), (100, 100), (100, 50), (50, 150), (150, 120)]

    m = compute_metrics(run_backtest(candles(prices), always_hold, LUMP, FREE))

    assert m.invested == Decimal(1_000_000)
    assert m.final_equity == Decimal(1_200_000)
    assert m.return_on_invested == Decimal("0.2")
    assert m.mdd == Decimal("-0.5")
    assert m.worst_vs_invested == Decimal("-0.5")
    assert m.longest_underwater_days == 1
    assert m.trades == 1
