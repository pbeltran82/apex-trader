from datetime import datetime

from backend.execution_engine import execution_queue
from backend.market import prices
from backend.portfolio import buy_symbol


def manage_execution_queue():
    updates = []

    for trade in execution_queue:
        if trade["status"] in ["REJECTED", "COMPLETED", "FILLED", "ERROR"]:
            continue

        symbol = trade["symbol"]
        current_price = prices.get(symbol)

        if current_price is None:
            trade["status"] = "ERROR"
            trade["message"] = "No price available."
            updates.append(trade)
            continue

        trade["current_price"] = current_price
        trade["last_checked"] = datetime.utcnow().isoformat()

        if trade["status"] == "WAITING":
            trade["status"] = "CHECKING"
            trade["message"] = "Checking market conditions."
            updates.append(trade)
            continue

        if trade["status"] == "CHECKING":
            entry = trade.get("entry", current_price)

            if current_price <= entry * 1.01:
                trade["status"] = "EXECUTING"
                trade["message"] = "Entry conditions acceptable. Executing paper trade."
            else:
                trade["status"] = "WAITING"
                trade["message"] = "Price moved away from entry. Waiting."

            updates.append(trade)
            continue

        if trade["status"] == "EXECUTING":
            qty = int(trade.get("shares", 1))
            result = buy_symbol(symbol, qty=qty)

            if result.get("error"):
                trade["status"] = "ERROR"
                trade["message"] = result["error"]
            else:
                trade["status"] = "FILLED"
                trade["filled_price"] = current_price
                trade["filled_qty"] = qty
                trade["filled_at"] = datetime.utcnow().isoformat()
                trade["message"] = f"Paper trade filled for {qty} share(s)."

            updates.append(trade)
            continue

    return {
        "checked": len(execution_queue),
        "updates": updates,
    }