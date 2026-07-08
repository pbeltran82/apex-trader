import os
import threading
import time
from datetime import datetime

from backend.execution_engine import get_execution_queue, queue_trade_from_advice
from backend.execution_manager import manage_execution_queue
from backend.exit_manager import run_exit_manager
from backend.health_monitor import build_health_monitor
from backend.market_data.service import get_prices, get_watchlist
from backend.position_advisor import build_position_advice
from backend.risk_engine import build_risk_engine

INTERVAL_SECONDS = int(os.getenv("AUTONOMOUS_TRADER_INTERVAL_SECONDS", "300"))
MAX_CANDIDATES = int(os.getenv("AUTONOMOUS_TRADER_MAX_CANDIDATES", "12"))
MAX_QUEUE_SIZE = int(os.getenv("AUTONOMOUS_TRADER_MAX_QUEUE_SIZE", "3"))
MIN_CONFIDENCE = float(os.getenv("AUTONOMOUS_TRADER_MIN_CONFIDENCE", "70"))

_thread = None
_running = False

_state = {
    "running": False,
    "started_at": None,
    "stopped_at": None,
    "cycles": 0,
    "failures": 0,
    "last_run": None,
    "last_error": None,
    "last_status": "IDLE",
    "last_selected_symbol": None,
    "last_action": None,
    "last_reason": None,
    "last_queue_size": 0,
    "last_execution_updates": 0,
    "last_exit_updates": 0,
    "interval_seconds": INTERVAL_SECONDS,
    "max_candidates": MAX_CANDIDATES,
    "max_queue_size": MAX_QUEUE_SIZE,
    "min_confidence": MIN_CONFIDENCE,
}


def _now():
    return datetime.utcnow().isoformat()


def _queue_size():
    return len(get_execution_queue())


def _non_terminal_queue_size():
    terminal = {"FILLED", "COMPLETED", "REJECTED", "ERROR"}
    return sum(
        1 for trade in get_execution_queue()
        if trade.get("status") not in terminal
    )


def _candidate_score(advice):
    trade_plan = advice.get("trade_plan", {})
    decision_confidence = trade_plan.get("confidence", 0)
    recommended_shares = advice.get("recommended_shares", 0)

    if not advice.get("approved"):
        return -1

    if recommended_shares <= 0:
        return -1

    return float(decision_confidence or 0)


def _build_candidates():
    prices = get_prices()
    symbols = [
        symbol for symbol in get_watchlist()
        if symbol in prices
    ][:MAX_CANDIDATES]

    candidates = []

    for symbol in symbols:
        try:
            advice = build_position_advice(symbol)
            score = _candidate_score(advice)

            candidates.append({
                "symbol": symbol,
                "score": score,
                "approved": bool(advice.get("approved")),
                "action": advice.get("action"),
                "reason": advice.get("reason"),
                "recommended_shares": advice.get("recommended_shares", 0),
                "current_price": advice.get("current_price"),
                "advice": advice,
            })
        except Exception as error:
            candidates.append({
                "symbol": symbol,
                "score": -1,
                "approved": False,
                "action": "ERROR",
                "reason": str(error),
                "recommended_shares": 0,
                "current_price": None,
                "advice": {"error": str(error)},
            })

    candidates.sort(key=lambda row: row["score"], reverse=True)
    return candidates


def _select_candidate(candidates):
    for candidate in candidates:
        if candidate["score"] >= MIN_CONFIDENCE:
            return candidate

    return None


def run_autonomous_cycle():
    health = build_health_monitor()
    risk = build_risk_engine()

    _state["cycles"] += 1
    _state["last_run"] = _now()
    _state["last_error"] = None

    if not health.get("healthy"):
        _state["last_status"] = "BLOCKED_HEALTH"
        _state["last_action"] = "NO_TRADE"
        _state["last_reason"] = "Health monitor is not healthy."
        return status(extra={"health": health})

    if not risk.get("trading_allowed"):
        _state["last_status"] = "BLOCKED_RISK"
        _state["last_action"] = "NO_TRADE"
        _state["last_reason"] = "; ".join(risk.get("reasons", []))
        return status(extra={"health": health, "risk": risk})

    exit_result = run_exit_manager()
    execution_result = manage_execution_queue()

    queue_size = _non_terminal_queue_size()
    _state["last_queue_size"] = queue_size
    _state["last_execution_updates"] = len(execution_result.get("updates", []))
    _state["last_exit_updates"] = len(exit_result.get("updates", []))

    if queue_size >= MAX_QUEUE_SIZE:
        _state["last_status"] = "QUEUE_FULL"
        _state["last_action"] = "MANAGED_ONLY"
        _state["last_reason"] = "Queue is at maximum autonomous capacity."
        return status(extra={
            "health": health,
            "risk": risk,
            "execution": execution_result,
            "exits": exit_result,
        })

    candidates = _build_candidates()
    selected = _select_candidate(candidates)

    if not selected:
        _state["last_status"] = "NO_CANDIDATE"
        _state["last_action"] = "NO_TRADE"
        _state["last_selected_symbol"] = None
        _state["last_reason"] = "No approved candidate met confidence threshold."
        return status(extra={
            "health": health,
            "risk": risk,
            "execution": execution_result,
            "exits": exit_result,
            "candidates": candidates[:5],
        })

    queue_result = queue_trade_from_advice(
        selected["symbol"],
        selected["advice"],
    )

    execution_after_queue = manage_execution_queue()

    _state["last_status"] = "CYCLE_COMPLETE"
    _state["last_action"] = "QUEUED" if queue_result.get("ok") else "REJECTED"
    _state["last_selected_symbol"] = selected["symbol"]
    _state["last_reason"] = queue_result.get("message")
    _state["last_queue_size"] = _non_terminal_queue_size()
    _state["last_execution_updates"] = len(execution_after_queue.get("updates", []))

    return status(extra={
        "health": health,
        "risk": risk,
        "selected": {
            "symbol": selected["symbol"],
            "score": selected["score"],
            "approved": selected["approved"],
            "recommended_shares": selected["recommended_shares"],
            "current_price": selected["current_price"],
        },
        "queue_result": queue_result,
        "execution_before_queue": execution_result,
        "execution_after_queue": execution_after_queue,
        "exits": exit_result,
        "candidates": candidates[:5],
    })


def _loop():
    while _running:
        try:
            run_autonomous_cycle()
        except Exception as error:
            _state["failures"] += 1
            _state["last_error"] = str(error)
            _state["last_status"] = "ERROR"

        time.sleep(INTERVAL_SECONDS)


def start_autonomous_trader():
    global _thread, _running

    if _running:
        return status()

    _running = True
    _state["running"] = True
    _state["started_at"] = _now()
    _state["stopped_at"] = None
    _state["last_error"] = None
    _state["last_status"] = "RUNNING"

    _thread = threading.Thread(target=_loop, daemon=True)
    _thread.start()

    return status()


def stop_autonomous_trader():
    global _running

    _running = False
    _state["running"] = False
    _state["stopped_at"] = _now()
    _state["last_status"] = "STOPPED"

    return status()


def reset_autonomous_trader():
    global _running

    _running = False

    _state.update({
        "running": False,
        "started_at": None,
        "stopped_at": None,
        "cycles": 0,
        "failures": 0,
        "last_run": None,
        "last_error": None,
        "last_status": "IDLE",
        "last_selected_symbol": None,
        "last_action": None,
        "last_reason": None,
        "last_queue_size": _queue_size(),
        "last_execution_updates": 0,
        "last_exit_updates": 0,
    })

    return status()


def status(extra=None):
    payload = {
        **_state,
        "thread_alive": _thread.is_alive() if _thread else False,
        "queue_size": _queue_size(),
        "non_terminal_queue_size": _non_terminal_queue_size(),
    }

    if extra:
        payload["details"] = extra

    return payload
