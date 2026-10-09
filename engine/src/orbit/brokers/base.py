from dataclasses import dataclass
from typing import Protocol

from orbit.ledger.book import Fill, Mode, OrderRow, OrderStatus


@dataclass(frozen=True, slots=True)
class BrokerResult:
    status: OrderStatus  # unknown = 응답이 없거나 애매함 — 실패가 아니라 "모름"
    fill: Fill | None
    reason: str = ""


class Broker(Protocol):
    # 지정가만 — 시장가 주문 경로를 만들지 않음
    mode: Mode

    def place_limit_order(self, order: OrderRow) -> BrokerResult: ...

    def get_order(self, client_order_id: str) -> BrokerResult: ...
