from datetime import datetime

from backend.activity_log import log_event
from backend.auto_exit_manager import run_auto_exit_manager
from backend.daily_plan import build_daily_plan
from backend.execution_engine import queue_trade_from_advice
from backend.execution_manager import manage_execution_queue
from backend.position_advisor import build_position_advice
from backend.risk_governor import check_risk
from backend.portfolio_live import build_portfolio_live


MAX_AUTOPILOT_POSITIONS = 3
MAX_AUTOPILOT_EXPOSURE_PCT = 18.0


autopilot_state = {
    "enabled": False,
    "running": False,
    "cycles": 0,
    "last_run": None,
    "last_action": None,
    "last_trade": None,
    "last_error": None,
    "mode": "IDLE",
}


def get_autopilot_status():
    return {
        **autopilot_state,
        "max_autopilot_positions": MAX_AUTOPILOT_POSITIONS,
        "max_autopilot_exposure_pct": MAX_AUTOPILOT_EXPOSURE_PCT,
    }


def start_autopilot():
    autopilot_state["enabled"] = True
    autopilot_state["mode"] = "IDLE"
    autopilot_state["last_action"] = "Autopilot enabled."
    log_event("Autopilot enabled.", "SYSTEM")
    return get_autopilot_status()


def stop_autopilot():
    autopilot_state["enabled"] = False
    autopilot_state["running"] = False
    autopilot_state["mode"] = "STOPPED"
    autopilot_state["last_action"] = "Autopilot stopped."
    log_event("Autopilot stopped.", "SYSTEM")
    return get_autopilot_status()


def run_autopilot_cycle():
    if not autopilot_state["enabled"]:
        return {
            "ok": False,
            "reason": "Autopilot is disabled.",
            "state": get_autopilot_status(),
        }

    if autopilot_state["running"]:
        return {
            "ok": False,
            "reason": "Autopilot is already running.",
            "state": get_autopilot_status(),
        }

    autopilot_state["running"] = True
    autopilot_state["cycles"] += 1
    autopilot_state["last_run"] = datetime.utcnow().isoformat()
    autopilot_state["last_error"] = None

    try:
        autopilot_state["mode"] = "RISK_CHECK"
        log_event("Autopilot cycle started.", "SYSTEM")

        risk = check_risk()

        if not risk["safe"]:
            stop_autopilot()

            autopilot_state["last_action"] = "Stopped by Risk Governor."
            autopilot_state["last_error"] = risk["reason"]
            autopilot_state["mode"] = "RISK_SHUTDOWN"

            return {
                "ok": False,
                "action": "RISK_SHUTDOWN",
                "reason": risk["reason"],
                "risk": risk,
                "state": get_autopilot_status(),
            }

        autopilot_state["mode"] = "MONITORING"
        portfolio = build_portfolio_live()

        exit_result = run_auto_exit_manager()

        open_positions = portfolio["open_positions"]
        exposure_pct = portfolio["exposure_pct"]

        if open_positions >= MAX_AUTOPILOT_POSITIONS:
            autopilot_state["last_action"] = (
                f"Portfolio guard active: {open_positions} open positions. Monitoring only."
            )
            autopilot_state["mode"] = "MONITOR_ONLY"

            log_event(
                f"Autopilot monitoring only: max positions reached ({open_positions}).",
                "SYSTEM",
            )

            return {
                "ok": True,
                "action": "MONITOR_ONLY",
                "reason": "Maximum autopilot positions reached.",
                "portfolio": portfolio,
                "exit_result": exit_result,
                "state": get_autopilot_status(),
            }

        if exposure_pct >= MAX_AUTOPILOT_EXPOSURE_PCT:
            autopilot_state["last_action"] = (
                f"Portfolio guard active: exposure {exposure_pct}%. Monitoring only."
            )
            autopilot_state["mode"] = "MONITOR_ONLY"

            log_event(
                f"Autopilot monitoring only: exposure limit reached ({exposure_pct}%).",
                "SYSTEM",
            )

            return {
                "ok": True,
                "action": "MONITOR_ONLY",
                "reason": "Maximum autopilot exposure reached.",
                "portfolio": portfolio,
                "exit_result": exit_result,
                "state": get_autopilot_status(),
            }

        autopilot_state["mode"] = "SCANNING"

        plan = build_daily_plan(limit=3)
        top_picks = plan.get("top_picks", [])

        if not top_picks:
            autopilot_state["last_action"] = "No top picks available."
            autopilot_state["mode"] = "WAITING"
            log_event("Autopilot found no trade candidates.", "WAITING")

            return {
                "ok": True,
                "action": "NO_TRADE",
                "plan": plan,
                "exit_result": exit_result,
                "state": get_autopilot_status(),
            }

        symbol = top_picks[0]["symbol"]

        autopilot_state["mode"] = "ANALYZING"
        advice = build_position_advice(symbol)

        autopilot_state["mode"] = "QUEUEING"
        queue_result = queue_trade_from_advice(symbol, advice)

        autopilot_state["last_trade"] = symbol

        if not queue_result.get("ok"):
            autopilot_state["last_action"] = f"{symbol} rejected."
            autopilot_state["mode"] = "REJECTED"
            log_event(f"Autopilot rejected {symbol}.", "REJECTED")

            return {
                "ok": True,
                "action": "REJECTED",
                "symbol": symbol,
                "queue_result": queue_result,
                "exit_result": exit_result,
                "state": get_autopilot_status(),
            }

        autopilot_state["mode"] = "EXECUTING"

        execution_1 = manage_execution_queue()
        execution_2 = manage_execution_queue()
        execution_3 = manage_execution_queue()

        autopilot_state["mode"] = "MONITORING"
        exit_result = run_auto_exit_manager()

        autopilot_state["last_action"] = f"Autopilot processed {symbol}."
        autopilot_state["mode"] = "IDLE"
        log_event(f"Autopilot processed {symbol}.", "SYSTEM")

        return {
            "ok": True,
            "action": "PROCESSED",
            "symbol": symbol,
            "plan": plan,
            "queue_result": queue_result,
            "execution": [execution_1, execution_2, execution_3],
            "exit_result": exit_result,
            "state": get_autopilot_status(),
        }

    except Exception as err:
        autopilot_state["last_error"] = str(err)
        autopilot_state["last_action"] = "Autopilot error."
        autopilot_state["mode"] = "ERROR"
        log_event(f"Autopilot error: {err}", "ERROR")

        return {
            "ok": False,
            "reason": str(err),
            "state": get_autopilot_status(),
        }

    finally:
        autopilot_state["running"] = False