import math
from collections.abc import Sequence
from statistics import NormalDist

# 검증용 통계 — 분석 산출물이라 float (금액 계산·주문에는 쓰지 않음)
EULER_GAMMA = 0.5772156649015329
_NORMAL = NormalDist()


def moments(returns: Sequence[float]) -> tuple[float, float, float, float]:
    # 평균, 표본 표준편차, 치우침(skewness), 뾰족함(kurtosis, 정규분포 = 3)
    n = len(returns)
    mean = sum(returns) / n
    dev = [r - mean for r in returns]
    var = sum(d * d for d in dev) / (n - 1) if n > 1 else 0.0
    std = math.sqrt(var)
    if std == 0:
        return mean, 0.0, 0.0, 3.0
    m2 = sum(d * d for d in dev) / n
    skew = (sum(d**3 for d in dev) / n) / m2**1.5
    kurt = (sum(d**4 for d in dev) / n) / m2**2
    return mean, std, skew, kurt


def sharpe(returns: Sequence[float]) -> float:
    # 봉 하나당 — 연환산은 × √(1년 봉 수). 무위험 수익률은 0 으로 봄
    mean, std, _, _ = moments(returns)
    return mean / std if std else 0.0


def deflated_sharpe(
    sr: float,
    n_obs: int,
    skew: float,
    kurt: float,
    trials: int,
    sr_variance: float,
    benchmark: float = 0.0,
) -> float:
    # Bailey·López de Prado (2014) — 여러 개를 시험해 고른 샤프가 기준보다 높은 게 우연이 아닐 확률
    # sr·benchmark 는 봉 하나당, sr_variance 는 시험한 규칙들의 샤프 분산, 시험 1개면 PSR
    if trials > 1:
        expected_max = math.sqrt(sr_variance) * (
            (1 - EULER_GAMMA) * _NORMAL.inv_cdf(1 - 1 / trials)
            + EULER_GAMMA * _NORMAL.inv_cdf(1 - 1 / (trials * math.e))
        )
    else:
        expected_max = 0.0
    # 수익 분포가 치우치거나 꼬리가 두꺼우면 샤프 추정이 더 흔들림
    spread = 1 - skew * sr + (kurt - 1) / 4 * sr * sr
    if spread <= 0 or n_obs < 2:
        return 0.0
    threshold = benchmark + expected_max
    return _NORMAL.cdf((sr - threshold) * math.sqrt(n_obs - 1) / math.sqrt(spread))
