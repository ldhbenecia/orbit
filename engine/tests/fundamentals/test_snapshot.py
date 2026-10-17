import pytest

from orbit.fundamentals.edgar import Fact, Facts
from orbit.fundamentals.snapshot import instant, snapshots, split_factors, ttm
from tests.fundamentals.facts import d


def fact(start: str | None, end: str, value: int, filed: str, accn: str = "x") -> Fact:
    return Fact(d(start) if start else None, d(end), value, d(filed), accn)


# 예시 회사 — 회계연도 = 달력 연도, 값은 전부 다르게 (뒤바뀜·누락이 드러나게)
K25 = "2026-02-10"  # 2025 연간 보고서
Q1 = "2026-05-05"
Q2 = "2026-08-05"
INCOME = [
    fact("2025-01-01", "2025-12-31", 1000, K25, "k25"),
    fact("2024-01-01", "2024-12-31", 800, K25, "k25"),
    fact("2026-01-01", "2026-03-31", 300, Q1, "q1"),
    fact("2025-01-01", "2025-03-31", 200, Q1, "q1"),
    fact("2026-04-01", "2026-06-30", 350, Q2, "q2"),  # 2분기 3개월
    fact("2026-01-01", "2026-06-30", 650, Q2, "q2"),  # 연초부터 누적
    fact("2025-04-01", "2025-06-30", 220, Q2, "q2"),
    fact("2025-01-01", "2025-06-30", 420, Q2, "q2"),
]


def test_연간_보고서면_그_해_값이_최근_4분기() -> None:
    assert ttm(INCOME, d("2025-12-31"), d(K25)) == 1000


@pytest.mark.parametrize(
    ("end", "known", "expected"),
    [
        ("2026-03-31", Q1, 1000 + 300 - 200),
        # 3개월 값(350·220)이 아니라 누적 값으로 — 1000 + 350 − 220 이면 틀림
        ("2026-06-30", Q2, 1000 + 650 - 420),
    ],
)
def test_분기는_직전_연간_더하기_올해_누적_빼기_작년_같은_기간(
    end: str, known: str, expected: int
) -> None:
    assert ttm(INCOME, d(end), d(known)) == expected


def test_나중에_정정된_값은_그_공시일_전에는_쓰지_않음() -> None:
    restated = [*INCOME, fact("2025-01-01", "2025-12-31", 900, "2027-02-10", "k26")]

    assert ttm(restated, d("2026-06-30"), d(Q2)) == 1000 + 650 - 420
    assert ttm(restated, d("2026-06-30"), d("2027-03-01")) == 900 + 650 - 420


def test_52주_회계연도라_기간_끝이_며칠_밀려도_맞춤() -> None:
    income = [
        fact("2024-12-29", "2025-12-27", 1000, K25),
        fact("2025-12-28", "2026-06-27", 650, Q2),
        fact("2024-12-29", "2025-06-28", 420, Q2),
    ]

    assert ttm(income, d("2026-06-27"), d(Q2)) == 1000 + 650 - 420


def test_작년_같은_기간이_없으면_비움() -> None:
    income = [
        fact("2025-01-01", "2025-12-31", 1000, K25),
        fact("2026-01-01", "2026-06-30", 650, Q2),
    ]

    assert ttm(income, d("2026-06-30"), d(Q2)) is None


def test_자본은_그_분기_끝_시점_값() -> None:
    equity = [fact(None, "2026-03-31", 5000, Q1), fact(None, "2026-06-30", 5200, Q2)]

    assert instant(equity, d("2026-06-30"), d(Q2)) == 5200
    assert instant(equity, d("2026-06-30"), d(Q1)) is None


def _company(cover: dict[str, list[int]], weighted: dict[str, int]) -> Facts:
    # 보고서마다 순이익·표지 주식 수·최근 분기 가중평균 주식 수
    ends = {"k25": "2025-12-31", "q1": "2026-03-31", "q2": "2026-06-30"}
    starts = {"k25": "2025-01-01", "q1": "2026-01-01", "q2": "2026-04-01"}
    filed = {"k25": K25, "q1": Q1, "q2": Q2}
    return {
        "net_income": INCOME,
        "cover_shares": [
            fact(None, filed[a], v, filed[a], a) for a, values in cover.items() for v in values
        ],
        "weighted_shares": [fact(starts[a], ends[a], v, filed[a], a) for a, v in weighted.items()],
    }


def test_보고서마다_그_공시일에_알던_값으로_하나씩() -> None:
    snaps = snapshots(_company({}, {}))

    # 기간 끝은 비교용 작년 값이 아니라 그 보고서의 기간
    assert [(s.filed, s.period_end, s.net_income) for s in snaps] == [
        (d(K25), d("2025-12-31"), 1000),
        (d(Q1), d("2026-03-31"), 1100),
        (d(Q2), d("2026-06-30"), 1230),
    ]


@pytest.mark.parametrize(
    ("cover", "weighted", "expected"),
    [
        ([1000], 990, 1000),
        # 표지 값이 여럿 (주식 종류별) — 어느 게 가격과 맞는지 모름
        ([600, 400], 1000, None),
        # 가중평균과 크게 다름 — 주식 종류마다 1주의 가치가 다른 회사 등
        ([1000], 1500, None),
    ],
)
def test_주식수는_가중평균과_교차_확인될_때만(
    cover: list[int], weighted: int, expected: int | None
) -> None:
    snaps = snapshots(_company({"q2": cover}, {"q2": weighted}))

    assert snaps[-1].shares == expected


def test_가중평균이_없으면_주식수를_믿지_않음() -> None:
    assert snapshots(_company({"q2": [1000]}, {}))[-1].shares is None


@pytest.mark.parametrize(
    ("older", "newer", "factor"),
    [
        (1000, 10_000, 10),  # 10:1 분할 — 옛 주식 수를 10배로
        (1000, 250, 0.25),  # 4:1 병합
        (1000, 950, 1),  # 자사주 매입으로 5% 줄어든 건 분할 아님
        (1000, 1500, 1),  # 합병 등으로 1.5배 — 정수배 분할로 보지 않음
    ],
)
def test_액면분할만_옛_주식수에_반영(older: int, newer: int, factor: float) -> None:
    factors = split_factors([(d(Q1), older), (d(Q2), newer)])

    assert factors[d(Q2)] == 1
    assert factors[d(Q1)] == factor


def test_분할은_여러_번이면_곱해서_반영() -> None:
    factors = split_factors([(d(K25), 100), (d(Q1), 400), (d(Q2), 4000)])

    assert factors[d(K25)] == 40


def test_분할_직후_교차_확인에_실패한_보고서로도_분할을_감지() -> None:
    # 2분기 보고서 표지는 분할 뒤 주식 수인데 가중평균은 분할 전 — 그 보고서는 주식 수 없음
    # 그래도 1분기 주식 수는 분할을 반영해 수정주가와 맞춤
    snaps = snapshots(_company({"q1": [1000], "q2": [10_000]}, {"q1": 1000, "q2": 1000}))

    assert [s.shares for s in snaps] == [None, 10_000, None]


def test_분할_반영_전후로_시가총액이_같음() -> None:
    # 수정주가 10 × 분할 반영 주식 10000 = 분할 전 가격 100 × 1000
    snaps = snapshots(_company({"q1": [1000], "q2": [10_000]}, {"q1": 1000, "q2": 10_000}))

    assert [s.shares for s in snaps] == [None, 10_000, 10_000]
    assert snaps[1].shares is not None and 10 * snaps[1].shares == 100 * 1000
