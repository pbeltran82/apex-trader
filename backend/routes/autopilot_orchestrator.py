from fastapi import APIRouter

from backend.autopilot_orchestrator import (
    get_history,
    run_autopilot_once,
    start_autopilot,
    stop_autopilot,
    status,
)

router = APIRouter()


@router.post("/autopilot-orchestrator/run-once")
def run_once():
    return run_autopilot_once()


@router.post("/autopilot-orchestrator/start")
def start():
    return start_autopilot()


@router.post("/autopilot-orchestrator/stop")
def stop():
    return stop_autopilot()


@router.get("/autopilot-orchestrator/status")
def get_status():
    return status()


@router.get("/autopilot-orchestrator/history")
def history(limit: int = 20):
    return get_history(limit)