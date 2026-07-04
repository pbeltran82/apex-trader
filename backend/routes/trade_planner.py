from fastapi import APIRouter

from backend.market import candles
from backend.portfolio import account
from backend.trade_planner import build_trade_plan

router = APIRouter()


@router.get("/trade-plan/{symbol}")
def trade_plan(symbol: str, risk_pct: float = 1.0):
    account_equity = account.get("equity", 10000)
    return build_trade_plan(
        symbol=symbol,
        candles=candles.get(symbol.upper(), []),
        account_equity=account_equity,
        risk_pct=risk_pct,
    )