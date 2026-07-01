import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

app = FastAPI(title="Apex Trader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = TradingClient(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY"),
    paper=True
)

class OrderRequest(BaseModel):
    symbol: str
    qty: float
    side: str
    type: str = "market"

@app.get("/")
def root():
    return {"status": "Apex Trader is running"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/api/account")
def get_account():
    try:
        account = client.get_account()
        return {
            "status": str(account.status),
            "cash": float(account.cash),
            "buying_power": float(account.buying_power),
            "portfolio_value": float(account.portfolio_value),
            "equity": float(account.equity),
            "currency": account.currency,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/positions")
def get_positions():
    try:
        positions = client.get_all_positions()
        return [
            {
                "symbol": p.symbol,
                "qty": float(p.qty),
                "market_value": float(p.market_value),
                "cost_basis": float(p.cost_basis),
                "unrealized_pl": float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc),
            }
            for p in positions
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/paper-order")
def paper_order(order: OrderRequest):
    if order.side not in ["buy", "sell"]:
        raise HTTPException(status_code=400, detail="Invalid side — must be 'buy' or 'sell'")

    if order.qty <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than 0")

    if order.qty > 10:
        raise HTTPException(status_code=400, detail="Safety limit: max 10 shares per order")

    try:
        side = OrderSide.BUY if order.side == "buy" else OrderSide.SELL

        if order.type == "market":
            order_data = MarketOrderRequest(
                symbol=order.symbol.upper(),
                qty=order.qty,
                side=side,
                time_in_force=TimeInForce.DAY,
            )
        else:
            raise HTTPException(status_code=400, detail="Only 'market' order type is supported currently")

        result = client.submit_order(order_data)

        return {
            "id": str(result.id),
            "status": str(result.status),
            "symbol": result.symbol,
            "qty": float(result.qty),
            "side": str(result.side),
            "type": str(result.order_type),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
