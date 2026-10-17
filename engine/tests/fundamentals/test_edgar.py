from orbit.fundamentals.edgar import edgar_symbol, parse_facts, parse_tickers
from tests.fundamentals.facts import body, d, row


def test_SEC_종목코드는_주식_종류를_하이픈으로() -> None:
    assert edgar_symbol("EXA.B") == "EXA-B"
    assert edgar_symbol("EXA") == "EXA"


def test_종목코드별_CIK() -> None:
    tickers = {
        "0": {"cik_str": 1001, "ticker": "EXA", "title": "Example A"},
        "1": {"cik_str": 1002, "ticker": "EXB-B", "title": "Example B"},
    }

    assert parse_tickers(tickers) == {"EXA": 1001, "EXB-B": 1002}


def test_연간_분기_보고서만_읽고_해외기업_보고서는_뺌() -> None:
    facts = parse_facts(
        body(
            {
                "NetIncomeLoss": [
                    row("2025-01-01", "2025-12-31", 100, "2026-02-01", "a1", "10-K"),
                    row("2026-01-01", "2026-03-31", 30, "2026-05-01", "a2", "10-Q"),
                    row("2025-01-01", "2025-12-31", 999, "2026-03-01", "a3", "20-F"),
                    row("2025-01-01", "2025-12-31", 888, "2026-03-01", "a4", "8-K"),
                ]
            }
        )
    )

    assert [f.value for f in facts["net_income"]] == [100, 30]


def test_같은_기간이_여러_이름으로_있으면_앞쪽_이름을_씀() -> None:
    # 매출은 Revenues 가 우선 — 같은 보고서·같은 기간이면 다른 이름 값은 버림, 다른 기간은 채움
    facts = parse_facts(
        body(
            {
                "Revenues": [row("2026-01-01", "2026-03-31", 500, "2026-05-01", "a2")],
                "RevenueFromContractWithCustomerExcludingAssessedTax": [
                    row("2026-01-01", "2026-03-31", 480, "2026-05-01", "a2"),
                    row("2025-01-01", "2025-03-31", 400, "2026-05-01", "a2"),
                ],
            }
        )
    )

    assert sorted((f.end, f.value) for f in facts["revenue"]) == [
        (d("2025-03-31"), 400),
        (d("2026-03-31"), 500),
    ]


def test_표지_주식수와_가중평균_주식수는_주식_단위로() -> None:
    facts = parse_facts(
        body(
            {
                "WeightedAverageNumberOfDilutedSharesOutstanding": [
                    row("2026-01-01", "2026-03-31", 1_000, "2026-05-01", "a2")
                ]
            },
            cover=[row(None, "2026-04-20", 1_010, "2026-05-01", "a2")],
            shares_unit=("WeightedAverageNumberOfDilutedSharesOutstanding",),
        )
    )

    assert [f.value for f in facts["weighted_shares"]] == [1_000]
    assert [(f.start, f.value) for f in facts["cover_shares"]] == [(None, 1_010)]
