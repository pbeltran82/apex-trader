from datetime import datetime

from backend.health_monitor import build_health_monitor
from backend.broker_health import status as broker_status
from backend.risk_engine import build_risk_engine
from backend.reconciliation import reconcile_positions
from backend.execution_engine import execution_queue


def build_operations_dashboard():

    broker = broker_status()

    risk = build_risk_engine()

    reconciliation = reconcile_positions()

    health = build_health_monitor()

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

        "system_status":
            "HEALTHY" if health["healthy"] else "ATTENTION",

        "broker": broker,

        "risk": {

            "trading_allowed":
                risk["trading_allowed"],

            "reasons":
                risk["reasons"],

        },

        "reconciliation": {

            "healthy":
                reconciliation["healthy"],

            "differences":
                reconciliation["differences"],

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