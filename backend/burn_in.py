import json
import os
import threading
import time
from datetime import datetime

from backend.database import get_connection
from backend.readiness_report import build_readiness_report

INTERVAL_SECONDS = int(os.getenv("BURN_IN_INTERVAL_SECONDS", "60"))
REQUIRED_CHECKS = int(os.getenv("BURN_IN_REQUIRED_CHECKS", "390"))

_thread = None
_running = False

_state = {
    "running": False,
    "started_at": None,
    "stopped_at": None,
    "checks": 0,
    "failures": 0,
    "passed_checks": 0,
    "required_checks": REQUIRED_CHECKS,
    "completed": False,
    "completed_at": None,
    "last_check": None,
    "last_status": None,
    "last_error": None,
    "last_market_data_provider": None,
    "last_market_data_connected": None,
    "last_market_data_validated": None,
    "last_market_data_market_open": None,
    "last_market_data_sample_price": None,
    "interval_seconds": INTERVAL_SECONDS,
}


def _ensure_burn_in_schema():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS burn_in_state (
        id INTEGER PRIMARY KEY,
        payload TEXT,
        updated TEXT
    )
    """)

    conn.commit()
    conn.close()


def _persist_state():
    _ensure_burn_in_schema()

    payload = json.dumps(_state, default=str)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO burn_in_state (id, payload, updated)
        VALUES (1, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            payload = excluded.payload,
            updated = excluded.updated
        """,
        (payload, datetime.utcnow().isoformat()),
    )

    conn.commit()
    conn.close()


def _load_state():
    _ensure_burn_in_schema()

    conn = get_connection()
    row = conn.execute(
        "SELECT payload FROM burn_in_state WHERE id = 1"
    ).fetchone()
    conn.close()

    if not row or not row["payload"]:
        return

    try:
        stored = json.loads(row["payload"])
    except Exception:
        return

    for key in _state.keys():
        if key in stored:
            _state[key] = stored[key]

    _state["running"] = False
    _state["stopped_at"] = _state.get("stopped_at")
    _state["required_checks"] = REQUIRED_CHECKS
    _state["interval_seconds"] = INTERVAL_SECONDS


def start_burn_in():
    global _thread, _running

    if _running:
        return status()

    _running = True
    _state["running"] = True

    if not _state.get("started_at"):
        _state["started_at"] = datetime.utcnow().isoformat()

    _state["stopped_at"] = None
    _state["last_error"] = None
    _persist_state()

    _thread = threading.Thread(target=_loop, daemon=True)
    _thread.start()

    return status()


def stop_burn_in():
    global _running

    _running = False
    _state["running"] = False
    _state["stopped_at"] = datetime.utcnow().isoformat()
    _persist_state()

    return status()


def reset_burn_in():
    global _running

    _running = False

    _state.update({
        "running": False,
        "started_at": None,
        "stopped_at": None,
        "checks": 0,
        "failures": 0,
        "passed_checks": 0,
        "required_checks": REQUIRED_CHECKS,
        "completed": False,
        "completed_at": None,
        "last_check": None,
        "last_status": None,
        "last_error": None,
        "last_market_data_provider": None,
        "last_market_data_connected": None,
        "last_market_data_validated": None,
        "last_market_data_market_open": None,
        "last_market_data_sample_price": None,
        "interval_seconds": INTERVAL_SECONDS,
    })

    _persist_state()

    return status()


def _loop():
    while _running:
        try:
            run_burn_in_check()
        except Exception as e:
            _state["failures"] += 1
            _state["last_error"] = str(e)
            _persist_state()

        time.sleep(INTERVAL_SECONDS)


def _record_market_data(report):
    market_data = report.get("health", {}).get("market_data", {})

    _state["last_market_data_provider"] = market_data.get("provider")
    _state["last_market_data_connected"] = market_data.get("connected")
    _state["last_market_data_validated"] = market_data.get("validated")
    _state["last_market_data_market_open"] = market_data.get("market_open")
    _state["last_market_data_sample_price"] = market_data.get("sample_price")

    return market_data


def _mark_completion_if_ready():
    completed = (
        _state["passed_checks"] >= REQUIRED_CHECKS
        and _state["failures"] == 0
    )

    if completed and not _state["completed"]:
        _state["completed"] = True
        _state["completed_at"] = datetime.utcnow().isoformat()

    return _state["completed"]


def run_burn_in_check():
    report = build_readiness_report()
    market_data = _record_market_data(report)

    passed = (
        report["paper_trading_ready"]
        and market_data.get("connected", False)
        and market_data.get("validated", False)
    )

    _state["checks"] += 1
    _state["last_check"] = datetime.utcnow().isoformat()
    _state["last_status"] = report["overall_status"]
    _state["last_error"] = None

    if passed:
        _state["passed_checks"] += 1
    else:
        _state["failures"] += 1
        _state["completed"] = False
        _state["completed_at"] = None

        if not market_data.get("connected", False):
            _state["last_error"] = "Market data is disconnected."
        elif not market_data.get("validated", False):
            _state["last_error"] = "Market data is not validated."
        else:
            _state["last_error"] = "Readiness report is not ready for paper trading."

    _mark_completion_if_ready()
    _persist_state()

    return {
        "passed": passed,
        "completed": _state["completed"],
        "market_data": market_data,
        "report": report,
        "burn_in": status(),
    }


def status():
    progress_pct = round(
        (_state["passed_checks"] / REQUIRED_CHECKS) * 100,
        2,
    ) if REQUIRED_CHECKS else 100.0

    return {
        **_state,
        "progress_pct": min(progress_pct, 100.0),
        "remaining_checks": max(REQUIRED_CHECKS - _state["passed_checks"], 0),
        "thread_alive": _thread.is_alive() if _thread else False,
    }


_load_state()
