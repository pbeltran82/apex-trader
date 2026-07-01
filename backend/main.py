import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus

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

# ------------------------------------
# SAFETY CONFIG (single place to edit)
# ------------------------------------
MAX_ORDER_QTY = 10
MIN_CASH_BUFFER = 100.0
ALLOWED_SYMBOLS = None  # Set to a list like ["AAPL","TSLA","SPY"] to restrict, or None to allow all

class OrderRequest(BaseModel):
    symbol: str
    qty: float
    side: str
    type: str = "market"

# ------------------------------------
# CORE ENDPOINTS
# ------------------------------------

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

@app.get("/api/orders")
def get_orders(limit: int = 20):
    try:
        request = GetOrdersRequest(
            status=QueryOrderStatus.ALL,
            limit=min(limit, 50),
        )
        orders = client.get_orders(request)
        return [
            {
                "id": str(o.id),
                "symbol": o.symbol,
                "side": str(o.side),
                "qty": float(o.qty) if o.qty else None,
                "status": str(o.status),
                "filled_avg_price": float(o.filled_avg_price) if o.filled_avg_price else None,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in orders
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ------------------------------------
# ORDER PLACEMENT (with safety layer)
# ------------------------------------

@app.post("/api/paper-order")
def paper_order(order: OrderRequest):
    symbol = order.symbol.strip().upper()

    # Validate side
    if order.side not in ["buy", "sell"]:
        raise HTTPException(status_code=400, detail="Invalid side — must be 'buy' or 'sell'")

    # Validate qty
    if order.qty <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than 0")

    # Hard cap on order size
    if order.qty > MAX_ORDER_QTY:
        raise HTTPException(status_code=400, detail=f"Safety limit: max {MAX_ORDER_QTY} shares per order")

    # Symbol allowlist (if configured)
    if ALLOWED_SYMBOLS and symbol not in ALLOWED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"{symbol} is not in the allowed symbols list")

    # Reject if cash is too low (buy orders only)
    if order.side == "buy":
        try:
            account = client.get_account()
            if float(account.cash) < MIN_CASH_BUFFER:
                raise HTTPException(status_code=400, detail=f"Insufficient cash — minimum buffer is ${MIN_CASH_BUFFER}")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Could not verify account cash: {str(e)}")

    # Only market orders supported currently
    if order.type != "market":
        raise HTTPException(status_code=400, detail="Only 'market' order type is supported currently")

    try:
        order_data = MarketOrderRequest(
            symbol=symbol,
            qty=order.qty,
            side=OrderSide.BUY if order.side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
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
