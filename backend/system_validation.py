from datetime import datetime

from backend.health_monitor import build_health_monitor
from backend.operations_dashboard import build_operations_dashboard
from backend.risk_engine import build_risk_engine
from backend.reconciliation import reconcile_positions


def run_system_validation():
    health = build_health_monitor()
    operations = build_operations_dashboard()
    risk = build_risk_engine()
    reconciliation = reconcile_positions()

    checks = {
        "health_monitor": health["healthy"],
        "operations_dashboard": operations["system_status"] == "HEALTHY",
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
    }