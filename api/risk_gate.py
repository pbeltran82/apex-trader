from typing import Dict, List

from pydantic import BaseModel, Field

from api import app as core


class RiskLimitUpdate(BaseModel):
    max_drawdown_pct: float | None = Field(default=None, gt=0, le=1)
    max_position_concentration_pct: float | None = Field(default=None, gt=0, le=1)
    min_cash_pct: float | None = Field(default=None, ge=0, le=1)
    max_daily_trades: int | None = Field(default=None, ge=1, le=100)


RISK_LIMITS = {
    "max_drawdown_pct": 0.08,
    "max_position_concentration_pct": 0.25,
    "min_cash_pct": 0.10,
    "max_daily_trades": 12,
}


def _today_prefix() -> str:
    return core._now()[:10]


def _today_trades() -> List[Dict]:
    today = _today_prefix()
    return [trade for trade in core.trades if trade.get("timestamp", "").startswith(today)]


def _largest_position_pct() -> float:
    core._refresh_equity(record=False)
    equity = max(core.account.get("equity", 0), 1)
    if not core.positions:
        return 0.0
    largest = max(position.get("market_value", 0) for position in core.positions)
    return round(largest / equity, 4)


def _cash_pct() -> float:
    core._refresh_equity(record=False)
    equity = max(core.account.get("equity", 0), 1)
    return round(core.account.get("buying_power", 0) / equity, 4)


def _drawdown_pct() -> float:
    core._refresh_equity(record=False)
    points = core.equity_curve or [{"equity": core.account.get("equity", 10000)}]
    peak = max(point.get("equity", 0) for point in points) or 1
    current = core.account.get("equity", 0)
    return round(max(0, (peak - current) / peak), 4)


def risk_telemetry() -> Dict:
    core._refresh_equity(record=False)
    daily_trades = _today_trades()
    concentration = _largest_position_pct()
    cash = _cash_pct()
    drawdown = _drawdown_pct()

    checks = [
        {
            "name": "drawdown_guard",
            "passed": drawdown <= RISK_LIMITS["max_drawdown_pct"],
            "value": drawdown,
            "limit": RISK_LIMITS["max_drawdown_pct"],
            "message": "Current drawdown is within limit." if drawdown <= RISK_LIMITS["max_drawdown_pct"] else "Drawdown limit breached.",
        },
        {
            "name": "position_concentration_guard",
            "passed": concentration <= RISK_LIMITS["max_position_concentration_pct"],
            "value": concentration,
            "limit": RISK_LIMITS["max_position_concentration_pct"],
            "message": "Largest position concentration is within limit." if concentration <= RISK_LIMITS["max_position_concentration_pct"] else "Largest position concentration is too high.",
        },
        {
            "name": "cash_guard",
            "passed": cash >= RISK_LIMITS["min_cash_pct"],
            "value": cash,
            "limit": RISK_LIMITS["min_cash_pct"],
            "message": "Cash buffer is healthy." if cash >= RISK_LIMITS["min_cash_pct"] else "Cash buffer is below minimum.",
        },
        {
            "name": "daily_trade_limit",
            "passed": len(daily_trades) < RISK_LIMITS["max_daily_trades"],
            "value": len(daily_trades),
            "limit": RISK_LIMITS["max_daily_trades"],
            "message": "Daily trade count is within limit." if len(daily_trades) < RISK_LIMITS["max_daily_trades"] else "Daily trade limit reached.",
        },
    ]

    passed = all(check["passed"] for check in checks)
    blockers = [check for check in checks if not check["passed"]]

    return {
        "ready": passed,
        "paper_only": True,
        "limits": RISK_LIMITS,
        "checks": checks,
        "blockers": blockers,
        "metrics": {
            "equity": core.account.get("equity"),
            "buying_power": core.account.get("buying_power"),
            "cash_pct": cash,
            "drawdown_pct": drawdown,
            "largest_position_pct": concentration,
            "open_positions": len(core.positions),
            "today_trade_count": len(daily_trades),
        },
    }


def readiness_report() -> Dict:
    telemetry = risk_telemetry()
    storage = {
        "state_file": str(core.STATE_FILE),
        "state_file_exists": core.STATE_FILE.exists(),
        "decision_log_file": str(core.DECISION_LOG_FILE),
        "decision_log_file_exists": core.DECISION_LOG_FILE.exists(),
    }
    status = core.autonomous_status()

    return {
        "ready_for_autonomous_paper_trading": telemetry["ready"],
        "mode": "paper",
        "autonomous_status": {
            "running": status["running"],
            "thread_alive": status["thread_alive"],
            "last_status": status["last_status"],
            "last_action": status["last_action"],
            "last_reason": status["last_reason"],
            "cycles": status["cycles"],
        },
        "risk": telemetry,
        "storage": storage,
        "next_best_action": "start_autonomous_trader" if telemetry["ready"] and not status["running"] else "hold_or_review_blockers",
    }


def guarded_cycle() -> Dict:
    telemetry = risk_telemetry()
    if not telemetry["ready"]:
        core._autonomous_state.update({
            "last_status": "BLOCKED_RISK_GATE",
            "last_action": "NO_TRADE",
            "last_selected_symbol": None,
            "last_reason": "Readiness risk gate blocked autonomous cycle.",
        })
        event = core._append_decision("RISK_GATE_BLOCKED", {"risk": telemetry})
        core._save_state()
        return {
            "ok": False,
            "message": "Autonomous cycle blocked by readiness risk gate.",
            "risk": telemetry,
            "event": event,
            "status": core.autonomous_status(),
        }

    result = core.run_autonomous_cycle()
    result["risk_gate"] = telemetry
    return result


def register_risk_gate(app):
    @app.get("/api/risk/telemetry")
    def get_risk_telemetry():
        return risk_telemetry()

    @app.get("/api/readiness")
    def get_readiness():
        return readiness_report()

    @app.post("/api/risk/limits")
    def update_risk_limits(payload: RiskLimitUpdate):
        updates = payload.dict(exclude_none=True)
        RISK_LIMITS.update(updates)
        event = core._append_decision("RISK_LIMITS_UPDATED", {"updates": updates, "limits": RISK_LIMITS})
        core._save_state()
        return {"ok": True, "limits": RISK_LIMITS, "event": event, "readiness": readiness_report()}

    @app.post("/api/autonomous-trader/run-guarded")
    def run_guarded_autonomous_cycle():
        return guarded_cycle()

    @app.get("/api/coo/status")
    def coo_status():
        return {
            "role": "COO",
            "system": "Kyle Apex Trader",
            "readiness": readiness_report(),
            "mission_control": core.mission_control(),
        }
