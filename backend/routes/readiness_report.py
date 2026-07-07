from fastapi import APIRouter

from backend.readiness_report import (
    build_readiness_report,
)

router = APIRouter()


@router.get("/readiness-report")
def readiness_report():

    return build_readiness_report()