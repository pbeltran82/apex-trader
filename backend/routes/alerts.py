from fastapi import APIRouter

from backend.alerts import build_alerts

router = APIRouter()


@router.get("/alerts")
def alerts():
    return build_alerts()