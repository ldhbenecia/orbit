from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import Decimal

from orbit.backtest.engine import Funding, run_backtest
from orbit.backtest.metrics import Metrics, compute_metrics
from orbit.marketdata.candle import Candle
from orbit.strategies.hold import always_hold


def month_starts(candles: Sequence[Candle]) -> int:
    # 판단 재료로만 쓰는 첫 봉을 뺀 기간에서 입금이 일어나는 날 수
    days = [c.start for c in candles[1:]]
    return sum(1 for i, d in enumerate(days) if i == 0 or d.month != days[i - 1].month)


def compare_lump_vs_dca(candles: Sequence[Candle], monthly: Decimal) -> dict[str, Metrics]:
    # 같은 총액으로 비교 — 적립식 총 투입액을 첫날 한 번에 넣은 것이 단순 보유
    total = monthly * month_starts(candles)
    return {
        "단순 보유 (일시 투입)": compute_metrics(
            run_backtest(candles, always_hold, Funding(initial=total, monthly=Decimal(0)))
        ),
        "적립식 (매달 투입)": compute_metrics(
            run_backtest(candles, always_hold, Funding(initial=Decimal(0), monthly=monthly))
        ),
    }


def select_period(candles: Sequence[Candle], start: datetime, end: datetime) -> list[Candle]:
    # 시작일 판단에 쓸 전날 봉 하나를 함께 포함
    return [c for c in candles if start - timedelta(days=1) <= c.start <= end]
