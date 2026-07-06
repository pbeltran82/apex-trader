import threading
import time
from datetime import datetime

from backend.daily_scheduler import run_daily_scheduler
from backend.execution_manager import manage_execution_queue
from backend.exit_manager import run_exit_manager
from backend.event_log import log_event

_running = False
_thread = None

INTERVAL_SECONDS = 10

history = []

state = {
    "running": False,
    "started_at": None,
    "stopped_at": None,
    "last_tick": None,
    "ticks": 0,
    "last_daily_run_date": None,
    "last_result": None,
    "last_error": None,
}


def _summarize_execution(execution):
    filled = 0
    executing = 0
    checking = 0
    rejected = 0

    for item in execution.get("updates", []):
        status = item.get("status")

        if status == "FILLED":
            filled += 1
        elif status == "EXECUTING":
            executing += 1
        elif status == "CHECKING":
            checking += 1
        elif status == "REJECTED":
            rejected += 1

    return {
        "checked": execution.get("checked", 0),
        "filled": filled,
        "executing": executing,
        "checking": checking,
        "rejected": rejected,
    }


def _summarize_exits(exit_result):
    sold = 0
    held = 0

    for item in exit_result.get("updates", []):
        action = item.get("action")

        if action == "SELL":
            sold += 1
        elif action == "HOLD":
            held += 1

    return {
        "checked": exit_result.get("checked", 0),
        "sold": sold,
        "held": held,
    }


def run_autopilot_once():
    """
    Runs one autonomous Kyle heartbeat.
    """

    # Lazy import avoids circular import.
    from backend.mission_control import build_mission_control

    today = datetime.utcnow().date().isoformat()

    result = {
        "time": datetime.utcnow().isoformat(),
        "tick": state["ticks"] + 1,
        "daily_scheduler": None,
        "execution": None,
        "exit_manager": None,
        "mission_control": None,
        "summary": None,
    }

    log_event(
        "AUTOPILOT_TICK",
        f"Autopilot heartbeat {result['tick']} started.",
        {"tick": result["tick"]},
    )

    if state["last_daily_run_date"] != today:
        result["daily_scheduler"] = run_daily_scheduler()
        state["last_daily_run_date"] = today

        log_event(
            "DAILY_SCHEDULER",
            "Daily scheduler completed.",
            result["daily_scheduler"],
        )

    execution = manage_execution_queue()
    exit_result = run_exit_manager()
    mission_control = build_mission_control()

    execution_summary = _summarize_execution(execution)
    exit_summary = _summarize_exits(exit_result)

    result["execution"] = execution
    result["exit_manager"] = exit_result
    result["mission_control"] = mission_control

    result["summary"] = {
        "cash": mission_control["portfolio"]["cash"],
        "equity": mission_control["portfolio"]["equity"],
        "open_positions": mission_control["portfolio"]["open_positions"],
        "mode": mission_control["decision_mode"]["mode"],
        "recommendation": mission_control["recommendation"]["action"],
        "execution": execution_summary,
        "exits": exit_summary,
    }

    log_event(
        "MISSION_CONTROL",
        f"Mission Control updated. Mode: {result['summary']['mode']}.",
        result["summary"],
    )

    state["ticks"] += 1
    state["last_tick"] = datetime.utcnow().isoformat()
    state["last_result"] = result
    state["last_error"] = None

    history.insert(
        0,
        {
            "time": result["time"],
            "tick": result["tick"],
            "cash": result["summary"]["cash"],
            "equity": result["summary"]["equity"],
            "open_positions": result["summary"]["open_positions"],
            "mode": result["summary"]["mode"],
            "recommendation": result["summary"]["recommendation"],
            "execution": execution_summary,
            "exits": exit_summary,
        },
    )

    history[:] = history[:100]

    return result


def _loop():
    global _running

    print("===================================================")
    print("Kyle Autopilot Orchestrator Started")
    print("===================================================")

    while _running:
        try:
            run_autopilot_once()
        except Exception as e:
            state["last_error"] = str(e)

            log_event(
                "ERROR",
                str(e),
                {},
            )

            print(f"Autopilot Error: {e}")

        time.sleep(INTERVAL_SECONDS)

    print("Kyle Autopilot Orchestrator Stopped")


def start_autopilot():
    global _running, _thread

    if _running:
        return status()

    _running = True

    state["running"] = True
    state["started_at"] = datetime.utcnow().isoformat()
    state["stopped_at"] = None

    _thread = threading.Thread(
        target=_loop,
        daemon=True,
    )

    _thread.start()

    log_event(
        "AUTOPILOT",
        "Autopilot started.",
        {},
    )

    return status()


def stop_autopilot():
    global _running

    _running = False

    state["running"] = False
    state["stopped_at"] = datetime.utcnow().isoformat()

    if _thread:
        _thread.join(timeout=2)

    log_event(
        "AUTOPILOT",
        "Autopilot stopped.",
        {},
    )

    return status()


def status():
    return {
        **state,
        "interval_seconds": INTERVAL_SECONDS,
        "thread_alive": _thread.is_alive() if _thread else False,
        "history_count": len(history),
    }


def get_history(limit=20):
    return history[:limit]