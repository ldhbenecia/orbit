from datetime import date
from typing import Any

# SEC companyfacts 응답 모양 — 회사·값은 전부 예시


def row(
    start: str | None, end: str, val: int, filed: str, accn: str, form: str = "10-Q"
) -> dict[str, Any]:
    out: dict[str, Any] = {"end": end, "val": val, "filed": filed, "accn": accn, "form": form}
    if start is not None:
        out["start"] = start
    return out


def body(
    gaap: dict[str, list[dict[str, Any]]],
    cover: list[dict[str, Any]] | None = None,
    shares_unit: tuple[str, ...] = (),
) -> dict[str, Any]:
    us_gaap = {
        name: {"units": {"shares" if name in shares_unit else "USD": rows}}
        for name, rows in gaap.items()
    }
    facts: dict[str, Any] = {"us-gaap": us_gaap}
    if cover is not None:
        facts["dei"] = {"EntityCommonStockSharesOutstanding": {"units": {"shares": cover}}}
    return {"cik": 1, "entityName": "Example Corp", "facts": facts}


def d(text: str) -> date:
    return date.fromisoformat(text)
