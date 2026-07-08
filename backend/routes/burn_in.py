from fastapi import APIRouter

from backend.burn_in import (
    start_burn_in,
    stop_burn_in,
    reset_burn_in,
    run_burn_in_check,
    status,
)

router = APIRouter()


@router.get("/burn-in")
def burn_in_status():
    return status()


@router.post("/burn-in/start")
def start():
    return start_burn_in()


@router.post("/burn-in/check")
def check():
    return run_burn_in_check()


@router.post("/burn-in/stop")
def stop():
    return stop_burn_in()


@router.post("/burn-in/reset")
def reset():
    return reset_burn_in()
