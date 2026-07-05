from fastapi import APIRouter

from backend.autopilot import (
    get_autopilot_status,
    start_autopilot,
    stop_autopilot,
    run_autopilot_cycle,
)

router = APIRouter()


@router.get("/autopilot/status")
def status():
    return get_autopilot_status()


@router.post("/autopilot/start")
def start():
    return start_autopilot()


@router.post("/autopilot/stop")
def stop():
    return stop_autopilot()


@router.post("/autopilot/run")
def run():
    return run_autopilot_cycle()