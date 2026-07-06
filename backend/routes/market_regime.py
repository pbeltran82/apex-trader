from fastapi import APIRouter

from backend.market_regime import get_market_regime

router = APIRouter()


@router.get("/market-regime")
def market_regime():
    return get_market_regime()