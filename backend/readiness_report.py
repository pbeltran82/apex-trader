from datetime import datetime

from backend.health_monitor import build_health_monitor
from backend.system_validation import run_system_validation


def build_readiness_report():

    validation = run_system_validation()
    health = build_health_monitor()

    blocking = []

    if not health["checks"]["broker_connected"]:
        blocking.append("Broker is disconnected.")

    if not health["checks"]["portfolio_reconciled"]:
        blocking.append("Portfolio reconciliation failed.")

    if not health["checks"]["trading_allowed"]:
        blocking.append("Enterprise Risk Engine is blocking trading.")

    paper_ready = (
        validation["success"]
        and health["healthy"]
    )

    live_ready = False

    if paper_ready:

        blocking.extend(
            [
                "Real broker integration incomplete.",
                "Order persistence not implemented.",
                "Continuous burn-in not completed.",
            ]
        )

    return {

        "generated":
            datetime.utcnow().isoformat(),

        "paper_trading_ready":
            paper_ready,

        "live_trading_ready":
            live_ready,

        "overall_status":

            "READY_FOR_PAPER"

            if paper_ready

            else

            "NOT_READY",

        "validation":
            validation,

        "health":
            health,

        "blocking_items":
            blocking,
    }