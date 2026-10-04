from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

# 업비트 공식 수수료·거래 이용 안내 기준 — 바뀌면 여기만 고침
# KRW 마켓 일반주문 Maker·Taker 동일 — 예약주문은 0.139% 라 쓰지 않음
FEE_RATE_KRW = Decimal("0.0005")
MIN_ORDER_KRW = Decimal(5000)

# (이 가격 이상, 호가 단위) — 높은 가격부터
_KRW_TICKS: list[tuple[Decimal, Decimal]] = [
    (Decimal(1_000_000), Decimal(1000)),
    (Decimal(500_000), Decimal(500)),
    (Decimal(100_000), Decimal(100)),
    (Decimal(50_000), Decimal(50)),
    (Decimal(10_000), Decimal(10)),
    (Decimal(5_000), Decimal(5)),
    (Decimal(100), Decimal(1)),
    (Decimal(10), Decimal("0.1")),
    (Decimal(1), Decimal("0.01")),
    (Decimal("0.1"), Decimal("0.001")),
    (Decimal("0.01"), Decimal("0.0001")),
    (Decimal("0.001"), Decimal("0.00001")),
    (Decimal("0.0001"), Decimal("0.000001")),
    (Decimal("0.00001"), Decimal("0.0000001")),
]
_SMALLEST_TICK = Decimal("0.00000001")


def krw_tick_size(price: Decimal) -> Decimal:
    for floor, tick in _KRW_TICKS:
        if price >= floor:
            return tick
    return _SMALLEST_TICK


def round_to_tick(price: Decimal, up: bool) -> Decimal:
    # 지정가는 호가 단위에 맞아야 접수됨 — 매수는 올리고 매도는 내려 항상 불리한 쪽으로
    tick = krw_tick_size(price)
    steps = (price / tick).to_integral_value(ROUND_CEILING if up else ROUND_FLOOR)
    return steps * tick
