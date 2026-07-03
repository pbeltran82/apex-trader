from fastapi import APIRouter

from backend.market import prices, candles, update_market

router = APIRouter()


@router.get("/prices")
def get_prices():
    update_market()
    return prices


@router.get("/candles/{symbol}")
def get_candles(symbol: str):
    return candles.get(symbol.upper(), [])