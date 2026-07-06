from fastapi import APIRouter

from backend.broker_health import (
    status,
    heartbeat,
    disconnect,
    reconnect,
)

router = APIRouter()


@router.get("/broker-health")
def broker_health():
    return status()


@router.post("/broker-health/heartbeat")
def broker_heartbeat():
    return heartbeat()


@router.post("/broker-health/disconnect")
def broker_disconnect(
    reason: str = "Manual disconnect",
):
    return disconnect(reason)


@router.post("/broker-health/reconnect")
def broker_reconnect():
    return reconnect()