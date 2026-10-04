import html
import re
from datetime import date
from decimal import Decimal
from typing import Any

import httpx

from orbit.marketdata.tiger_holdings import TIGER_BASE_URL

# 운용사가 공시하는 기준가(NAV, 1주당 순자산가치) — 둘 다 공개 API 가 아닌 화면용 경로라 바뀌면 깨짐
ACE_API_URL = "https://papi.aceetf.co.kr"

_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")
# "기준가격(NAV) … 기준일 2026.10.02 16:55:33 … 7,307.43 원" — 바로 뒤 "주당 시장가격"(종가)과 구분
_TIGER_NAV = re.compile(
    r"기준가격\(NAV\).{0,300}?기준일 (\d{4}\.\d{2}\.\d{2}).{0,300}?([\d,]+\.\d+) 원"
)

Nav = tuple[date, Decimal]  # (기준일, 기준가)


def parse_tiger_nav(page: str) -> Nav | None:
    text = _SPACE.sub(" ", _TAG.sub(" ", html.unescape(page)))
    match = _TIGER_NAV.search(text)
    if match is None:
        return None
    day = date.fromisoformat(match.group(1).replace(".", "-"))
    return day, Decimal(match.group(2).replace(",", ""))


def parse_ace_nav(body: dict[str, Any]) -> Nav | None:
    if not body.get("stdDt") or body.get("stpr") is None:
        return None
    # 숫자로 오지만 문자열로 바꿔 Decimal 로 — float 를 그대로 넘기면 이진 오차가 따라옴
    # 기준일은 20261001 같은 숫자로 옴
    return date.fromisoformat(str(body["stdDt"])), Decimal(str(body["stpr"]))


def fetch_tiger_nav(client: httpx.Client, ksd_fund: str) -> Nav | None:
    response = client.get(
        f"{TIGER_BASE_URL}/ko/product/search/detail/index.do", params={"ksdFund": ksd_fund}
    )
    response.raise_for_status()
    return parse_tiger_nav(response.text)


def fetch_ace_nav(client: httpx.Client, fund_code: str) -> Nav | None:
    response = client.get(f"{ACE_API_URL}/api/funds/{fund_code}")
    response.raise_for_status()
    body: dict[str, Any] = response.json()
    return parse_ace_nav(body.get("data", body))
