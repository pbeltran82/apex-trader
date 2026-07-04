from fastapi import APIRouter

from backend.activity_log import (
    get_activity,
    clear_activity,
)

router = APIRouter()


@router.get("/activity")
def activity():
    return get_activity()


@router.delete("/activity")
def clear():
    return clear_activity()