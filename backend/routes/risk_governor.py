from fastapi import APIRouter

from backend.risk_governor import (
    get_risk_status,
    activate_manual_stop,
    clear_manual_stop,
)

router = APIRouter()


@router.get("/risk-governor/status")
def status():
    return get_risk_status()


@router.post("/risk-governor/stop")
def stop():
    return activate_manual_stop()


@router.post("/risk-governor/resume")
def resume():
    return clear_manual_stop()