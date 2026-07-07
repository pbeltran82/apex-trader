from fastapi import APIRouter

from backend.market_data import service as market_data

router = APIRouter()


@router.get("/prices")
def get_prices():
    # Legacy endpoint kept for the existing frontend/components.
    # Internally this now flows through the provider-based market data service.
    return market_data.get_prices()


@router.get("/candles/{symbol}")
def get_candles(symbol: str):
    return market_data.get_candles(symbol.upper(), limit=2000)
