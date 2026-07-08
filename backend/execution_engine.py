import json
from datetime import datetime

from backend.database import get_connection
from backend.decision_engine import evaluate_trade
from backend.sector_map import get_sector

execution_queue = []

TERMINAL_STATUSES = [
    "FILLED",
    "COMPLETED",
]


def _now():
    return datetime.utcnow().isoformat()


def _ensure_execution_queue_schema():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS execution_queue (
        id INTEGER PRIMARY KEY,
        symbol TEXT,
        status TEXT,
        payload TEXT,
        created TEXT,
        last_updated TEXT
    )
    """)

    conn.commit()
    conn.close()


def _serialize_trade(trade):
    return json.dumps(trade, default=str)


def _persist_trade(trade):
    _ensure_execution_queue_schema()

    trade_id = int(trade["id"])
    symbol = trade.get("symbol")
    status = trade.get("status")
    created = trade.get("created") or _now()
    last_updated = trade.get("last_updated") or _now()

    trade["created"] = created
    trade["last_updated"] = last_updated

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO execution_queue (
            id, symbol, status, payload, created, last_updated
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            symbol = excluded.symbol,
            status = excluded.status,
            payload = excluded.payload,
            created = excluded.created,
            last_updated = excluded.last_updated
        """,
        (
            trade_id,
            symbol,
            status,
            _serialize_trade(trade),
            created,
            last_updated,
        ),
    )

    conn.commit()
    conn.close()


def _persist_all():
    for trade in execution_queue:
        _persist_trade(trade)


def _delete_all_persisted():
    _ensure_execution_queue_schema()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM execution_queue")
    conn.commit()
    conn.close()


def _next_id():
    queue_max = max([int(t.get("id", 0)) for t in execution_queue] or [0])

    conn = get_connection()
    row = conn.execute("SELECT MAX(id) AS max_id FROM execution_queue").fetchone()
    conn.close()

    db_max = int(row["max_id"] or 0) if row else 0

    return max(queue_max, db_max) + 1


def _load_execution_queue():
    global execution_queue

    _ensure_execution_queue_schema()

    conn = get_connection()
    rows = conn.execute(
        """
        SELECT payload
        FROM execution_queue
        ORDER BY id ASC
        """
    ).fetchall()
    conn.close()

    loaded = []

    for row in rows:
        try:
            loaded.append(json.loads(row["payload"]))
        except Exception:
            continue

    execution_queue = loaded


def _find_trade(symbol):
    symbol = symbol.upper()

    for trade in execution_queue:
        if trade["symbol"] == symbol and trade["status"] not in TERMINAL_STATUSES:
            return trade

    return None


def _save_existing_trade(trade):
    trade["last_updated"] = _now()
    _persist_trade(trade)
    return trade


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
            existing["decision"] = decision
            _save_existing_trade(existing)

            return {
                "ok": False,
                "message": "Existing trade updated as rejected.",
                "trade": existing,
                "queue_size": len(execution_queue),
            }

        trade = {
            "id": _next_id(),
            "symbol": symbol,
            "status": "REJECTED",
            "reason": reason,
            "message": "Trade rejected by Decision Engine.",
            "attempts": 1,
            "created": _now(),
            "last_updated": _now(),
            "decision": decision,
        }

        execution_queue.append(trade)
        _persist_trade(trade)

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
        _save_existing_trade(existing)

        return {
            "ok": True,
            "message": "Existing trade updated.",
            "trade": existing,
            "queue_size": len(execution_queue),
        }

    trade = {
        "id": _next_id(),
        **trade_payload,
        "attempts": 1,
        "created": _now(),
        "last_updated": _now(),
    }

    execution_queue.append(trade)
    _persist_trade(trade)

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
    _delete_all_persisted()
    return {"ok": True, "queue_size": 0}


def clear_queue():
    return clear_execution_queue()


def execute_trade(symbol):
    symbol = symbol.upper()

    for trade in execution_queue:
        if trade["symbol"] == symbol:
            trade["status"] = "ACTIVE"
            trade["executed"] = _now()
            _save_existing_trade(trade)
            return trade

    return {"error": "Trade not found."}


def complete_trade(symbol):
    symbol = symbol.upper()

    for trade in execution_queue:
        if trade["symbol"] == symbol:
            trade["status"] = "COMPLETED"
            trade["completed"] = _now()
            _save_existing_trade(trade)
            return trade

    return {"error": "Trade not found."}


def sync_execution_queue():
    _persist_all()
    return {"ok": True, "queue_size": len(execution_queue)}


_load_execution_queue()
