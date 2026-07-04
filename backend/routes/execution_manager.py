from fastapi import APIRouter

from backend.execution_manager import manage_execution_queue

router = APIRouter()


@router.post("/execution-manager/run")
def run_execution_manager():
    return manage_execution_queue()