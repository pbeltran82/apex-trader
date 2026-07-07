from fastapi import APIRouter

from backend.health_monitor import build_health_monitor

router = APIRouter()


@router.get("/health-monitor")
def health_monitor():
    return build_health_monitor()