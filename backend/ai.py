from fastapi import APIRouter

from backend.market import candles
from backend.ai_engine import analyze_symbol

router = APIRouter()


@router.get("/analysis/{symbol}")
def analysis(symbol: str):
    symbol = symbol.upper()
    return analyze_symbol(symbol, candles.get(symbol, []))


@router.get("/ai/analyze/{symbol}")
def ai_analyze(symbol: str):
    symbol = symbol.upper()
    return analyze_symbol(symbol, candles.get(symbol, []))