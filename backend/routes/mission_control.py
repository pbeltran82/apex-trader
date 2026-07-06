from fastapi import APIRouter

from backend.mission_control import build_mission_control

router = APIRouter()


@router.get("/mission-control")
def mission_control():
    return build_mission_control()