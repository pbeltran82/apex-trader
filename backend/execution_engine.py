from datetime import datetime

execution_queue = []


def queue_trade(symbol, advice):
    symbol = symbol.upper()

    if not advice.get("approved"):
        trade = {
            "id": len(execution_queue) + 1,
            "symbol": symbol,
            "status": "REJECTED",
            "reason": advice.get("reason", "Trade was not approved."),
            "created": datetime.utcnow().isoformat(),
        }

        execution_queue.append(trade)

        return {
            "ok": False,
            "message": "Trade rejected and added to queue history.",
            "trade": trade,
            "queue_size": len(execution_queue),
        }

    trade = {
        "id": len(execution_queue) + 1,
        "symbol": symbol,
        "status": "WAITING",
        "confidence": advice["trade_plan"]["confidence"],
        "entry": advice["current_price"],
        "shares": advice.get("recommended_shares", 1),
        "allocation": advice.get("recommended_allocation_pct", 1),
        "created": datetime.utcnow().isoformat(),
    }

    execution_queue.append(trade)

    return {
        "ok": True,
        "queue_size": len(execution_queue),
        "trade": trade,
    }


def get_execution_queue():
    return execution_queue


def execute_trade(symbol):
    symbol = symbol.upper()

    for trade in execution_queue:
        if trade["symbol"] == symbol:
            trade["status"] = "ACTIVE"
            trade["executed"] = datetime.utcnow().isoformat()
            return trade

    return {"error": "Trade not found."}


def complete_trade(symbol):
    symbol = symbol.upper()

    for trade in execution_queue:
        if trade["symbol"] == symbol:
            trade["status"] = "COMPLETED"
            trade["completed"] = datetime.utcnow().isoformat()
            return trade

    return {"error": "Trade not found."}