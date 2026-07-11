from __future__ import annotations

import os
from typing import Any, Dict

from api import risk_gate


def _float_env(name: str, default: float, low: float, high: float) -> float:
    raw = os.getenv(name, str(default))
    try:
        return max(low, min(high, float(raw)))
    except ValueError:
        return default


def _int_env(name: str, default: int, low: int, high: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        return max(low, min(high, int(raw)))
    except ValueError:
        return default


def _daily_starting_equity(app_module: Any) -> float:
    today = app_module._now()[:10]
    todays_points = [
        point
        for point in app_module.equity_curve
        if str(point.get("timestamp", "")).startswith(today)
    ]
    if todays_points:
        return max(float(todays_points[0].get("equity", 0)), 1.0)
    return max(float(app_module.account.get("equity", 0)), 1.0)


def _consecutive_losses(app_module: Any) -> int:
    count = 0
    for trade in reversed(app_module.trades):
        if trade.get("side") != "SELL":
            continue
        pnl = float(trade.get("realized_pnl", 0))
        if pnl < 0:
            count += 1
            continue
        break
    return count


def _open_risk_dollars(app_module: Any) -> float:
    total = 0.0
    for position in app_module.positions:
        entry = float(position.get("entry_price", 0))
        stop = float(
            position.get("stop_loss")
            or entry * (1 - app_module.config["stop_loss_pct"])
        )
        qty = float(position.get("qty", 0))
        total += max(0.0, entry - stop) * qty
    return round(total, 2)


def install_advanced_risk(app_module: Any) -> None:
    if getattr(app_module, "_advanced_risk_installed", False):
        return

    original_telemetry = risk_gate.risk_telemetry

    def advanced_telemetry() -> Dict:
        telemetry = original_telemetry()
        equity = max(float(app_module.account.get("equity", 0)), 1.0)
        daily_start = _daily_starting_equity(app_module)
        daily_loss_pct = max(0.0, (daily_start - equity) / daily_start)
        loss_streak = _consecutive_losses(app_module)
        open_risk_dollars = _open_risk_dollars(app_module)
        open_risk_pct = open_risk_dollars / equity

        max_daily_loss = _float_env("KYLE_MAX_DAILY_LOSS_PCT", 0.02, 0.0025, 0.10)
        max_loss_streak = _int_env("KYLE_MAX_CONSECUTIVE_LOSSES", 3, 1, 10)
        max_open_risk = _float_env("KYLE_MAX_OPEN_RISK_PCT", 0.02, 0.005, 0.10)

        advanced_checks = [
            {
                "name": "daily_loss_guard",
                "passed": daily_loss_pct < max_daily_loss,
                "value": round(daily_loss_pct, 4),
                "limit": max_daily_loss,
                "message": "Daily loss is within limit."
                if daily_loss_pct < max_daily_loss
                else "Daily loss limit reached; new entries are blocked.",
            },
            {
                "name": "consecutive_loss_guard",
                "passed": loss_streak < max_loss_streak,
                "value": loss_streak,
                "limit": max_loss_streak,
                "message": "Consecutive losses are within limit."
                if loss_streak < max_loss_streak
                else "Consecutive-loss limit reached; new entries are blocked.",
            },
            {
                "name": "total_open_risk_guard",
                "passed": open_risk_pct <= max_open_risk,
                "value": round(open_risk_pct, 4),
                "limit": max_open_risk,
                "message": "Total portfolio risk at stops is within limit."
                if open_risk_pct <= max_open_risk
                else "Total portfolio risk at stops exceeds the limit.",
            },
        ]

        telemetry["checks"].extend(advanced_checks)
        telemetry["blockers"] = [
            check for check in telemetry["checks"] if not check["passed"]
        ]
        telemetry["ready"] = not telemetry["blockers"]
        telemetry["limits"].update(
            {
                "max_daily_loss_pct": max_daily_loss,
                "max_consecutive_losses": max_loss_streak,
                "max_open_risk_pct": max_open_risk,
            }
        )
        telemetry["metrics"].update(
            {
                "daily_starting_equity": round(daily_start, 2),
                "daily_loss_pct": round(daily_loss_pct, 4),
                "consecutive_losses": loss_streak,
                "open_risk_dollars": open_risk_dollars,
                "open_risk_pct": round(open_risk_pct, 4),
            }
        )
        return telemetry

    risk_gate.risk_telemetry = advanced_telemetry
    app_module._advanced_risk_installed = True

    @app_module.app.get("/api/risk/advanced")
    def advanced_risk_status():
        return advanced_telemetry()
