from dataclasses import dataclass
from decimal import Decimal

from orbit.backtest.engine import BacktestResult

DAYS_PER_YEAR = Decimal("365.25")


@dataclass(frozen=True, slots=True)
class Metrics:
    invested: Decimal  # 총 투입 원금
    final_equity: Decimal
    profit: Decimal
    return_on_invested: Decimal  # 손익 ÷ 총 투입
    worst_vs_invested: Decimal  # 넣은 돈 대비 가장 나빴던 순간 (음수면 원금 손실)
    cagr: Decimal  # 기준가 기준 연평균 복리 수익률 — 입금 효과 제외
    mdd: Decimal  # 기준가 기준 최대 낙폭 (음수)
    longest_underwater_days: int  # 기준가가 이전 고점을 회복하지 못한 최장 일수
    trades: int
    fees: Decimal
    slippage: Decimal


def compute_metrics(result: BacktestResult) -> Metrics:
    records = result.records
    last = records[-1]

    peak = records[0].nav
    mdd = Decimal(0)
    underwater = longest = 0
    worst = Decimal(0)
    for r in records:
        if r.nav >= peak:
            peak = r.nav
            underwater = 0
        else:
            underwater += 1
            longest = max(longest, underwater)
            mdd = min(mdd, r.nav / peak - 1)
        if r.invested:
            worst = min(worst, r.equity / r.invested - 1)

    years = Decimal((last.day - records[0].day).days) / DAYS_PER_YEAR
    cagr = last.nav ** (1 / years) - 1 if years > 0 else Decimal(0)

    return Metrics(
        invested=last.invested,
        final_equity=last.equity,
        profit=last.equity - last.invested,
        return_on_invested=last.equity / last.invested - 1,
        worst_vs_invested=worst,
        cagr=cagr,
        mdd=mdd,
        longest_underwater_days=longest,
        trades=len(result.trades),
        fees=sum((t.fee for t in result.trades), Decimal(0)),
        slippage=sum((t.slippage_cost for t in result.trades), Decimal(0)),
    )
