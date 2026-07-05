from fastapi import APIRouter

from backend.auto_exit_manager import (
    run_auto_exit_manager,
    get_auto_exit_status,
)

router = APIRouter()


@router.post("/auto-exit/run")
def run_auto_exit():
    return run_auto_exit_manager()


@router.get("/auto-exit/status")
def auto_exit_status():
    return get_auto_exit_status()