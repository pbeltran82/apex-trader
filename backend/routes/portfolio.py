from fastapi import APIRouter

from backend.portfolio import trades, get_enriched_positions, buy_symbol

router = APIRouter()


@router.get("/positions")
def get_positions():
    return get_enriched_positions()


@router.get("/trades")
def get_trades():
    return trades


@router.post("/buy/{symbol}")
def buy(symbol: str):
    return buy_symbol(symbol)