from fastapi import APIRouter

from backend.autonomous_trader import (
    reset_autonomous_trader,
    run_autonomous_cycle,
    start_autonomous_trader,
    status,
    stop_autonomous_trader,
)

router = APIRouter()


@router.get("/autonomous-trader")
def autonomous_trader_status():
    return status()


@router.get("/autonomous-trader/status")
def autonomous_trader_status_alias():
    return status()


@router.post("/autonomous-trader/start")
def start():
    return start_autonomous_trader()


@router.post("/autonomous-trader/stop")
def stop():
    return stop_autonomous_trader()


@router.post("/autonomous-trader/reset")
def reset():
    return reset_autonomous_trader()


@router.post("/autonomous-trader/run")
def run():
    return run_autonomous_cycle()
