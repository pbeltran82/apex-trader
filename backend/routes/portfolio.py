from fastapi import APIRouter

from backend.portfolio import (
    trades,
    get_enriched_positions,
    buy_symbol,
    sell_symbol,
)
from backend.trade_history import record_trade
from backend.activity_log import log_event

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


@router.post("/sell/{symbol}")
def sell(symbol: str):
    result = sell_symbol(symbol)

    if result.get("ok"):
        record_trade(
            side="SELL",
            symbol=result["symbol"],
            qty=result["qty"],
            price=result["price"],
            total=result["total"],
            realized_pnl=result["realized_pnl"],
            source="MANUAL_SELL",
        )

        log_event(
            f"{result['symbol']} sold: {result['qty']} share(s) at ${result['price']}. P/L ${result['realized_pnl']}.",
            "SELL",
        )

    return result


@router.post("/close/{symbol}")
def close(symbol: str):
    return sell(symbol)