from datetime import datetime

execution_queue = []


def next_id():
    return len(execution_queue) + 1


def queue_trade_from_advice(symbol, advice):
    symbol = symbol.upper()

    existing = None
    for trade in execution_queue:
        if trade["symbol"] == symbol and trade["status"] not in [
            "COMPLETED",
            "FILLED",
        ]:
            existing = trade
            break

    if not advice.get("approved"):
        if existing:
            existing["status"] = "REJECTED"
            existing["reason"] = advice.get("reason", "Trade was not approved.")
            existing["message"] = "Trade rejected by latest advice."
            existing["attempts"] = existing.get("attempts", 1) + 1
            existing["last_updated"] = datetime.utcnow().isoformat()

            return {
                "ok": False,
                "message": "Existing trade updated as rejected.",
                "trade": existing,
                "queue_size": len(execution_queue),
            }

        trade = {
            "id": next_id(),
            "symbol": symbol,
            "status": "REJECTED",
            "reason": advice.get("reason", "Trade was not approved."),
            "message": "Trade rejected by advisor.",
            "attempts": 1,
            "created": datetime.utcnow().isoformat(),
        }

        execution_queue.append(trade)

        return {
            "ok": False,
            "message": "Trade rejected and saved to queue history.",
            "trade": trade,
            "queue_size": len(execution_queue),
        }

    if existing:
        existing.update(
            {
                "status": "WAITING",
                "confidence": advice["trade_plan"]["confidence"],
                "entry": advice["current_price"],
                "shares": advice["recommended_shares"],
                "allocation": advice["recommended_allocation_pct"],
                "estimated_cost": advice["recommended_dollars"],
                "sector": advice["sector"],
                "reason": advice["reason"],
                "message": "Trade updated and waiting for execution manager.",
                "attempts": existing.get("attempts", 1) + 1,
                "last_updated": datetime.utcnow().isoformat(),
            }
        )

        return {
            "ok": True,
            "message": "Existing trade updated.",
            "trade": existing,
            "queue_size": len(execution_queue),
        }

    trade = {
        "id": next_id(),
        "symbol": symbol,
        "status": "WAITING",
        "confidence": advice["trade_plan"]["confidence"],
        "entry": advice["current_price"],
        "shares": advice["recommended_shares"],
        "allocation": advice["recommended_allocation_pct"],
        "estimated_cost": advice["recommended_dollars"],
        "sector": advice["sector"],
        "reason": advice["reason"],
        "attempts": 1,
        "created": datetime.utcnow().isoformat(),
        "last_checked": None,
        "message": "Queued and waiting for execution manager.",
    }

    execution_queue.append(trade)

    return {
        "ok": True,
        "message": "Trade queued.",
        "trade": trade,
        "queue_size": len(execution_queue),
    }


def get_execution_queue():
    return execution_queue


def execute_trade(symbol):
    symbol = symbol.upper()

    for trade in execution_queue:
        if trade["symbol"] == symbol and trade["status"] == "WAITING":
            trade["status"] = "ACTIVE"
            trade["executed"] = datetime.utcnow().isoformat()
            trade["message"] = "Manually marked active."
            return trade

    return {"error": "Waiting trade not found."}


def complete_trade(symbol):
    symbol = symbol.upper()

    for trade in execution_queue:
        if trade["symbol"] == symbol and trade["status"] in ["ACTIVE", "FILLED"]:
            trade["status"] = "COMPLETED"
            trade["completed"] = datetime.utcnow().isoformat()
            trade["message"] = "Trade completed."
            return trade

    return {"error": "Active or filled trade not found."}


def clear_queue():
    execution_queue.clear()
    return {"ok": True, "queue_size": 0}