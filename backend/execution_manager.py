from datetime import datetime

from backend.activity_log import log_event
from backend.broker_factory import get_broker
from backend.execution_engine import execution_queue
from backend.market import prices
from backend.order import Order
from backend.order_state import OrderState
from backend.risk_engine import build_risk_engine
from backend.trade_history import record_trade


def manage_execution_queue():
    risk = build_risk_engine()

    if not risk["trading_allowed"]:
        return {
            "checked": 0,
            "blocked": True,
            "reason": risk["reasons"],
            "risk": risk,
            "updates": [],
        }

    broker = get_broker()

    updates = []

    for trade in execution_queue:

        if trade["status"] in [
            "REJECTED",
            "COMPLETED",
            "FILLED",
            "ERROR",
        ]:
            continue

        symbol = trade["symbol"]

        current_price = prices.get(symbol)

        if current_price is None:

            trade["status"] = "ERROR"
            trade["message"] = "No price available."
            trade["order_state"] = OrderState.REJECTED.value

            log_event(
                f"{symbol} execution error: No price available.",
                "ERROR",
            )

            updates.append(trade)
            continue

        trade["current_price"] = current_price
        trade["last_checked"] = datetime.utcnow().isoformat()

        order = Order(
            symbol=symbol,
            side="BUY",
            qty=int(trade.get("shares", 1)),
        )

        if trade["status"] == "WAITING":

            order.transition(OrderState.VALIDATED)

            trade["status"] = "CHECKING"
            trade["order_state"] = order.state.value
            trade["message"] = "Checking market conditions."

            log_event(
                f"{symbol} checking market conditions.",
                "CHECKING",
            )

            updates.append(trade)
            continue

        if trade["status"] == "CHECKING":

            order.transition(OrderState.VALIDATED)
            order.transition(OrderState.RISK_APPROVED)

            entry = trade.get("entry", current_price)

            if current_price <= entry * 1.01:

                order.transition(OrderState.SUBMITTED)

                trade["status"] = "EXECUTING"
                trade["order_state"] = order.state.value

                trade["message"] = (
                    "Entry conditions acceptable. Executing paper trade."
                )

                log_event(
                    f"{symbol} entry acceptable. Executing paper trade.",
                    "EXECUTING",
                )

            else:

                trade["status"] = "WAITING"
                trade["order_state"] = OrderState.QUEUED.value
                trade["message"] = (
                    "Price moved away from entry. Waiting."
                )

                log_event(
                    f"{symbol} price moved away from entry. Waiting.",
                    "WAITING",
                )

            updates.append(trade)
            continue

        if trade["status"] == "EXECUTING":

            qty = int(trade.get("shares", 1))

            order.transition(OrderState.SUBMITTED)

            result = broker.buy(
                symbol=symbol,
                qty=qty,
                sector=trade.get("sector", "Other"),
                confidence=trade.get("confidence", 0),
                strategy=trade.get("strategy", "Momentum"),
                market_bias=trade.get("market_bias", "Bullish"),
            )

            if result.get("error"):

                order.reject(result["error"])

                trade["status"] = "ERROR"
                trade["order_state"] = order.state.value
                trade["message"] = result["error"]
                trade["rejection_reason"] = (
                    order.rejection_reason
                )

                log_event(
                    f"{symbol} execution error: {trade['message']}",
                    "ERROR",
                )

            else:

                order.fill(current_price)
                order.monitor()

                trade["status"] = "FILLED"
                trade["order_state"] = OrderState.FILLED.value
                trade["filled_price"] = order.fill_price
                trade["filled_qty"] = order.filled_qty
                trade["average_fill_price"] = (
                    order.average_fill_price
                )
                trade["filled_at"] = (
                    datetime.utcnow().isoformat()
                )

                trade["message"] = (
                    f"Paper trade filled for {qty} share(s)."
                )

                record_trade(
                    side="BUY",
                    symbol=symbol,
                    qty=qty,
                    price=current_price,
                    total=current_price * qty,
                    source="EXECUTION_MANAGER",
                )

                log_event(
                    f"{symbol} filled for {qty} share(s) "
                    f"at ${current_price}.",
                    "FILLED",
                )

            updates.append(trade)

    return {
        "checked": len(execution_queue),
        "updates": updates,
    }