from dataclasses import dataclass
from datetime import date, timedelta
from fractions import Fraction

from orbit.fundamentals.edgar import Fact, Facts

YEAR = 365
# 회계연도를 52·53주로 끊는 회사가 있어 기간 끝이 해마다 며칠씩 밀림
SLACK = timedelta(days=10)
ANNUAL_MIN_DAYS = 350
# 표지 주식 수가 가중평균 주식 수에서 이만큼 벗어나면 믿지 않음
# 주식 종류마다 1주의 가치가 다른 회사 등
SHARES_TOLERANCE = (Fraction(4, 5), Fraction(5, 4))
SPLIT_MIN_RATIO = Fraction(19, 10)  # 보고서 사이 주식 수가 이 배 이상 정수배로 바뀌면 액면분할로 봄
SPLIT_INTEGER_SLACK = Fraction(3, 100)


@dataclass(frozen=True, slots=True)
class Snapshot:
    filed: date  # 공시일 — 이 날 이후 가격과 맞춰 씀
    period_end: date  # 보고서의 분기·연도 끝
    net_income: int | None  # 최근 4분기 합 (TTM)
    revenue: int | None  # 최근 4분기 합
    revenue_prev: int | None  # 1년 전 시점의 최근 4분기 합 — 매출 성장률
    operating_cf: int | None  # 영업활동 현금흐름, 최근 4분기 합
    capex: int | None  # 설비투자, 최근 4분기 합
    equity: int | None  # 기말 자본총계
    shares: int | None  # 발행주식 수 — 이후 액면분할 반영, 교차 확인을 못 하면 없음


def _days(fact: Fact) -> int:
    assert fact.start is not None
    return (fact.end - fact.start).days + 1


def _latest(facts: list[Fact]) -> Fact | None:
    # 같은 기간이 나중 보고서에서 정정되면 그 시점에 알던 가장 최근 값
    return max(facts, key=lambda f: f.filed, default=None)


def _near(a: date, b: date) -> bool:
    return abs(a - b) <= SLACK


def ttm(facts: list[Fact], end: date, known: date) -> int | None:
    # 분기 보고서는 연초부터 누적(YTD)으로 공시
    # 최근 4분기 = 직전 연간 + 올해 누적 − 작년 같은 기간 누적
    seen = [f for f in facts if f.filed <= known and f.start is not None]
    ending = [f for f in seen if f.end == end and _days(f) <= YEAR + 15]
    if not ending:
        return None
    longest = max(_days(f) for f in ending)
    ytd = _latest([f for f in ending if _days(f) == longest])
    assert ytd is not None and ytd.start is not None
    if longest >= ANNUAL_MIN_DAYS:
        return ytd.value
    annual = _latest(
        [f for f in seen if _days(f) >= ANNUAL_MIN_DAYS and _near(f.end, ytd.start - timedelta(1))]
    )
    prior = _latest(
        [
            f
            for f in seen
            if _near(f.end, end - timedelta(YEAR)) and abs(_days(f) - longest) <= SLACK.days
        ]
    )
    if annual is None or prior is None:
        return None
    return annual.value + ytd.value - prior.value


def instant(facts: list[Fact], end: date, known: date) -> int | None:
    found = _latest([f for f in facts if f.end == end and f.filed <= known])
    return found.value if found else None


def _cover_shares(facts: Facts, accn: str) -> int | None:
    # 표지 주식 수 — 주식 종류별로 나눠 적은 회사는 값이 여럿이라 믿지 않음, 0 으로 적은 것도 뺌
    cover = [f for f in facts.get("cover_shares", []) if f.accn == accn and f.value > 0]
    if not cover:
        return None
    last = max(f.end for f in cover)
    values = {f.value for f in cover if f.end == last}
    return values.pop() if len(values) == 1 else None


def _weighted_quarter(facts: Facts, accn: str, end: date) -> int | None:
    # 같은 보고서의 최근 분기 가중평균 주식 수 (회사 전체, 주식 종류 합)
    weighted = [f for f in facts.get("weighted_shares", []) if f.accn == accn and f.end == end]
    quarter = min(weighted, key=_days, default=None)
    return quarter.value if quarter and quarter.value > 0 else None


def _close(shares: int, weighted: int) -> bool:
    low, high = SHARES_TOLERANCE
    return low <= Fraction(shares, weighted) <= high


def _is_split(ratio: Fraction) -> bool:
    n = round(ratio)
    return ratio >= SPLIT_MIN_RATIO and abs(ratio - n) / ratio <= SPLIT_INTEGER_SLACK


def _split_ratio(newer: int, older: int) -> Fraction:
    ratio = Fraction(newer, older)
    if _is_split(ratio):
        return Fraction(round(ratio))
    if _is_split(1 / ratio):
        return Fraction(1, round(1 / ratio))
    return Fraction(1)


def split_factors(cover: list[tuple[date, int]]) -> dict[date, Fraction]:
    # 가격은 수정주가(분할 반영)라 옛 보고서 주식 수도 지금 기준으로 맞춰야 시가총액이 맞음
    # 교차 확인에 실패한 보고서의 주식 수도 분할 감지에는 씀 — 분할 직후 보고서가 그런 경우가 많음
    factors: dict[date, Fraction] = {}
    factor = Fraction(1)
    newer: int | None = None
    for filed, shares in sorted(cover, reverse=True):
        if newer is not None:
            factor *= _split_ratio(newer, shares)
        newer = shares
        factors[filed] = factor
    return factors


def snapshots(facts: Facts, *, weighted_fallback: bool) -> list[Snapshot]:
    # 보고서 하나 = 그 공시일에 시장이 알던 재무 상태 하나 (뒤에 나온 정정값을 섞지 않음)
    # weighted_fallback: 표지 주식 수가 없을 때 회사 전체 가중평균으로 대신 — 주식 종류마다
    # 1주의 가치가 같을 때만 맞음 (예: 표지를 종류별로만 적는 회사)
    income = facts.get("net_income", [])
    revenue = facts.get("revenue", [])
    reports: dict[date, tuple[str, date]] = {}
    for fact in income:
        if fact.start is None:
            continue
        current = reports.get(fact.filed)
        # 같은 날 공시가 둘이면 기간이 늦은 쪽
        if current is None or fact.end > current[1]:
            reports[fact.filed] = (fact.accn, fact.end)
    # 보고서별 (주식 수, 가격과 곱해도 되는지) — 맞지 않는 값도 분할 감지에는 씀
    shares_by: dict[date, tuple[int, bool]] = {}
    for filed, (accn, end) in reports.items():
        cover = _cover_shares(facts, accn)
        weighted = _weighted_quarter(facts, accn, end)
        if cover is not None:
            # 가중평균과 크게 다르면 가격과 곱할 수 없음
            shares_by[filed] = (cover, weighted is not None and _close(cover, weighted))
        elif weighted_fallback and weighted is not None:
            shares_by[filed] = (weighted, True)
    factors = split_factors([(filed, shares) for filed, (shares, _) in shares_by.items()])
    out = []
    for filed, (_, end) in sorted(reports.items()):
        found = shares_by.get(filed)
        out.append(
            Snapshot(
                filed=filed,
                period_end=end,
                net_income=ttm(income, end, filed),
                revenue=ttm(revenue, end, filed),
                revenue_prev=ttm(revenue, _prior_end(revenue, end, filed), filed),
                operating_cf=ttm(facts.get("operating_cf", []), end, filed),
                capex=ttm(facts.get("capex", []), end, filed),
                equity=instant(facts.get("equity", []), end, filed),
                shares=round(found[0] * factors[filed]) if found and found[1] else None,
            )
        )
    return out


def _prior_end(facts: list[Fact], end: date, known: date) -> date:
    # 1년 전 기간 끝 — 52·53주 회계연도라 정확히 365일 전이 아닐 수 있어 실제 공시된 날짜로
    target = end - timedelta(YEAR)
    ends = {f.end for f in facts if f.filed <= known and _near(f.end, target)}
    return min(ends, key=lambda d: abs(d - target), default=target)
