import math
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from orbit.backtest.configs import config_for
from orbit.backtest.engine import BacktestResult, Funding, run_backtest
from orbit.backtest.metrics import DAYS_PER_YEAR
from orbit.backtest.stats import deflated_sharpe, moments, sharpe
from orbit.db.migrations import migrate
from orbit.marketdata.candle import Candle
from orbit.strategies.registry import build_strategy
from orbit.units import from_units, round_to_units

# 파라미터 민감도 — 좋은 값 하나만이 아니라 주변 값도 비슷해야 우연이 아님
MA_WINDOWS = (40, 60, 80, 100, 120, 140, 160, 200, 240)
VB_KS = ("0.3", "0.4", "0.5", "0.6", "0.7")
# 약 3·6·9·12개월 — 코인은 달력 일, 주식은 거래일
MOM_LOOKBACKS = {"coin": (91, 182, 273, 365), "stock": (63, 126, 189, 252)}
PPM = 6

Period = Literal["all", "first", "second"]
Span = tuple[datetime, datetime]


@dataclass(frozen=True, slots=True)
class RuleCheck:
    strategy: str
    period: Period
    start: datetime
    end: datetime
    cagr: Decimal
    mdd: Decimal
    trades: int
    fee_ratio: Decimal  # 기간 수수료·슬리피지 ÷ 기간 시작 평가액
    sharpe: Decimal = Decimal(0)  # 연환산 샤프 비율 — 출렁인 만큼 대비 수익 (무위험 수익률 0)
    # 전체 기간만 — 시험 횟수·수익 분포를 감안해도 샤프가 단순 보유보다 높은 게 우연이 아닐 확률
    edge_prob: Decimal | None = None


def specs_for(market: str) -> list[str]:
    coin = market.startswith("KRW-")
    specs = ["hold", *(f"ma-{w}" for w in MA_WINDOWS)]
    specs += [f"mom-{n}" for n in MOM_LOOKBACKS["coin" if coin else "stock"]]
    # 주식 변동성 돌파는 장중 시가·호가 단위가 필요해 아직 제외 (신호와 같음)
    if coin:
        specs += [f"vb-{k}" for k in VB_KS]
    return specs


def warmup_for(specs: Sequence[str]) -> int:
    # 모든 규칙이 판단할 수 있는 날부터 평가 — 규칙마다 출발점이 다르면 불공정
    # 이동평균 N 은 N 봉, 모멘텀 N 은 N 봉 전 종가가 있어야 함
    need = [0]
    for spec in specs:
        name, _, arg = spec.partition("-")
        if name == "ma":
            need.append(int(arg))
        elif name == "mom":
            need.append(int(arg) + 1)
    return max(need)


def periods(candles: Sequence[Candle], warmup: int) -> tuple[Span, Span, Span]:
    # 평가 구간을 날짜로 반씩 — 앞에서 고른 규칙이 뒤에서도 통하는지 보려는 것
    days = [c.start for c in candles[warmup + 1 :]]
    middle = days[len(days) // 2]
    first_end = max(d for d in days if d < middle)
    return (days[0], days[-1]), (days[0], first_end), (middle, days[-1])


def check_rules(
    market: str,
    candles: Sequence[Candle],
    specs: Sequence[str],
    warmup: int | None = None,
) -> list[RuleCheck]:
    # 전 기간을 한 번 돌리고 기준가 기록을 기간별로 자름
    # 뒤 기간만 잘라 돌리면 이동평균이 처음 N일 동안 판단을 못 해 불리해짐
    whole, first, second = periods(candles, warmup_for(specs) if warmup is None else warmup)
    spans: list[tuple[Period, Span]] = [("all", whole), ("first", first), ("second", second)]
    funding = Funding(initial=_initial(market), monthly=Decimal(0))
    per_year = 365 if market.startswith("KRW-") else 252
    results = {}
    for spec in specs:
        strategy, _ = build_strategy(spec)
        results[spec] = run_backtest(candles, strategy, funding, config_for(market))
    rows = [
        _slice(spec, period, span, result, per_year)
        for spec, result in results.items()
        for period, span in spans
    ]
    return _with_edge(rows, results, whole) if "hold" in results else rows


def _daily_returns(result: BacktestResult, span: Span) -> list[float]:
    start, end = span
    navs = [r.nav for r in result.records]
    days = [r.day for r in result.records]
    first = next(i for i, d in enumerate(days) if d >= start)
    out = []
    for i in range(first, len(days)):
        if days[i] > end:
            break
        out.append(float(navs[i] / navs[i - 1] - 1))
    return out


def _with_edge(
    rows: list[RuleCheck], results: dict[str, BacktestResult], whole: Span
) -> list[RuleCheck]:
    # 규칙의 샤프가 단순 보유보다 높은 게 우연이 아닐 확률 — 이 종목에서 시험한 규칙 수로 보정
    # 일별 수익의 단순 차이로 보면 덜 출렁여 복리가 덜 깎이는 효과를 놓쳐 위험을 줄이는 규칙에 불리
    returns = {spec: _daily_returns(result, whole) for spec, result in results.items()}
    benchmark = sharpe(returns["hold"])
    srs = {spec: sharpe(series) for spec, series in returns.items() if spec != "hold"}
    if not srs:
        return rows
    mean_sr = sum(srs.values()) / len(srs)
    variance = sum((v - mean_sr) ** 2 for v in srs.values()) / max(len(srs) - 1, 1)
    probs = {}
    for spec, sr in srs.items():
        _, _, skew, kurt = moments(returns[spec])
        probs[spec] = deflated_sharpe(
            sr, len(returns[spec]), skew, kurt, len(srs), variance, benchmark
        )
    return [
        replace(r, edge_prob=Decimal(str(round(probs[r.strategy], 6))))
        if r.period == "all" and r.strategy in probs
        else r
        for r in rows
    ]


def _initial(market: str) -> Decimal:
    # 비율만 보므로 금액은 1주·최소 주문을 넉넉히 넘기는 예시값
    return Decimal(10_000) if market.startswith("US-") else Decimal(10_000_000)


def _slice(
    spec: str, period: Period, span: Span, result: BacktestResult, per_year: int
) -> RuleCheck:
    start, end = span
    records = result.records
    # 기간 첫날 시가에 이미 체결되므로 기준은 그 전날 종가 기준가
    base_index = next(i for i, r in enumerate(records) if r.day >= start) - 1
    base = records[base_index]
    inside = [r for r in records if start <= r.day <= end]
    peak = base.nav
    mdd = Decimal(0)
    for r in inside:
        peak = max(peak, r.nav)
        mdd = min(mdd, r.nav / peak - 1)
    years = Decimal((inside[-1].day - base.day).days) / DAYS_PER_YEAR
    growth = inside[-1].nav / base.nav
    trades = [t for t in result.trades if start <= t.day <= end]
    costs = sum((t.fee + t.slippage_cost for t in trades), Decimal(0))
    return RuleCheck(
        strategy=spec,
        period=period,
        start=start,
        end=end,
        cagr=growth ** (1 / years) - 1 if years > 0 else Decimal(0),
        mdd=mdd,
        trades=len(trades),
        fee_ratio=costs / base.equity if base.equity else Decimal(0),
        sharpe=Decimal(str(round(sharpe(_daily_returns(result, span)) * math.sqrt(per_year), 6))),
    )


def save_checks(
    conn: sqlite3.Connection,
    market: str,
    rows: Sequence[RuleCheck],
    created_at: datetime,
    code_version: str,
) -> None:
    migrate(conn)
    with conn:
        conn.executemany(
            """
            INSERT INTO rule_checks (
                market, created_ts, strategy, period, code_version, start_ts, end_ts,
                cagr_ppm, mdd_ppm, trades, fee_ppm, sharpe_ppm, edge_ppm
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    market,
                    int(created_at.timestamp()),
                    r.strategy,
                    r.period,
                    code_version,
                    int(r.start.timestamp()),
                    int(r.end.timestamp()),
                    round_to_units(r.cagr, PPM),
                    round_to_units(r.mdd, PPM),
                    r.trades,
                    round_to_units(r.fee_ratio, PPM),
                    round_to_units(r.sharpe, PPM),
                    None if r.edge_prob is None else round_to_units(r.edge_prob, PPM),
                )
                for r in rows
            ],
        )


@dataclass(frozen=True, slots=True)
class SavedChecks:
    created_at: datetime
    code_version: str
    rows: list[RuleCheck]


def latest_checks(conn: sqlite3.Connection, market: str) -> SavedChecks | None:
    # 가장 최근에 한 번 검증한 묶음 전체 — 묶음끼리 섞으면 코드 버전·기간이 달라짐
    migrate(conn)
    found = conn.execute(
        "SELECT MAX(created_ts) FROM rule_checks WHERE market = ?", (market,)
    ).fetchone()[0]
    if found is None:
        return None
    rows = conn.execute(
        """
        SELECT strategy, period, code_version, start_ts, end_ts, cagr_ppm, mdd_ppm, trades, fee_ppm,
            sharpe_ppm, edge_ppm
        FROM rule_checks WHERE market = ? AND created_ts = ?
        """,
        (market, found),
    ).fetchall()
    return SavedChecks(
        created_at=datetime.fromtimestamp(found, UTC),
        code_version=rows[0][2],
        rows=[
            RuleCheck(
                strategy=row[0],
                period=row[1],
                start=datetime.fromtimestamp(row[3], UTC),
                end=datetime.fromtimestamp(row[4], UTC),
                cagr=from_units(row[5], PPM),
                mdd=from_units(row[6], PPM),
                trades=row[7],
                fee_ratio=from_units(row[8], PPM),
                sharpe=from_units(row[9], PPM),
                edge_prob=None if row[10] is None else from_units(row[10], PPM),
            )
            for row in rows
        ],
    )
