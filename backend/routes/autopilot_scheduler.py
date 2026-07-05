import asyncio

from fastapi import APIRouter

from backend.autopilot_scheduler import (
    autopilot_loop,
    get_scheduler_status,
    start_scheduler,
    stop_scheduler,
)

router = APIRouter()


@router.get("/autopilot-scheduler/status")
def status():
    return get_scheduler_status()


@router.post("/autopilot-scheduler/start")
async def start(interval_seconds: int = 60):
    state = start_scheduler(interval_seconds)

    if not state["running"]:
        asyncio.create_task(autopilot_loop())

    return state


@router.post("/autopilot-scheduler/stop")
def stop():
    return stop_scheduler()