from datetime import datetime

from backend.health_monitor import build_health_monitor
from backend.persistence_health import build_persistence_health
from backend.system_validation import run_system_validation


def _burn_in_status_safe():
    try:
        from backend.burn_in import status as burn_in_status

        return burn_in_status()
    except Exception as error:
        return {
            "completed": False,
            "error": str(error),
        }


def build_readiness_report():
    validation = run_system_validation()
    health = build_health_monitor()
    persistence = build_persistence_health()
    burn_in = _burn_in_status_safe()

    checks = health.get("checks", {})
    broker = health.get("broker", {})
    market_data = health.get("market_data", {})

    blocking = []

    if not checks.get("broker_connected"):
        blocking.append("Broker is disconnected.")

    if not checks.get("market_data_connected"):
        blocking.append("Market data is disconnected.")

    if not market_data.get("validated", False):
        blocking.append("Market data is not validated.")

    if not persistence.get("connected", False):
        blocking.append("Database persistence is unavailable.")

    if not persistence.get("order_persistence_ready", False):
        blocking.append("Order persistence not implemented.")

    if not persistence.get("burn_in_persistence_ready", False):
        blocking.append("Burn-in persistence is unavailable.")

    if not checks.get("portfolio_reconciled"):
        blocking.append("Portfolio reconciliation failed.")

    if not checks.get("trading_allowed"):
        blocking.append("Enterprise Risk Engine is blocking trading.")

    paper_ready = validation["success"] and health["healthy"]

    live_data_paper_mode = (
        paper_ready
        and market_data.get("provider") == "ALPACA"
        and broker.get("provider") == "SIMULATION"
    )

    burn_in_completed = burn_in.get("completed", False)
    live_ready = False

    if paper_ready:
        blocking.append("Real broker integration incomplete.")

        if not burn_in_completed:
            blocking.append("Continuous burn-in not completed.")

    if live_data_paper_mode and burn_in_completed:
        overall_status = "LIVE_DATA_PAPER_BURN_IN_COMPLETE"
    elif live_data_paper_mode:
        overall_status = "LIVE_DATA_PAPER_READY"
    elif paper_ready:
        overall_status = "READY_FOR_PAPER"
    else:
        overall_status = "NOT_READY"

    return {
        "generated": datetime.utcnow().isoformat(),
        "paper_trading_ready": paper_ready,
        "live_data_paper_mode": live_data_paper_mode,
        "burn_in_completed": burn_in_completed,
        "live_trading_ready": live_ready,
        "overall_status": overall_status,
        "validation": validation,
        "health": health,
        "persistence": persistence,
        "burn_in": burn_in,
        "blocking_items": blocking,
    }
