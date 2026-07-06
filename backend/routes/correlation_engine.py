from fastapi import APIRouter

from backend.correlation_engine import analyze_correlation_risk

router = APIRouter()


@router.get("/correlation-risk/{symbol}")
def correlation_risk(symbol: str):
    return analyze_correlation_risk(symbol)