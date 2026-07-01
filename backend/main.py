import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from engine import DecisionEngine, EngineConfig

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

# Read-only market data client — never used for order execution
data_client = StockHistoricalDataClient(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY")
)

# Decision engine — instantiated once, reused across requests
engine = DecisionEngine(
    trading_client=client,
    data_client=data_client,
    config=EngineConfig(),
)

# ------------------------------------
# SAFETY CONFIG (single place to edit)
# ------------------------------------
MAX_ORDER_QTY       = 10      # max shares per single order
MIN_CASH_BUFFER     = 100.0   # minimum cash to keep at all times ($)
MAX_OPEN_POSITIONS  = 10      # max number of distinct holdings
MAX_POSITION_PCT    = 0.20    # max portfolio % in any one symbol (20%)
MAX_INVESTED_PCT    = 0.90    # max total equity deployed (90% — keep 10% cash)
ALLOWED_SYMBOLS     = None    # e.g. ["AAPL","TSLA","SPY"] or None for all

# ------------------------------------
# ORDER STATE NORMALIZER (truth layer)
# ------------------------------------
# Alpaca returns many raw status strings. We normalize them to 5 clean states
# so the rest of the system (and frontend) only needs to handle known values.

_PENDING_STATUSES = {
    "new", "accepted", "pending_new", "accepted_for_bidding",
    "pending_cancel", "pending_replace", "held",
}
_FILLED_STATUSES       = {"filled"}
_PARTIAL_STATUSES      = {"partially_filled"}
_CANCELED_STATUSES     = {"canceled", "done_for_day", "expired", "replaced", "stopped", "suspended", "calculated"}
_REJECTED_STATUSES     = {"rejected"}

def normalize_order_status(raw: str) -> str:
    """Map a raw Alpaca order status string to one of: pending | filled | partially_filled | canceled | rejected | unknown"""
    clean = raw.lower().replace("orderstatus.", "")
    if clean in _FILLED_STATUSES:
        return "filled"
    if clean in _PARTIAL_STATUSES:
        return "partially_filled"
    if clean in _PENDING_STATUSES:
        return "pending"
    if clean in _CANCELED_STATUSES:
        return "canceled"
    if clean in _REJECTED_STATUSES:
        return "rejected"
    return "unknown"

def format_order(o) -> dict:
    return {
        "id": str(o.id),
        "symbol": o.symbol,
        "side": str(o.side).replace("OrderSide.", "").lower(),
        "qty": float(o.qty) if o.qty else None,
        "filled_qty": float(o.filled_qty) if o.filled_qty else 0.0,
        "status": normalize_order_status(str(o.status)),
        "raw_status": str(o.status).replace("OrderStatus.", "").lower(),
        "filled_avg_price": float(o.filled_avg_price) if o.filled_avg_price else None,
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }

# ------------------------------------
# PORTFOLIO EXPOSURE HELPER
# ------------------------------------

def get_exposure_snapshot():
    """Return current account + position data used for exposure checks."""
    account = client.get_account()
    positions = client.get_all_positions()
    equity = float(account.equity)
    cash = float(account.cash)
    invested = sum(float(p.market_value) for p in positions)
    return {
        "account": account,
        "positions": positions,
        "equity": equity,
        "cash": cash,
        "invested": invested,
        "open_count": len(positions),
        "invested_pct": invested / equity if equity > 0 else 0,
    }

# ------------------------------------
# REQUEST MODELS
# ------------------------------------

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
            "status": str(account.status).replace("AccountStatus.", "").lower(),
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
        return [format_order(o) for o in orders]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/portfolio/exposure")
def get_exposure():
    """Snapshot of current portfolio risk exposure — use this to answer 'should I trade?'"""
    try:
        snap = get_exposure_snapshot()
        equity = snap["equity"]
        positions = snap["positions"]

        symbol_exposure = [
            {
                "symbol": p.symbol,
                "market_value": float(p.market_value),
                "pct_of_portfolio": float(p.market_value) / equity if equity > 0 else 0,
                "over_limit": (float(p.market_value) / equity) > MAX_POSITION_PCT if equity > 0 else False,
            }
            for p in positions
        ]

        return {
            "equity": equity,
            "cash": snap["cash"],
            "invested": snap["invested"],
            "invested_pct": round(snap["invested_pct"], 4),
            "open_positions": snap["open_count"],
            "limits": {
                "max_open_positions": MAX_OPEN_POSITIONS,
                "max_position_pct": MAX_POSITION_PCT,
                "max_invested_pct": MAX_INVESTED_PCT,
                "min_cash_buffer": MIN_CASH_BUFFER,
            },
            "breaches": {
                "too_many_positions": snap["open_count"] >= MAX_OPEN_POSITIONS,
                "over_invested": snap["invested_pct"] > MAX_INVESTED_PCT,
                "low_cash": snap["cash"] < MIN_CASH_BUFFER,
            },
            "symbol_exposure": symbol_exposure,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ------------------------------------
# DECISION ENGINE (thin wrapper only)
# ------------------------------------

@app.get("/api/decision/{symbol}")
def get_decision(symbol: str):
    try:
        result = engine.evaluate(symbol)
        return result.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ------------------------------------
# MARKET DATA (read-only layer)
# ------------------------------------

@app.get("/api/market/{symbol}")
def get_market_data(symbol: str):
    try:
        sym = symbol.upper()
        request = StockLatestTradeRequest(symbol_or_symbols=sym)
        trade_data = data_client.get_stock_latest_trade(request)
        trade = trade_data[sym]
        return {
            "symbol": sym,
            "price": float(trade.price),
            "size": float(trade.size),
            "exchange": trade.exchange,
            "timestamp": trade.timestamp.isoformat() if trade.timestamp else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ------------------------------------
# ORDER PLACEMENT (with safety layer)
# ------------------------------------

@app.post("/api/paper-order")
def paper_order(order: OrderRequest):
    symbol = order.symbol.strip().upper()

    if order.side not in ["buy", "sell"]:
        raise HTTPException(status_code=400, detail="Invalid side — must be 'buy' or 'sell'")

    if order.qty <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than 0")

    if order.qty > MAX_ORDER_QTY:
        raise HTTPException(status_code=400, detail=f"Safety limit: max {MAX_ORDER_QTY} shares per order")

    if ALLOWED_SYMBOLS and symbol not in ALLOWED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"{symbol} is not in the allowed symbols list")

    if order.type != "market":
        raise HTTPException(status_code=400, detail="Only 'market' order type is supported currently")

    # Portfolio exposure checks (buy orders only)
    if order.side == "buy":
        try:
            snap = get_exposure_snapshot()

            if snap["cash"] < MIN_CASH_BUFFER:
                raise HTTPException(status_code=400, detail=f"Insufficient cash — minimum buffer is ${MIN_CASH_BUFFER}")

            if snap["open_count"] >= MAX_OPEN_POSITIONS:
                raise HTTPException(status_code=400, detail=f"Exposure limit: already at max {MAX_OPEN_POSITIONS} open positions")

            if snap["invested_pct"] > MAX_INVESTED_PCT:
                raise HTTPException(status_code=400, detail=f"Exposure limit: {snap['invested_pct']*100:.1f}% of equity is already deployed (max {MAX_INVESTED_PCT*100:.0f}%)")

            # Per-symbol exposure check
            existing = next((p for p in snap["positions"] if p.symbol == symbol), None)
            if existing:
                current_pct = float(existing.market_value) / snap["equity"]
                if current_pct >= MAX_POSITION_PCT:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Exposure limit: {symbol} already at {current_pct*100:.1f}% of portfolio (max {MAX_POSITION_PCT*100:.0f}%)"
                    )

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Could not verify exposure: {str(e)}")

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
            "status": normalize_order_status(str(result.status)),
            "raw_status": str(result.status).replace("OrderStatus.", "").lower(),
            "symbol": result.symbol,
            "qty": float(result.qty),
            "side": str(result.side).replace("OrderSide.", "").lower(),
            "type": str(result.order_type).replace("OrderType.", "").lower(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
