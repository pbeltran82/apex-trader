from fastapi import APIRouter

from backend.market_data import service as market_data

router = APIRouter()


@router.get("/market-data/status")
def market_data_status():
    return market_data.provider_status()


@router.post("/market-data/refresh")
def refresh_market_data():
    return market_data.refresh()


@router.get("/market-data/watchlist")
def market_data_watchlist():
    return market_data.get_watchlist()


@router.get("/market-data/prices")
def market_data_prices():
    return market_data.get_prices()


@router.get("/market-data/price/{symbol}")
def market_data_price(symbol: str):
    return {
        "symbol": symbol.upper(),
        "price": market_data.get_price(symbol),
    }


@router.get("/market-data/quote/{symbol}")
def market_data_quote(symbol: str):
    return market_data.get_quote(symbol)


@router.get("/market-data/snapshot/{symbol}")
def market_data_snapshot(symbol: str):
    return market_data.get_snapshot(symbol)


@router.get("/market-data/candles/{symbol}")
def market_data_candles(symbol: str, limit: int = 120):
    return market_data.get_candles(symbol, limit=limit)
