from datetime import datetime

from backend.activity_log import log_event
from backend.auto_exit_manager import run_auto_exit_manager
from backend.daily_plan import build_daily_plan
from backend.execution_engine import queue_trade_from_advice
from backend.execution_manager import manage_execution_queue
from backend.position_advisor import build_position_advice


autopilot_state = {
    "enabled": False,
    "running": False,
    "cycles": 0,
    "last_run": None,
    "last_action": None,
    "last_trade": None,
    "last_error": None,
}


def get_autopilot_status():
    return autopilot_state


def start_autopilot():
    autopilot_state["enabled"] = True
    autopilot_state["last_action"] = "Autopilot enabled."
    log_event("Autopilot enabled.", "SYSTEM")
    return autopilot_state


def stop_autopilot():
    autopilot_state["enabled"] = False
    autopilot_state["running"] = False
    autopilot_state["last_action"] = "Autopilot stopped."
    log_event("Autopilot stopped.", "SYSTEM")
    return autopilot_state


def run_autopilot_cycle():
    if not autopilot_state["enabled"]:
        return {
            "ok": False,
            "reason": "Autopilot is disabled.",
            "state": autopilot_state,
        }

    if autopilot_state["running"]:
        return {
            "ok": False,
            "reason": "Autopilot is already running.",
            "state": autopilot_state,
        }

    autopilot_state["running"] = True
    autopilot_state["cycles"] += 1
    autopilot_state["last_run"] = datetime.utcnow().isoformat()
    autopilot_state["last_error"] = None

    try:
        log_event("Autopilot cycle started.", "SYSTEM")

        plan = build_daily_plan(limit=3)
        top_picks = plan.get("top_picks", [])

        if not top_picks:
            autopilot_state["last_action"] = "No top picks available."
            log_event("Autopilot found no trade candidates.", "WAITING")

            exit_result = run_auto_exit_manager()

            return {
                "ok": True,
                "action": "NO_TRADE",
                "plan": plan,
                "exit_result": exit_result,
                "state": autopilot_state,
            }

        symbol = top_picks[0]["symbol"]

        advice = build_position_advice(symbol)
        queue_result = queue_trade_from_advice(symbol, advice)

        autopilot_state["last_trade"] = symbol

        if not queue_result.get("ok"):
            autopilot_state["last_action"] = f"{symbol} rejected."
            log_event(f"Autopilot rejected {symbol}.", "REJECTED")

            exit_result = run_auto_exit_manager()

            return {
                "ok": True,
                "action": "REJECTED",
                "symbol": symbol,
                "queue_result": queue_result,
                "exit_result": exit_result,
                "state": autopilot_state,
            }

        execution_1 = manage_execution_queue()
        execution_2 = manage_execution_queue()
        execution_3 = manage_execution_queue()

        exit_result = run_auto_exit_manager()

        autopilot_state["last_action"] = f"Autopilot processed {symbol}."
        log_event(f"Autopilot processed {symbol}.", "SYSTEM")

        return {
            "ok": True,
            "action": "PROCESSED",
            "symbol": symbol,
            "plan": plan,
            "queue_result": queue_result,
            "execution": [execution_1, execution_2, execution_3],
            "exit_result": exit_result,
            "state": autopilot_state,
        }

    except Exception as err:
        autopilot_state["last_error"] = str(err)
        autopilot_state["last_action"] = "Autopilot error."
        log_event(f"Autopilot error: {err}", "ERROR")

        return {
            "ok": False,
            "reason": str(err),
            "state": autopilot_state,
        }

    finally:
        autopilot_state["running"] = False