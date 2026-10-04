from collections.abc import Sequence
from decimal import Decimal

from orbit.backtest.configs import US_STOCK_CONFIG
from orbit.backtest.engine import Funding, run_backtest
from orbit.marketdata.candle import Candle
from orbit.marketdata.toss_rules import us_fee
from orbit.strategies.base import Decision
from tests.backtest.test_engine import candles

USD_1000 = Funding(initial=Decimal(1000), monthly=Decimal(0))


def test_미국주식은_1주_단위로_사고_가격은_센트_호가로_올림() -> None:
    # 시가 300 × 슬리피지 1.0005 = 300.15 → 1000 달러로 수수료 포함 3주
    result = run_backtest(candles([(300, 300), (300, 300)]), _always, USD_1000, US_STOCK_CONFIG)

    buy = result.trades[0]
    assert (buy.qty, buy.price) == (Decimal(3), Decimal("300.15"))
    assert buy.fee == Decimal("0.90")  # 900.45 × 0.1% = 0.90045 → 센트 미만 절사


def test_매도에는_SEC_fee_가_붙고_최소_1센트() -> None:
    assert us_fee(Decimal("900"), "buy") == Decimal("0.90")
    # 0.1% 0.90 + SEC 900 × 0.00206% = 0.0185 → 0.02
    assert us_fee(Decimal("900"), "sell") == Decimal("0.92")
    # 작은 매도도 SEC fee 최소 0.01
    assert us_fee(Decimal("10"), "sell") == Decimal("0.02")


def test_1주도_못_사는_금액이면_거래하지_않음() -> None:
    small = Funding(initial=Decimal(200), monthly=Decimal(0))

    result = run_backtest(candles([(300, 300), (300, 300)]), _always, small, US_STOCK_CONFIG)

    assert result.trades == []


def _always(history: Sequence[Candle]) -> Decision:
    return Decision(Decimal(1), "")
