import asyncio
from datetime import datetime

from backend.autopilot import run_autopilot_cycle, start_autopilot, stop_autopilot

scheduler_state = {
    "enabled": False,
    "running": False,
    "interval_seconds": 60,
    "started_at": None,
    "last_tick": None,
    "ticks": 0,
    "last_result": None,
}


async def autopilot_loop():
    scheduler_state["running"] = True
    scheduler_state["started_at"] = datetime.utcnow().isoformat()

    while scheduler_state["enabled"]:
        scheduler_state["ticks"] += 1
        scheduler_state["last_tick"] = datetime.utcnow().isoformat()

        result = run_autopilot_cycle()
        scheduler_state["last_result"] = result

        if result.get("action") == "RISK_SHUTDOWN":
            scheduler_state["enabled"] = False
            break

        await asyncio.sleep(scheduler_state["interval_seconds"])

    scheduler_state["running"] = False


def get_scheduler_status():
    return scheduler_state


def start_scheduler(interval_seconds=60):
    interval_seconds = int(interval_seconds)

    if interval_seconds < 10:
        interval_seconds = 10

    scheduler_state["enabled"] = True
    scheduler_state["interval_seconds"] = interval_seconds

    start_autopilot()

    return scheduler_state


def stop_scheduler():
    scheduler_state["enabled"] = False
    stop_autopilot()
    return scheduler_state