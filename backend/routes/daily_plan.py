from fastapi import APIRouter

from backend.daily_plan import build_daily_plan

router = APIRouter()


@router.get("/daily-plan")
def daily_plan(limit: int = 3):
    return build_daily_plan(limit)