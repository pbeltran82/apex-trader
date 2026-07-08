from datetime import datetime

from backend.health_monitor import build_health_monitor
from backend.broker_health import status as broker_status
from backend.persistence_health import build_persistence_health
from backend.risk_engine import build_risk_engine
from backend.reconciliation import reconcile_positions
from backend.execution_engine import execution_queue


def build_operations_dashboard():
    broker = broker_status()
    risk = build_risk_engine()
    reconciliation = reconcile_positions()
    health = build_health_monitor()
    persistence = build_persistence_health()
    market_data = health.get("market_data", {})

    queued = len(execution_queue)

    waiting = sum(
        1 for o in execution_queue
        if o["status"] == "WAITING"
    )

    checking = sum(
        1 for o in execution_queue
        if o["status"] == "CHECKING"
    )

    executing = sum(
        1 for o in execution_queue
        if o["status"] == "EXECUTING"
    )

    filled = sum(
        1 for o in execution_queue
        if o["status"] == "FILLED"
    )

    rejected = sum(
        1 for o in execution_queue
        if o["status"] == "REJECTED"
    )

    errors = sum(
        1 for o in execution_queue
        if o["status"] == "ERROR"
    )

    return {
        "generated": datetime.utcnow().isoformat(),
        "system_status": "HEALTHY" if health["healthy"] and persistence["connected"] else "ATTENTION",
        "mode": {
            "market_data_provider": market_data.get("provider"),
            "broker_provider": broker.get("provider"),
            "live_data_paper_execution": (
                market_data.get("provider") == "ALPACA"
                and broker.get("provider") == "SIMULATION"
            ),
        },
        "broker": broker,
        "market_data": {
            "connected": market_data.get("connected"),
            "provider": market_data.get("provider"),
            "configured_provider": market_data.get("configured_provider"),
            "validated": market_data.get("validated"),
            "market_open": market_data.get("market_open"),
            "market_status": market_data.get("market_status"),
            "sample_symbol": market_data.get("sample_symbol"),
            "sample_price": market_data.get("sample_price"),
            "fallback_active": market_data.get("fallback_active"),
            "fallback_error": market_data.get("fallback_error"),
        },
        "persistence": {
            "connected": persistence.get("connected"),
            "database": persistence.get("database"),
            "order_persistence_ready": persistence.get("order_persistence_ready"),
            "execution_queue_count": persistence.get("execution_queue_count"),
            "tables": persistence.get("tables"),
            "error": persistence.get("error"),
        },
        "risk": {
            "trading_allowed": risk["trading_allowed"],
            "reasons": risk["reasons"],
        },
        "reconciliation": {
            "healthy": reconciliation["healthy"],
            "differences": reconciliation["differences"],
        },
        "queue": {
            "total": queued,
            "waiting": waiting,
            "checking": checking,
            "executing": executing,
            "filled": filled,
            "rejected": rejected,
            "errors": errors,
        },
        "health": health,
    }
