from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from orbit.backtest.engine import BacktestResult

# 워크포워드 — 지난 3년으로 값을 고르고 다음 1년 써 보기를 해마다 굴림 (López de Prado 2018)
# 한 번 반으로 나누는 검증보다 "고르는 방식" 자체가 통하는지를 여러 번 봄
TRAIN = timedelta(days=3 * 365)
TEST = timedelta(days=365)


@dataclass(frozen=True, slots=True)
class Pick:
    start: datetime  # 써 본 첫날
    end: datetime  # 써 본 마지막 날
    spec: str  # 직전 3년 수익이 가장 컸던 값


@dataclass(frozen=True, slots=True)
class Walk:
    picks: list[Pick]
    navs: list[tuple[datetime, Decimal]]  # 고른 값을 이어 쓴 기준가 — 첫 줄은 시작 전날 1
    trades: int  # 고른 값이 그 기간에 실제로 한 매매 수


def walk_forward(
    results: Mapping[str, BacktestResult], specs: Sequence[str], start: datetime, end: datetime
) -> Walk | None:
    # 판단은 그 시점까지의 기준가만 — 다음 1년 성과는 고를 때 보지 않음
    days = [r.day for r in results[specs[0]].records]
    navs = {s: [r.nav for r in results[s].records] for s in specs}
    picks: list[Pick] = []
    chain: list[tuple[datetime, Decimal]] = []
    trades = 0
    level = Decimal(1)
    t = start + TRAIN
    while t <= end:
        train = [i for i, d in enumerate(days) if t - TRAIN <= d < t]
        test = [i for i, d in enumerate(days) if t <= d < t + TEST and d <= end]
        if len(train) < 2 or not test:
            break
        first, last = train[0], train[-1]
        # 같으면 앞쪽(목록 순서) 값 — 결과를 보고 순서를 바꾸지 않음
        spec = max(specs, key=lambda s: (navs[s][last] / navs[s][first], -specs.index(s)))
        if not chain:
            chain.append((days[test[0] - 1], level))
        for i in test:
            level *= navs[spec][i] / navs[spec][i - 1]
            chain.append((days[i], level))
        lo, hi = days[test[0]], days[test[-1]]
        trades += sum(1 for tr in results[spec].trades if lo <= tr.day <= hi)
        picks.append(Pick(lo, hi, spec))
        t += TEST
    return Walk(picks, chain, trades) if picks else None
