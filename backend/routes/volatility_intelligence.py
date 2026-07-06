from fastapi import APIRouter

from backend.volatility_intelligence import analyze_volatility

router = APIRouter()


@router.get("/volatility/{symbol}")
def volatility(symbol: str):
    return analyze_volatility(symbol)