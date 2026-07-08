from datetime import datetime

from backend.health_monitor import build_health_monitor
from backend.operations_dashboard import build_operations_dashboard
from backend.persistence_health import build_persistence_health
from backend.risk_engine import build_risk_engine
from backend.reconciliation import reconcile_positions


def run_system_validation():
    health = build_health_monitor()
    operations = build_operations_dashboard()
    persistence = build_persistence_health()
    risk = build_risk_engine()
    reconciliation = reconcile_positions()
    market_data = health.get("market_data", {})

    checks = {
        "health_monitor": health["healthy"],
        "operations_dashboard": operations["system_status"] == "HEALTHY",
        "market_data": (
            market_data.get("connected", False)
            and market_data.get("validated", False)
        ),
        "persistence": persistence["connected"],
        "order_persistence": persistence["order_persistence_ready"],
        "burn_in_persistence": persistence.get("burn_in_persistence_ready", False),
        "risk_engine": risk["trading_allowed"],
        "reconciliation": reconciliation["healthy"],
    }

    passed = sum(1 for value in checks.values() if value)
    total = len(checks)

    return {
        "generated": datetime.utcnow().isoformat(),
        "passed": passed,
        "total": total,
        "success": passed == total,
        "checks": checks,
        "persistence": persistence,
    }
