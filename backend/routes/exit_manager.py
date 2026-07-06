from fastapi import APIRouter

from backend.exit_manager import run_exit_manager

router = APIRouter()


@router.post("/exit-manager/run")
def run_exit_manager_route():
    return run_exit_manager()