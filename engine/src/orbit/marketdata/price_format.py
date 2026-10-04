from decimal import Decimal


def format_price(market: str, value: Decimal) -> str:
    # 미국 주식은 달러 센트까지, 원화(업비트·KRX)는 원 단위
    if market.startswith("US-"):
        return f"${value:,.2f}"
    return f"{value:,.0f}원"
