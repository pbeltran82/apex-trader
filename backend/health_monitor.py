from datetime import datetime

from backend.broker_health import status as broker_status
from backend.risk_engine import build_risk_engine
from backend.reconciliation import reconcile_positions


def build_health_monitor():
    broker = broker_status()
    risk = build_risk_engine()
    reconciliation = reconcile_positions()

    checks = {
        "broker_connected": broker["connected"],
        "trading_allowed": risk["trading_allowed"],
        "portfolio_reconciled": reconciliation["healthy"],
    }

    healthy = all(checks.values())
    passed = sum(1 for value in checks.values() if value)
    total = len(checks)

    return {
        "generated": datetime.utcnow().isoformat(),
        "healthy": healthy,
        "health_score": f"{passed}/{total}",
        "checks": checks,
        "broker": broker,
        "risk": risk,
        "reconciliation": reconciliation,
    }