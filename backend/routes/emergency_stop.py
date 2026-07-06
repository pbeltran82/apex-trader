from fastapi import APIRouter

from backend.emergency_stop import (
    activate_emergency_stop,
    clear_emergency_stop,
    status,
)

router = APIRouter()


@router.get("/emergency-stop")
def get_emergency_stop():
    return status()


@router.post("/emergency-stop")
def activate(reason: str = "Manual emergency stop activated."):
    return activate_emergency_stop(reason)


@router.delete("/emergency-stop")
def clear():
    return clear_emergency_stop()