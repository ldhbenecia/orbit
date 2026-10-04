from decimal import Decimal, InvalidOperation

from orbit.strategies.base import Strategy
from orbit.strategies.hold import always_hold
from orbit.strategies.ma_filter import make_ma_filter
from orbit.strategies.vol_breakout import make_vol_breakout


def build_strategy(spec: str) -> tuple[Strategy, dict[str, str]]:
    # "hold" · "ma-120" · "vb-0.5" 처럼 이름-파라미터 한 덩어리로 받음
    name, _, arg = spec.partition("-")
    if name == "hold" and not arg:
        return always_hold, {}
    if name == "ma" and arg.isdigit() and int(arg) > 0:
        return make_ma_filter(int(arg)), {"window": arg}
    if name == "vb" and arg:
        try:
            k = Decimal(arg)
        except InvalidOperation:
            k = Decimal(0)
        if 0 < k <= 1:
            return make_vol_breakout(k), {"k": arg}
    raise ValueError(f"알 수 없는 전략: {spec} (예: hold, ma-120, vb-0.5)")


# 규칙 상태 — 채택·기각은 ADR 과 docs/knowledge/orbit-rules.md 를 같이 고침
_STATUS = {"hold": "기준선", "ma": "실험 중", "vb": "실험 중"}


def strategy_status(spec: str) -> str:
    return _STATUS[spec.partition("-")[0]]
