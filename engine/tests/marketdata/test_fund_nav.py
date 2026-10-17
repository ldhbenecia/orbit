from datetime import date
from decimal import Decimal

from orbit.marketdata.fund_nav import parse_ace_nav, parse_tiger_nav

# 운용사 상품 페이지 모양 — 값은 예시
TIGER_PAGE = """
<div class="tit">기준가격(NAV) <button>도움말</button></div>
<p>기준일 2026.10.02 16:55:33</p><p>본 정보는 10~20분 지연 정보입니다.</p>
<strong>10,123.45</strong> 원 <span>-50.00원(-0.49%)</span>
<div>주당 시장가격</div><strong>10,200</strong> 원
"""


def test_TIGER_상품_페이지에서_기준일과_기준가를_읽음() -> None:
    assert parse_tiger_nav(TIGER_PAGE) == (date(2026, 10, 2), Decimal("10123.45"))


def test_TIGER_기준가가_없으면_비움() -> None:
    assert parse_tiger_nav("<p>점검 중</p>") is None


def test_ACE_펀드_정보에서_기준일과_기준가를_읽음() -> None:
    body = {"stockCd": "KR7100000000", "stdDt": 20261001, "stpr": 12345.67, "clpr": 12400}

    assert parse_ace_nav(body) == (date(2026, 10, 1), Decimal("12345.67"))
