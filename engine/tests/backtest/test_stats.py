import random

import pytest

from orbit.backtest.stats import deflated_sharpe, moments, sharpe


def test_샤프_비율은_평균을_표준편차로_나눈_값() -> None:
    assert sharpe([0.01, 0.03, 0.01, 0.03]) == pytest.approx(0.02 / 0.011547, rel=1e-4)
    assert sharpe([0.01, 0.01]) == 0.0  # 출렁임이 없으면 정의 안 됨 — 0 으로


def test_정규분포면_치우침_0_뾰족함_3_근처() -> None:
    rng = random.Random(1)
    _, _, skew, kurt = moments([rng.gauss(0, 1) for _ in range(20000)])

    assert skew == pytest.approx(0, abs=0.05)
    assert kurt == pytest.approx(3, abs=0.1)


def test_시험을_많이_할수록_우연이_아닐_확률이_낮아짐() -> None:
    args = {"sr": 0.05, "n_obs": 2000, "skew": 0.0, "kurt": 3.0, "sr_variance": 0.0004}

    one = deflated_sharpe(trials=1, **args)
    many = deflated_sharpe(trials=50, **args)

    assert 0.9 < one < 1  # 하나만 시험했다면 충분히 우연이 아님
    assert many < one


def test_샤프가_0_이면_한_번만_시험해도_반반() -> None:
    assert deflated_sharpe(0.0, 1000, 0.0, 3.0, trials=1, sr_variance=0.0) == pytest.approx(0.5)


def test_두꺼운_꼬리면_확률이_낮아짐() -> None:
    normal = deflated_sharpe(0.05, 500, 0.0, 3.0, trials=1, sr_variance=0.0)
    fat = deflated_sharpe(0.05, 500, -1.0, 10.0, trials=1, sr_variance=0.0)

    assert fat < normal


def test_기준_샤프보다_높아야_확률이_올라감() -> None:
    base = deflated_sharpe(0.05, 2000, 0.0, 3.0, trials=1, sr_variance=0.0)
    vs_hold = deflated_sharpe(0.05, 2000, 0.0, 3.0, trials=1, sr_variance=0.0, benchmark=0.05)

    assert vs_hold == pytest.approx(0.5)  # 보유와 같은 샤프면 반반
    assert base > vs_hold
