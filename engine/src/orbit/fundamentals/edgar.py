from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import httpx

from orbit.units import round_to_units

# 미국 SEC 공시 데이터 (XBRL) — 요청마다 연락처를 담은 User-Agent 필수, 초당 10회 이하
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

# 미국 회사의 연간·분기 보고서만 — 해외 기업(20-F, IFRS)·ETF 는 여기 없어 재무 없음
FORMS = frozenset({"10-K", "10-Q"})

# 같은 값을 회사·연도마다 다른 이름으로 공시함 — 앞쪽 이름을 우선
CONCEPTS: dict[str, tuple[str, ...]] = {
    "net_income": ("NetIncomeLoss",),
    "revenue": (
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
    ),
    "operating_cf": (
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ),
    "capex": ("PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"),
    "equity": (
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ),
    "weighted_shares": (
        "WeightedAverageNumberOfDilutedSharesOutstanding",
        "WeightedAverageNumberOfSharesOutstandingBasic",
    ),
}
COVER_SHARES = "EntityCommonStockSharesOutstanding"  # 보고서 표지의 발행주식 수 (dei)


@dataclass(frozen=True, slots=True)
class Fact:
    start: date | None  # 기간 값(이익·현금흐름)의 시작일, 시점 값(자본·주식 수)은 없음
    end: date
    value: int  # 달러 또는 주식 수
    filed: date  # 공시일 — 이 날부터 시장이 아는 값
    accn: str  # 공시 번호 — 한 보고서의 값끼리 묶음


Facts = dict[str, list[Fact]]  # CONCEPTS 의 키 + "cover_shares"


def edgar_symbol(symbol: str) -> str:
    # SEC 는 주식 종류를 하이픈으로 (BRK.B → BRK-B)
    return symbol.replace(".", "-")


def parse_tickers(body: dict[str, Any]) -> dict[str, int]:
    return {row["ticker"]: int(row["cik_str"]) for row in body.values()}


def _facts(units: dict[str, Any], unit: str) -> list[Fact]:
    out = []
    for row in units.get(unit, []):
        if row.get("form") not in FORMS:
            continue
        out.append(
            Fact(
                start=date.fromisoformat(row["start"]) if "start" in row else None,
                end=date.fromisoformat(row["end"]),
                # 분석용 값 — 달러 미만은 원 단위 저장 규칙처럼 정수로 반올림
                value=round_to_units(Decimal(str(row["val"])), 0),
                filed=date.fromisoformat(row["filed"]),
                accn=row["accn"],
            )
        )
    return out


def parse_facts(body: dict[str, Any]) -> Facts:
    taxonomies = body.get("facts", {})
    gaap = taxonomies.get("us-gaap", {})
    out: Facts = {}
    for key, names in CONCEPTS.items():
        unit = "shares" if key == "weighted_shares" else "USD"
        seen: set[tuple[date | None, date, str]] = set()
        merged: list[Fact] = []
        # 같은 기간·같은 보고서 값이 여러 이름으로 있으면 앞쪽 이름 것만
        for name in names:
            for fact in _facts(gaap.get(name, {}).get("units", {}), unit):
                slot = (fact.start, fact.end, fact.accn)
                if slot not in seen:
                    seen.add(slot)
                    merged.append(fact)
        out[key] = merged
    cover = taxonomies.get("dei", {}).get(COVER_SHARES, {}).get("units", {})
    out["cover_shares"] = _facts(cover, "shares")
    return out


def fetch_tickers(client: httpx.Client) -> dict[str, int]:
    response = client.get(SEC_TICKERS_URL)
    response.raise_for_status()
    return parse_tickers(response.json())


def fetch_facts(client: httpx.Client, cik: int) -> Facts:
    response = client.get(SEC_FACTS_URL.format(cik=cik))
    if response.status_code == 404:  # XBRL 공시가 없는 회사
        return {}
    response.raise_for_status()
    return parse_facts(response.json())
