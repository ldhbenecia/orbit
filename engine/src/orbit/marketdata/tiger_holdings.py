import html
import re
from dataclasses import dataclass
from decimal import Decimal

import httpx

# 운용사(미래에셋) 상품 페이지의 구성 종목(PDF) 표 — 공개 API 가 아닌 화면용 경로라 바뀌면 깨짐
TIGER_BASE_URL = "https://investments.miraeasset.com/tigeretf"
HOLDINGS_PATH = "/ko/product/search/detail/pdfListAjax.ajax"
PAGE_SIZE = 100

_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_TAG = re.compile(r"<[^>]+>")
_US_EQUITY = re.compile(r"^([A-Z0-9.\-]+) US EQUITY$")


@dataclass(frozen=True, slots=True)
class Holding:
    code: str  # 운용사 표기 그대로 (예: RKLB US EQUITY)
    symbol: str | None  # 토스 미국 종목 심볼 — 못 읽으면 없음
    name: str
    weight: Decimal  # 순자산 대비 비중 0~1
    is_cash: bool  # 원화 현금 — 환율·미국 등락과 무관


def parse_holdings(page: str) -> list[Holding]:
    holdings = []
    for row in _ROW.findall(page):
        cells = [html.unescape(_TAG.sub("", c)).strip() for c in _CELL.findall(row)]
        if len(cells) < 5:
            continue
        code, name, weight = cells[0], cells[1], Decimal(cells[4].replace(",", "")) / 100
        match = _US_EQUITY.match(code)
        holdings.append(
            Holding(
                code=code,
                symbol=match.group(1) if match else None,
                name=name,
                weight=weight,
                is_cash=name == "원화예금",
            )
        )
    return holdings


def fetch_holdings(client: httpx.Client, ksd_fund: str) -> list[Holding]:
    # 기준일을 비우면 운용사가 올린 최신 구성 종목
    response = client.post(
        HOLDINGS_PATH,
        data={"ksdFund": ksd_fund, "pageIndex": 1, "firstIndex": 0, "listCnt": PAGE_SIZE},
    )
    response.raise_for_status()
    return parse_holdings(response.text)
