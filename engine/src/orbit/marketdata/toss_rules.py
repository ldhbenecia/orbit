from decimal import ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Literal

# 토스증권 미국주식 비용 — 출처·확인일은 docs/knowledge/toss-fees.md
US_FEE_RATE = Decimal("0.001")  # 매매 수수료 0.1%, $0.01 미만 절사
SEC_FEE_RATE = Decimal("0.0000206")  # 매도 SEC fee 0.00206%, 최소 $0.01
SEC_FEE_MIN = Decimal("0.01")
CENT = Decimal("0.01")


def us_fee(amount: Decimal, side: Literal["buy", "sell"]) -> Decimal:
    fee = (amount * US_FEE_RATE).quantize(CENT, ROUND_DOWN)
    if side == "sell":
        # 안내 문구 "소수 셋째 자리 반올림" 을 센트 단위 반올림으로 해석
        fee += max(amount * SEC_FEE_RATE, SEC_FEE_MIN).quantize(CENT, ROUND_HALF_UP)
    return fee


def round_to_cent(price: Decimal, up: bool) -> Decimal:
    # $1 이상 미국 주식 호가는 $0.01 — 더 촘촘한 호가가 있어도 매수 올림·매도 내림이라 보수적
    return price.quantize(CENT, ROUND_CEILING if up else ROUND_FLOOR)
