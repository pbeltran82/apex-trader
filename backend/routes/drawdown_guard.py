from fastapi import APIRouter

from backend.drawdown_guard import (
    get_drawdown_status,
    reset_peak_equity,
)

router = APIRouter()


@router.get("/drawdown")
def drawdown():
    return get_drawdown_status()


@router.post("/drawdown/reset")
def reset_drawdown():
    return reset_peak_equity()