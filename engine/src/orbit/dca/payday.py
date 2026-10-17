from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from enum import StrEnum
from typing import Literal

from orbit.dca.plan import payday_indices
from orbit.marketdata.candle import Candle
from orbit.strategies.registry import build_strategy

# 월급날 규칙 — 숫자는 결과를 보고 고르지 않은 고정값 (고르면 과거에 맞춘 규칙이 됨)
DIP = Decimal("-0.2")  # 52주 최고 종가 대비 −20% 이하면 "떨어짐"
YEAR_BARS = 252  # 주식 1년 거래일 — 52주 고점과 200일 평균을 셀 수 있게 이만큼 지난 뒤부터 비교
TREND_RULE = "ma-200"  # 대시보드 신호와 같은 규칙 함수
WINDOW_MONTHS = 60  # 5년씩 잘라 본 구간


class Spend(StrEnum):
    ALL = "all"  # 모아 둔 돈까지 전부
    HALF_SALARY = "half_salary"  # 이번 달 월급의 절반만, 나머지는 모아 둠
    NONE = "none"  # 이번 달은 안 사고 모아 둠


@dataclass(frozen=True, slots=True)
class Choice:
    spend: Spend
    reason: str


# 월급날 전날까지의 확정 봉만 받음 — 월급날 종가로 판단하고 그 종가에 사면 미래 데이터
PaydayRule = Callable[[Sequence[Candle]], Choice]


def plain(history: Sequence[Candle]) -> Choice:
    return Choice(Spend.ALL, "매달 들어온 돈을 전부 삼")


def buy_the_dip(history: Sequence[Candle]) -> Choice:
    high = max(c.close for c in history[-YEAR_BARS:])
    gap = history[-1].close / high - 1
    line = f"52주 고점 대비 {gap * 100:.1f}%"
    if gap <= DIP:
        return Choice(Spend.ALL, f"{line} — 모아 둔 돈까지 전부")
    return Choice(Spend.HALF_SALARY, f"{line} — 월급 절반만, 절반은 모아 둠")


_trend, _ = build_strategy(TREND_RULE)


def wait_for_trend(history: Sequence[Candle]) -> Choice:
    decision = _trend(history)
    if decision.reference is None:  # 200거래일이 안 됨 — 신호처럼 현금 쪽
        return Choice(Spend.NONE, f"{decision.reason} — 이번 달은 모아 둠")
    line = f"200거래일 평균 대비 {(history[-1].close / decision.reference - 1) * 100:+.1f}%"
    if decision.target_weight > 0:
        return Choice(Spend.ALL, f"{line} — 평균 위라 모아 둔 돈까지 전부")
    return Choice(Spend.NONE, f"{line} — 평균 아래라 이번 달은 모아 둠")


RuleName = Literal["plain", "dip", "trend"]
RULES: dict[RuleName, PaydayRule] = {"plain": plain, "dip": buy_the_dip, "trend": wait_for_trend}


@dataclass(frozen=True, slots=True)
class PaydayResult:
    invested: Decimal  # 넣은 월급 합계
    final_value: Decimal  # 마지막 종가 평가액 + 남은 현금
    cash: Decimal  # 아직 안 쓴 돈 (이자 없음)
    qty: int
    buys: int  # 실제로 산 달 수
    fees: Decimal
    worst_vs_invested: Decimal  # 넣은 돈 대비 가장 나빴던 순간 (0 이하)


Fee = Callable[[Decimal], Decimal]


def run_payday(
    candles: Sequence[Candle],
    paydays: Sequence[int],
    choices: dict[int, Spend],
    monthly: Decimal,
    fee: Fee,
) -> PaydayResult:
    # paydays 첫 날부터 candles 끝까지 — 판단(choices)은 미리 계산해 여러 구간에서 같이 씀
    cash = invested = fees = Decimal(0)
    qty = buys = 0
    worst = Decimal(0)
    pay = set(paydays)
    first = paydays[0] if paydays else len(candles)
    for i in range(first, len(candles)):
        close = candles[i].close
        if i in pay:
            cash += monthly
            invested += monthly
            spend = choices[i]
            if spend is Spend.ALL:
                budget = cash
            elif spend is Spend.HALF_SALARY:
                budget = min(cash, monthly / 2)
            else:
                budget = Decimal(0)
            # 수수료까지 예산 안에서 — 1주 단위로 내림, 넘치면 한 주씩 줄임
            n = int((budget / close).to_integral_value(ROUND_DOWN))
            while n > 0 and close * n + fee(close * n) > budget:
                n -= 1
            if n > 0:
                cost = close * n
                paid = fee(cost)
                cash -= cost + paid
                fees += paid
                qty += n
                buys += 1
        if invested:
            worst = min(worst, (cash + close * qty) / invested - 1)
    end = candles[-1].close if candles else Decimal(0)
    return PaydayResult(invested, cash + end * qty, cash, qty, buys, fees, worst)


@dataclass(frozen=True, slots=True)
class Comparison:
    start: datetime  # 비교한 첫 월급날
    full: dict[RuleName, PaydayResult]  # 비교 가능한 전 기간
    windows: int  # 5년씩 잘라 본 구간 수 (매달 시작)
    beat_plain: dict[RuleName, Decimal]  # 구간 중 단순 적립보다 평가액이 컸던 비율 (plain 제외)
    latest: dict[RuleName, Choice]  # 다음 월급날에 각 규칙이 할 일 — 마지막 확정 봉 기준


def decide(candles: Sequence[Candle], paydays: Sequence[int]) -> dict[RuleName, dict[int, Spend]]:
    # 월급날 i 의 판단은 i 전날까지의 봉으로만
    return {name: {i: rule(candles[:i]).spend for i in paydays} for name, rule in RULES.items()}


def compare(candles: Sequence[Candle], monthly: Decimal, fee: Fee) -> Comparison | None:
    # 52주 고점·200일 평균을 셀 수 있는 날부터 — 앞쪽은 규칙끼리 조건이 달라 비교에서 뺌
    paydays = [i for i in payday_indices(candles) if i >= YEAR_BARS]
    if not paydays:
        return None
    choices = {name: {i: rule(candles[:i]).spend for i in paydays} for name, rule in RULES.items()}
    full = {name: run_payday(candles, paydays, c, monthly, fee) for name, c in choices.items()}
    wins: dict[RuleName, int] = {name: 0 for name in RULES if name != "plain"}
    windows = 0
    for start in range(len(paydays) - WINDOW_MONTHS):
        span = paydays[start : start + WINDOW_MONTHS]
        # 구간 끝 = 다음 구간 첫 월급날 전날 — 5년 동안 넣고 그 시점에 평가
        window = candles[: paydays[start + WINDOW_MONTHS]]
        results = {name: run_payday(window, span, c, monthly, fee) for name, c in choices.items()}
        windows += 1
        for name in wins:
            if results[name].final_value > results["plain"].final_value:
                wins[name] += 1
    return Comparison(
        start=candles[paydays[0]].start,
        full=full,
        windows=windows,
        beat_plain={n: Decimal(w) / windows for n, w in wins.items()} if windows else {},
        latest={name: rule(candles) for name, rule in RULES.items()},
    )
