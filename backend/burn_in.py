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
    "last_market_data_provider": None,
    "last_market_data_connected": None,
    "last_market_data_validated": None,
    "last_market_data_market_open": None,
    "last_market_data_sample_price": None,
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


def _record_market_data(report):
    market_data = report.get("health", {}).get("market_data", {})

    _state["last_market_data_provider"] = market_data.get("provider")
    _state["last_market_data_connected"] = market_data.get("connected")
    _state["last_market_data_validated"] = market_data.get("validated")
    _state["last_market_data_market_open"] = market_data.get("market_open")
    _state["last_market_data_sample_price"] = market_data.get("sample_price")

    return market_data


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

    if not passed:
        _state["failures"] += 1
        if not market_data.get("connected", False):
            _state["last_error"] = "Market data is disconnected."
        elif not market_data.get("validated", False):
            _state["last_error"] = "Market data is not validated."
        else:
            _state["last_error"] = "Readiness report is not ready for paper trading."

    return {
        "passed": passed,
        "market_data": market_data,
        "report": report,
        "burn_in": status(),
    }


def status():
    return {
        **_state,
        "thread_alive": _thread.is_alive() if _thread else False,
    }
