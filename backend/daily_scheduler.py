from datetime import datetime

from backend.daily_plan import build_daily_plan
from backend.position_advisor import build_position_advice
from backend.execution_engine import queue_trade
from backend.execution_manager import manage_execution_queue


DEFAULT_EXECUTION_CYCLES = 3


def run_daily_scheduler(execution_cycles=DEFAULT_EXECUTION_CYCLES):
    """
    Build today's plan, queue the highest-ranked trade,
    and run the execution manager enough times to fill if conditions pass.
    """

    plan = build_daily_plan()
    top_picks = plan.get("top_picks", [])

    if not top_picks:
        return {
            "ok": False,
            "message": "No qualifying trades today.",
        }

    trade = top_picks[0]
    symbol = trade["symbol"]

    advice = build_position_advice(symbol)
    queued = queue_trade(symbol, advice)

    if not queued.get("ok"):
        return {
            "ok": False,
            "step": "queue",
            "selected_trade": symbol,
            "advice": advice,
            "result": queued,
        }

    executions = []

    for _ in range(int(execution_cycles)):
        executions.append(manage_execution_queue())

    return {
        "ok": True,
        "time": datetime.utcnow().isoformat(),
        "selected_trade": symbol,
        "plan": trade,
        "advice": advice,
        "queue": queued,
        "execution_cycles": execution_cycles,
        "executions": executions,
    }