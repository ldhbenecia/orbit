from decimal import Decimal

from orbit.marketdata.price_format import format_price


def test_통화별_표기() -> None:
    assert format_price("US-QQQ", Decimal("749.58")) == "$749.58"
    assert format_price("KRW-BTC", Decimal("115183000")) == "115,183,000원"
    assert format_price("KRX-367380", Decimal("31500")) == "31,500원"
