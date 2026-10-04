from decimal import Decimal

import pytest

from orbit.units import from_units, round_to_units, to_units


def test_정수_단위로_정확히_왕복() -> None:
    assert to_units(Decimal("343.06635870"), 8) == 34306635870
    assert from_units(34306635870, 8) == Decimal("343.06635870")
    assert to_units(Decimal("115183000.00000000"), 0) == 115183000


def test_자릿수를_넘는_값은_반올림하지_않고_거부() -> None:
    with pytest.raises(ValueError):
        to_units(Decimal("115216000.1"), 0)
    with pytest.raises(ValueError):
        to_units(Decimal("0.000000001"), 8)


def test_분석_산출물_반올림은_은행가_반올림() -> None:
    assert round_to_units(Decimal("52974.5"), 0) == 52974
    assert round_to_units(Decimal("52975.5"), 0) == 52976
    assert round_to_units(Decimal("-0.8681234"), 6) == -868123
