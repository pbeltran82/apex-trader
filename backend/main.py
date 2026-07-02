import os
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from engine import DecisionEngine, EngineConfig, PipelineTrace, TradeAttribution
from backtest import BacktestEngine, BacktestConfig

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
def get_decision(symbol: str, debug: bool = False, attribution: bool = False):
    try:
        if debug:
            return engine.evaluate_debug(symbol).to_dict()
        if attribution:
            decision, attr = engine.evaluate_attributed(symbol)
            return {**decision.to_dict(), "attribution": attr.to_dict()}
        return engine.evaluate(symbol).to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------
# SCAN (parallel ranking layer)
# ------------------------------------

MAX_SCAN_SYMBOLS = 50
SCAN_TIMEOUT_SECS = 12  # per-symbol wall time before it's marked as error


class ScanRequest(BaseModel):
    symbols: list[str] = Field(..., min_length=1, max_length=MAX_SCAN_SYMBOLS)
    debug: bool = False


def _rank(results: list[dict]) -> list[dict]:
    """
    Ranking is a pure post-process step, separate from evaluation.
    Rule: actionable signals (buy/sell) first, then sort all by confidence_score desc.
    Rank 1 = highest priority opportunity. risk_blocked rows sort to the bottom.
    """
    def sort_key(r):
        is_actionable = r["action"] in {"buy", "sell"} and not r["risk_blocked"]
        return (0 if is_actionable else 1, -r["confidence_score"])

    sorted_results = sorted(results, key=sort_key)
    for i, r in enumerate(sorted_results):
        r["rank"] = i + 1
    return sorted_results


@app.post("/api/scan")
def scan(request: ScanRequest):
    symbols = [s.upper().strip() for s in request.symbols]
    scan_time = datetime.now(timezone.utc).isoformat()

    raw_results: dict[str, dict] = {}

    def evaluate_one(sym: str) -> tuple[str, dict]:
        try:
            if request.debug:
                trace = engine.evaluate_debug(sym)
                d = trace.decision
                return sym, {
                    "symbol": sym,
                    "action": d["action"],
                    "confidence": d["confidence"],
                    "confidence_score": d["confidence_score"],
                    "risk_blocked": trace.risk["blocked"],
                    "reason": d["reason"],
                    "pipeline": trace.to_dict(),
                    "error": None,
                }
            else:
                decision = engine.evaluate(sym)
                return sym, {
                    "symbol": sym,
                    "action": decision.action,
                    "confidence": decision.confidence,
                    "confidence_score": decision.confidence_score,
                    "risk_blocked": decision.action == "hold" and decision.confidence == "high",
                    "reason": decision.reason,
                    "error": None,
                }
        except Exception as e:
            return sym, {
                "symbol": sym,
                "action": "error",
                "confidence": "low",
                "confidence_score": 0.0,
                "risk_blocked": False,
                "reason": str(e),
                "error": str(e),
            }

    with ThreadPoolExecutor(max_workers=min(len(symbols), 10)) as pool:
        futures = {pool.submit(evaluate_one, sym): sym for sym in symbols}
        for future in as_completed(futures, timeout=SCAN_TIMEOUT_SECS * len(symbols)):
            sym, result = future.result()
            raw_results[sym] = result

    results = _rank(list(raw_results.values()))

    actionable = [r for r in results if r["action"] in {"buy", "sell"} and not r["risk_blocked"]]

    return {
        "scan_time": scan_time,
        "total": len(results),
        "actionable_count": len(actionable),
        "results": results,
    }


# ------------------------------------
# BACKTEST
# ------------------------------------

bt_engine = BacktestEngine(data_client=data_client, engine_config=EngineConfig())


class BacktestRequest(BaseModel):
    symbol: str
    start: str = Field(..., description="ISO date, e.g. 2024-01-01")
    end: str = Field(..., description="ISO date, e.g. 2024-12-31")
    initial_cash: float = Field(default=100_000.0, gt=0)
    shares_per_trade: int = Field(default=1, ge=1, le=100)


@app.post("/api/backtest")
def run_backtest(request: BacktestRequest):
    try:
        start_dt = datetime.fromisoformat(request.start).replace(tzinfo=timezone.utc)
        end_dt = datetime.fromisoformat(request.end).replace(tzinfo=timezone.utc)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid date format: {e}")

    if end_dt <= start_dt:
        raise HTTPException(status_code=422, detail="end must be after start")
    if (end_dt - start_dt).days < 30:
        raise HTTPException(status_code=422, detail="Date range must be at least 30 days")

    try:
        result = bt_engine.run(BacktestConfig(
            symbol=request.symbol,
            start=start_dt,
            end=end_dt,
            initial_cash=request.initial_cash,
            shares_per_trade=request.shares_per_trade,
        ))
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
