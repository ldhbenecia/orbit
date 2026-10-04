from decimal import ROUND_HALF_EVEN, Decimal


def to_units(value: Decimal, scale: int) -> int:
    # 반올림하면 금액이 조용히 바뀜 — 자릿수가 넘치면 저장을 거부
    scaled = value.scaleb(scale)
    if scaled != scaled.to_integral_value():
        raise ValueError(f"{value} 는 소수 {scale}자리 정수 단위로 정확히 표현되지 않음")
    return int(scaled)


def from_units(units: int, scale: int) -> Decimal:
    return Decimal(units).scaleb(-scale)


def round_to_units(value: Decimal, scale: int) -> int:
    # 백테스트 같은 분석 산출물 전용 — 장부·주문 금액에는 쓰지 않음 (to_units 로 정확히)
    return int(value.scaleb(scale).to_integral_value(ROUND_HALF_EVEN))
