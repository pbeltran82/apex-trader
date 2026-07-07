from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from backend.order_state import OrderState


@dataclass
class Order:
    symbol: str
    side: str
    qty: float

    state: OrderState = OrderState.NEW
    created: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    broker_order_id: Optional[str] = None
    fill_price: Optional[float] = None
    rejection_reason: Optional[str] = None
    filled_qty: float = 0
    average_fill_price: Optional[float] = None

    def transition(self, state: OrderState):
        self.state = state
        self.updated = datetime.utcnow().isoformat()

    def acknowledge(self, broker_order_id: str):
        self.broker_order_id = broker_order_id
        self.transition(OrderState.ACKNOWLEDGED)

    def partial_fill(self, qty: float, price: float):
        self.filled_qty += qty
        self.average_fill_price = price
        self.transition(OrderState.PARTIALLY_FILLED)

    def fill(self, price: float):
        self.fill_price = price
        self.filled_qty = self.qty
        self.average_fill_price = price
        self.transition(OrderState.FILLED)

    def reject(self, reason: str):
        self.rejection_reason = reason
        self.transition(OrderState.REJECTED)

    def cancel(self):
        self.transition(OrderState.CANCELLED)

    def monitor(self):
        self.transition(OrderState.MONITORING)

    def exit(self):
        self.transition(OrderState.EXITED)

    def archive(self):
        self.transition(OrderState.ARCHIVED)