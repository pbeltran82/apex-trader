import core.env

from fastapi import FastAPI
from pydantic import BaseModel

from services.trading_service import TradingService
from services.history_service import HistoryService

app = FastAPI(
    title="Apex Trader API",
    version="1.0.0"
)

service = None
history = None


class TradeRequest(BaseModel):
    symbol: str
    qty: float
    side: str


@app.on_event("startup")
def startup():
    global service, history
    service = TradingService()
    history = HistoryService()


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "Apex Trader API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/account")
def account():
    return service.broker.get_account()


@app.get("/positions")
def positions():
    return service.broker.get_positions()


@app.get("/market/{symbol}")
def market(symbol: str):
    trade = service.broker.get_latest_trade(symbol.upper())

    return {
        "symbol": symbol.upper(),
        "price": float(trade.price),
        "size": trade.size,
        "timestamp": trade.timestamp,
    }


@app.get("/exposure")
def exposure():
    return service.get_exposure()


@app.get("/trades")
def trades():
    return history.get_trades()


@app.post("/trade")
def trade(request: TradeRequest):
    return service.trade(
        request.symbol,
        request.qty,
        request.side,
    )