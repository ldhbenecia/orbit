from decimal import Decimal

from orbit.backtest.engine import DEFAULT_CONFIG, BacktestConfig
from orbit.marketdata.toss_rules import US_FEE_RATE, round_to_cent, us_fee

# 토스증권 미국주식 — 1주 단위 (Open API 소수점 주문 지원은 미확인이라 보수적으로)
US_STOCK_CONFIG = BacktestConfig(
    fee_rate=US_FEE_RATE,
    # 거래소 공식 값이 아닌 가정 — QQQ·SPY 호가 차이(1센트 ≈ 0.002%)보다 넉넉하게
    slippage_rate=Decimal("0.0005"),
    min_order=Decimal(1),
    qty_step=Decimal(1),
    round_price=round_to_cent,
    fee=us_fee,
)


def config_for(market: str) -> BacktestConfig:
    # 국내 ETF 는 호가 단위를 공식 확인하기 전이라 백테스트하지 않음
    if market.startswith("KRW-"):
        return DEFAULT_CONFIG
    if market.startswith("US-"):
        return US_STOCK_CONFIG
    raise ValueError(f"백테스트 비용 규칙이 없는 종목: {market}")
