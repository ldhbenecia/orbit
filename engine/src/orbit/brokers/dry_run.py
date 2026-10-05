from decimal import ROUND_CEILING, Decimal

from orbit.brokers.base import BrokerResult
from orbit.ledger.book import Fill, Mode, OrderRow
from orbit.marketdata.upbit_rules import FEE_RATE_KRW


def dry_run_fee(amount: Decimal) -> Decimal:
    # 업비트 수수료는 원 미만이 생김 — 장부는 원 단위라 올려서 기록 (실제보다 불리하게)
    return (amount * FEE_RATE_KRW).to_integral_value(ROUND_CEILING)


class DryRunBroker:
    # 실제로 주문하지 않음 — 지정가에 바로 체결됐다고 보고 기록만
    mode: Mode = "dry-run"

    def __init__(self) -> None:
        self._results: dict[str, BrokerResult] = {}

    def place_limit_order(self, order: OrderRow) -> BrokerResult:
        fee = dry_run_fee(order.qty * order.price)
        fill = Fill(order.client_order_id, order.side, order.qty, order.price, fee)
        result = BrokerResult("filled", fill)
        self._results[order.client_order_id] = result
        return result

    def get_order(self, client_order_id: str) -> BrokerResult:
        return self._results.get(client_order_id, BrokerResult("unknown", None, "기록 없음"))
