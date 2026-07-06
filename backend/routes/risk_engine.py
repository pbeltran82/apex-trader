from fastapi import APIRouter

from backend.risk_engine import build_risk_engine

router = APIRouter()


@router.get("/risk-engine")
def risk_engine():
    return build_risk_engine()