from fastapi import APIRouter

from backend.daily_scheduler import run_daily_scheduler

router = APIRouter()


@router.post("/daily-scheduler/run")
def daily_scheduler():

    return run_daily_scheduler()