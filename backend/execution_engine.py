from datetime import datetime

from backend.decision_engine import evaluate_trade
from backend.sector_map import get_sector

execution_queue = []


def _find_trade(symbol):
    symbol = symbol.upper()

    for trade in execution_queue:
        if trade["symbol"] == symbol and trade["status"] not in [
            "FILLED",
            "COMPLETED",
        ]:
            return trade

    return None


def queue_trade_from_advice(symbol, advice):
    symbol = symbol.upper()

    base_confidence = advice.get("trade_plan", {}).get("confidence", 0)
    sector = advice.get("sector") or get_sector(symbol)
    strategy = advice.get("strategy", "Momentum")

    decision = evaluate_trade(
        symbol=symbol,
        confidence=base_confidence,
        strategy=strategy,
        sector=sector,
    )

    estimated_cost = advice.get("estimated_cost")

    if estimated_cost is None:
        estimated_cost = round(
            advice.get("current_price", 0)
            * advice.get("recommended_shares", 1),
            2,
        )

    if not advice.get("approved") or not decision["approved"]:
        existing = _find_trade(symbol)

        reason = advice.get("reason", "Trade was not approved.")

        if not decision["approved"]:
            reason = f"Decision Engine rejected trade: {decision['recommendation']}."

        if existing:
            existing["status"] = "REJECTED"
            existing["reason"] = reason
            existing["message"] = "Trade rejected by Decision Engine."
            existing["attempts"] = existing.get("attempts", 1) + 1
            existing["last_updated"] = datetime.utcnow().isoformat()
            existing["decision"] = decision

            return {
                "ok": False,
                "message": "Existing trade updated as rejected.",
                "trade": existing,
                "queue_size": len(execution_queue),
            }

        trade = {
            "id": len(execution_queue) + 1,
            "symbol": symbol,
            "status": "REJECTED",
            "reason": reason,
            "message": "Trade rejected by Decision Engine.",
            "attempts": 1,
            "created": datetime.utcnow().isoformat(),
            "decision": decision,
        }

        execution_queue.append(trade)

        return {
            "ok": False,
            "message": "Trade rejected and saved to queue history.",
            "trade": trade,
            "queue_size": len(execution_queue),
        }

    existing = _find_trade(symbol)

    decision_reason = (
        f"{symbol} approved by Decision Engine. "
        f"Decision Score: {decision['decision_score']}. "
        f"Recommendation: {decision['recommendation']}. "
        f"Allocation: {decision['recommended_allocation_pct']}%. "
        f"Strategy: {strategy}. "
        f"Sector: {sector}."
    )

    trade_payload = {
        "symbol": symbol,
        "status": "WAITING",
        "confidence": decision["decision_score"],
        "base_confidence": base_confidence,
        "decision_score": decision["decision_score"],
        "recommendation": decision["recommendation"],
        "decision": decision,
        "entry": advice["current_price"],
        "shares": advice.get("recommended_shares", 1),
        "allocation": decision["recommended_allocation_pct"],
        "estimated_cost": estimated_cost,
        "sector": sector,
        "strategy": strategy,
        "market_bias": advice.get("market_bias", "Bullish"),
        "reason": decision_reason,
        "last_checked": None,
        "message": "Queued and waiting for execution manager.",
    }

    if existing:
        existing.update(trade_payload)
        existing["attempts"] = existing.get("attempts", 1) + 1
        existing["last_updated"] = datetime.utcnow().isoformat()

        return {
            "ok": True,
            "message": "Existing trade updated.",
            "trade": existing,
            "queue_size": len(execution_queue),
        }

    trade = {
        "id": len(execution_queue) + 1,
        **trade_payload,
        "attempts": 1,
        "created": datetime.utcnow().isoformat(),
    }

    execution_queue.append(trade)

    return {
        "ok": True,
        "message": "Trade queued.",
        "trade": trade,
        "queue_size": len(execution_queue),
    }


def queue_trade(symbol, advice):
    return queue_trade_from_advice(symbol, advice)


def get_execution_queue():
    return execution_queue


def clear_execution_queue():
    execution_queue.clear()
    return {"ok": True, "queue_size": 0}


def clear_queue():
    return clear_execution_queue()


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