from decimal import Decimal

from orbit.marketdata.upbit_rules import krw_tick_size, round_to_tick


def test_호가_단위는_가격대별_공식_표와_같음() -> None:
    assert krw_tick_size(Decimal(115_183_000)) == Decimal(1000)
    assert krw_tick_size(Decimal(1_000_000)) == Decimal(1000)
    assert krw_tick_size(Decimal(999_999)) == Decimal(500)
    assert krw_tick_size(Decimal(4_500_000)) == Decimal(1000)
    assert krw_tick_size(Decimal(150)) == Decimal(1)
    assert krw_tick_size(Decimal("0.5")) == Decimal("0.001")


def test_매수는_올리고_매도는_내려_항상_불리한_쪽() -> None:
    price = Decimal(115_183_000) * Decimal("1.0005")  # 115,240,591.5

    assert round_to_tick(price, up=True) == Decimal(115_241_000)
    assert round_to_tick(price, up=False) == Decimal(115_240_000)


def test_이미_호가_단위면_그대로() -> None:
    assert round_to_tick(Decimal(115_241_000), up=True) == Decimal(115_241_000)
