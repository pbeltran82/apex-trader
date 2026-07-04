from datetime import datetime

from backend.activity_log import log_event
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

            log_event(f"{symbol} execution error: No price available.", "ERROR")

            updates.append(trade)
            continue

        trade["current_price"] = current_price
        trade["last_checked"] = datetime.utcnow().isoformat()

        if trade["status"] == "WAITING":
            trade["status"] = "CHECKING"
            trade["message"] = "Checking market conditions."

            log_event(f"{symbol} checking market conditions.", "CHECKING")

            updates.append(trade)
            continue

        if trade["status"] == "CHECKING":
            entry = trade.get("entry", current_price)

            if current_price <= entry * 1.01:
                trade["status"] = "EXECUTING"
                trade["message"] = "Entry conditions acceptable. Executing paper trade."

                log_event(
                    f"{symbol} entry acceptable. Executing paper trade.",
                    "EXECUTING",
                )
            else:
                trade["status"] = "WAITING"
                trade["message"] = "Price moved away from entry. Waiting."

                log_event(
                    f"{symbol} price moved away from entry. Waiting.",
                    "WAITING",
                )

            updates.append(trade)
            continue

        if trade["status"] == "EXECUTING":
            qty = int(trade.get("shares", 1))
            result = buy_symbol(symbol, qty=qty)

            if result.get("error"):
                trade["status"] = "ERROR"
                trade["message"] = result["error"]

                log_event(f"{symbol} execution error: {trade['message']}", "ERROR")
            else:
                trade["status"] = "FILLED"
                trade["filled_price"] = current_price
                trade["filled_qty"] = qty
                trade["filled_at"] = datetime.utcnow().isoformat()
                trade["message"] = f"Paper trade filled for {qty} share(s)."

                log_event(
                    f"{symbol} filled for {qty} share(s) at ${current_price}.",
                    "FILLED",
                )

            updates.append(trade)
            continue

    return {
        "checked": len(execution_queue),
        "updates": updates,
    }