import threading
import time
from datetime import datetime

from backend.readiness_report import build_readiness_report

INTERVAL_SECONDS = 60

_thread = None
_running = False

_state = {
    "running": False,
    "started_at": None,
    "stopped_at": None,
    "checks": 0,
    "failures": 0,
    "last_check": None,
    "last_status": None,
    "last_error": None,
    "interval_seconds": INTERVAL_SECONDS,
}


def start_burn_in():
    global _thread, _running

    if _running:
        return status()

    _running = True
    _state["running"] = True
    _state["started_at"] = datetime.utcnow().isoformat()
    _state["stopped_at"] = None
    _state["last_error"] = None

    _thread = threading.Thread(target=_loop, daemon=True)
    _thread.start()

    return status()


def stop_burn_in():
    global _running

    _running = False
    _state["running"] = False
    _state["stopped_at"] = datetime.utcnow().isoformat()

    return status()


def _loop():
    while _running:
        try:
            run_burn_in_check()
        except Exception as e:
            _state["failures"] += 1
            _state["last_error"] = str(e)

        time.sleep(INTERVAL_SECONDS)


def run_burn_in_check():
    report = build_readiness_report()
    passed = report["paper_trading_ready"]

    _state["checks"] += 1
    _state["last_check"] = datetime.utcnow().isoformat()
    _state["last_status"] = report["overall_status"]
    _state["last_error"] = None

    if not passed:
        _state["failures"] += 1

    return {
        "passed": passed,
        "report": report,
        "burn_in": status(),
    }


def status():
    return {
        **_state,
        "thread_alive": _thread.is_alive() if _thread else False,
    }