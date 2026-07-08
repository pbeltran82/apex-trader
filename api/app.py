from datetime import datetime
import threading
import time
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Kyle Apex Trader API")

# =========================
# CORS
# =========================
# Codespaces frontend/backend ports use different subdomains. Star patterns in
# allow_origins are not treated as wildcards by Starlette, so use regex instead.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"https://.*\.(app\.)?github\.dev",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# REQUEST MODELS
# =========================
class PriceUpdate(BaseModel):
    symbol: str
    price: float = Field(gt=0)


class ConfigUpdate(BaseModel):
    interval_seconds: Optional[int] = Field(default=None, ge=5, le=3600)
    min_confidence: Optional[int] = Field(default=None, ge=1, le=100)
    max_open_positions: Optional[int] = Field(default=None, ge=1, le=25)
    max_position_value: Optional[float] = Field(default=None, gt=0, le=100000)
    stop_loss_pct: Optional[float] = Field(default=None, gt=0, le=0.5)
    take_profit_pct: Optional[float] = Field(default=None, gt=0, le=2.0)


class ManualExitRequest(BaseModel):
    symbol: str
    reason: str = "Manual paper exit."


# =========================
# PAPER TRADING STATE
# =========================
account = {
    "balance": 10000.0,
    "equity": 10000.0,
    "buying_power": 10000.0,
    "currency": "USD",
    "mode": "paper",
}

positions: List[Dict] = []
trades: List[Dict] = []
equity_curve = [{"timestamp": datetime.utcnow().isoformat(), "equity": 10000.0}]
prices = {
    "AAPL": 190.12,
    "TSLA": 245.55,
    "NVDA": 455.10,
    "MSFT": 430.25,
    "AMZN": 185.40,
}
watchlist = ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN"]

# =========================
# AUTONOMOUS TRADER CONFIG
# =========================
config = {
    "interval_seconds": 60,
    "max_position_value": 1500.0,
    "max_open_positions": 3,
    "min_confidence": 70,
    "stop_loss_pct": 0.03,
    "take_profit_pct": 0.06,
}

_autonomous_thread: Optional[threading.Thread] = None
_autonomous_running = False
_autonomous_stop_event = threading.Event()
_autonomous_lock = threading.Lock()
_autonomous_state = {
    "running": False,
    "started_at": None,
    "stopped_at": None,
    "cycles": 0,
    "failures": 0,
    "last_run": None,
    "last_error": None,
    "last_status": "IDLE",
    "last_selected_symbol": None,
    "last_action": None,
    "last_reason": None,
}


# =========================
# HELPERS
# =========================
def _now() -> str:
    return datetime.utcnow().isoformat()


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def _open_position(symbol: str) -> Optional[Dict]:
    symbol = _normalize_symbol(symbol)
    return next((position for position in positions if position["symbol"] == symbol), None)


def _refresh_positions() -> None:
    for position in positions:
        current_price = prices.get(position["symbol"], position["entry_price"])
        position["current_price"] = round(current_price, 2)
        position["market_value"] = round(position["qty"] * current_price, 2)
        position["unrealized_pnl"] = round(
            (current_price - position["entry_price"]) * position["qty"], 2
        )
        position["unrealized_pnl_pct"] = round(
            ((current_price - position["entry_price"]) / position["entry_price"]) * 100, 2
        )


def _refresh_equity() -> float:
    _refresh_positions()
    market_value = sum(position["market_value"] for position in positions)
    account["equity"] = round(account["balance"] + market_value, 2)
    account["buying_power"] = round(account["balance"], 2)
    equity_curve.append({"timestamp": _now(), "equity": account["equity"]})
    if len(equity_curve) > 1000:
        del equity_curve[:-1000]
    return account["equity"]


def _record_trade(symbol: str, side: str, qty: int, price: float, reason: str, pnl: float = 0.0) -> Dict:
    trade = {
        "id": len(trades) + 1,
        "timestamp": _now(),
        "symbol": _normalize_symbol(symbol),
        "side": side,
        "qty": qty,
        "price": round(price, 2),
        "notional": round(qty * price, 2),
        "reason": reason,
        "realized_pnl": round(pnl, 2),
        "mode": "paper",
    }
    trades.append(trade)
    return trade


def _score_symbol(symbol: str) -> Dict:
    """Simple deterministic paper signal until live AI signals are wired in."""
    symbol = _normalize_symbol(symbol)
    price = prices[symbol]
    symbol_bias = sum(ord(char) for char in symbol) % 18
    confidence = 64 + symbol_bias

    if _open_position(symbol):
        return {
            "symbol": symbol,
            "action": "HOLD",
            "confidence": confidence,
            "approved": False,
            "reason": "Already holding this symbol.",
            "price": price,
        }

    approved = confidence >= config["min_confidence"]
    return {
        "symbol": symbol,
        "action": "BUY" if approved else "WAIT",
        "confidence": confidence,
        "approved": approved,
        "reason": "Confidence passed autonomous threshold." if approved else "Confidence below threshold.",
        "price": price,
    }


def _sell_position(symbol: str, reason: str) -> Dict:
    symbol = _normalize_symbol(symbol)
    position = _open_position(symbol)
    if not position:
        return {"ok": False, "message": f"No open paper position for {symbol}."}

    current_price = prices.get(symbol, position["entry_price"])
    qty = position["qty"]
    proceeds = round(qty * current_price, 2)
    pnl = round((current_price - position["entry_price"]) * qty, 2)

    account["balance"] = round(account["balance"] + proceeds, 2)
    positions.remove(position)
    trade = _record_trade(symbol, "SELL", qty, current_price, reason, pnl)
    _refresh_equity()

    return {
        "ok": True,
        "message": "Paper sell executed.",
        "symbol": symbol,
        "trade": trade,
        "realized_pnl": pnl,
    }


def _manage_positions() -> List[Dict]:
    updates = []
    _refresh_positions()

    for position in list(positions):
        symbol = position["symbol"]
        current_price = prices.get(symbol, position["entry_price"])
        entry_price = position["entry_price"]
        change_pct = (current_price - entry_price) / entry_price

        exit_reason = None
        if change_pct <= -config["stop_loss_pct"]:
            exit_reason = "Autonomous stop loss triggered."
        elif change_pct >= config["take_profit_pct"]:
            exit_reason = "Autonomous take profit triggered."

        if exit_reason:
            result = _sell_position(symbol, exit_reason)
            updates.append({**result, "pnl_pct": round(change_pct * 100, 2)})

    return updates


def _place_paper_buy(candidate: Dict) -> Dict:
    price = candidate["price"]
    qty = int(min(config["max_position_value"], account["buying_power"]) // price)

    if qty <= 0:
        return {"ok": False, "message": "Not enough buying power for at least one share."}

    notional = round(qty * price, 2)
    if notional > account["buying_power"]:
        return {"ok": False, "message": "Risk check failed: insufficient buying power."}

    if len(positions) >= config["max_open_positions"]:
        return {"ok": False, "message": "Risk check failed: maximum open positions reached."}

    account["balance"] = round(account["balance"] - notional, 2)

    position = {
        "symbol": candidate["symbol"],
        "qty": qty,
        "entry_price": round(price, 2),
        "current_price": round(price, 2),
        "market_value": notional,
        "opened_at": _now(),
        "stop_loss": round(price * (1 - config["stop_loss_pct"]), 2),
        "take_profit": round(price * (1 + config["take_profit_pct"]), 2),
        "unrealized_pnl": 0.0,
        "unrealized_pnl_pct": 0.0,
    }
    positions.append(position)
    trade = _record_trade(candidate["symbol"], "BUY", qty, price, candidate["reason"])
    _refresh_equity()

    return {"ok": True, "message": "Paper buy executed.", "position": position, "trade": trade}


def performance_summary() -> Dict:
    _refresh_equity()
    buys = [trade for trade in trades if trade["side"] == "BUY"]
    sells = [trade for trade in trades if trade["side"] == "SELL"]
    realized_pnl = round(sum(trade.get("realized_pnl", 0.0) for trade in sells), 2)
    unrealized_pnl = round(sum(position.get("unrealized_pnl", 0.0) for position in positions), 2)
    total_pnl = round(realized_pnl + unrealized_pnl, 2)
    wins = [trade for trade in sells if trade.get("realized_pnl", 0.0) > 0]
    losses = [trade for trade in sells if trade.get("realized_pnl", 0.0) < 0]
    win_rate = round((len(wins) / len(sells)) * 100, 2) if sells else 0.0

    return {
        "starting_equity": 10000.0,
        "current_equity": account["equity"],
        "realized_pnl": realized_pnl,
        "unrealized_pnl": unrealized_pnl,
        "total_pnl": total_pnl,
        "return_pct": round((account["equity"] - 10000.0) / 10000.0 * 100, 2),
        "trade_count": len(trades),
        "buy_count": len(buys),
        "sell_count": len(sells),
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate": win_rate,
        "open_positions": len(positions),
    }


def autonomous_status(extra: Optional[Dict] = None) -> Dict:
    _refresh_equity()
    payload = {
        **_autonomous_state,
        **config,
        "thread_alive": _autonomous_thread.is_alive() if _autonomous_thread else False,
        "open_positions": len(positions),
        "trade_count": len(trades),
        "account": account,
        "performance": performance_summary(),
    }
    if extra:
        payload["details"] = extra
    return payload


def run_autonomous_cycle() -> Dict:
    with _autonomous_lock:
        _autonomous_state["cycles"] += 1
        _autonomous_state["last_run"] = _now()
        _autonomous_state["last_error"] = None

        exit_updates = _manage_positions()
        _refresh_equity()

        if len(positions) >= config["max_open_positions"]:
            _autonomous_state.update({
                "last_status": "MAX_POSITIONS",
                "last_action": "MANAGED_ONLY",
                "last_selected_symbol": None,
                "last_reason": "Maximum open positions reached.",
            })
            return autonomous_status(extra={"exit_updates": exit_updates})

        candidates = sorted(
            (_score_symbol(symbol) for symbol in watchlist if symbol in prices),
            key=lambda row: row["confidence"],
            reverse=True,
        )
        selected = next((candidate for candidate in candidates if candidate["approved"]), None)

        if not selected:
            _autonomous_state.update({
                "last_status": "NO_CANDIDATE",
                "last_action": "NO_TRADE",
                "last_selected_symbol": None,
                "last_reason": "No candidate met autonomous confidence threshold.",
            })
            return autonomous_status(extra={"exit_updates": exit_updates, "candidates": candidates})

        order_result = _place_paper_buy(selected)
        _autonomous_state.update({
            "last_status": "CYCLE_COMPLETE" if order_result["ok"] else "REJECTED",
            "last_action": "BUY" if order_result["ok"] else "NO_TRADE",
            "last_selected_symbol": selected["symbol"],
            "last_reason": order_result["message"],
        })

        return autonomous_status(extra={
            "selected": selected,
            "order_result": order_result,
            "exit_updates": exit_updates,
            "candidates": candidates,
        })


def _autonomous_loop() -> None:
    global _autonomous_running

    while not _autonomous_stop_event.is_set():
        try:
            run_autonomous_cycle()
        except Exception as error:  # defensive guard for the background loop
            _autonomous_state["failures"] += 1
            _autonomous_state["last_error"] = str(error)
            _autonomous_state["last_status"] = "ERROR"
        _autonomous_stop_event.wait(config["interval_seconds"])

    _autonomous_running = False
    _autonomous_state["running"] = False


def start_autonomous_trader() -> Dict:
    global _autonomous_thread, _autonomous_running

    if _autonomous_running:
        return autonomous_status()

    _autonomous_stop_event.clear()
    _autonomous_running = True
    _autonomous_state.update({
        "running": True,
        "started_at": _now(),
        "stopped_at": None,
        "last_error": None,
        "last_status": "RUNNING",
        "last_action": "STARTED",
        "last_reason": "Autonomous paper trader started.",
    })

    _autonomous_thread = threading.Thread(target=_autonomous_loop, daemon=True)
    _autonomous_thread.start()
    return autonomous_status()


def stop_autonomous_trader() -> Dict:
    global _autonomous_running

    _autonomous_stop_event.set()
    _autonomous_running = False
    if _autonomous_thread and _autonomous_thread.is_alive():
        _autonomous_thread.join(timeout=2)

    _autonomous_state.update({
        "running": False,
        "stopped_at": _now(),
        "last_status": "STOPPED",
        "last_action": "STOPPED",
        "last_reason": "Autonomous paper trader stopped.",
    })
    return autonomous_status()


def reset_autonomous_trader() -> Dict:
    stop_autonomous_trader()
    positions.clear()
    trades.clear()
    equity_curve.clear()
    account.update({
        "balance": 10000.0,
        "equity": 10000.0,
        "buying_power": 10000.0,
        "currency": "USD",
        "mode": "paper",
    })
    equity_curve.append({"timestamp": _now(), "equity": account["equity"]})

    _autonomous_state.update({
        "running": False,
        "started_at": None,
        "stopped_at": None,
        "cycles": 0,
        "failures": 0,
        "last_run": None,
        "last_error": None,
        "last_status": "IDLE",
        "last_selected_symbol": None,
        "last_action": "RESET",
        "last_reason": "Autonomous paper trader reset.",
    })
    return autonomous_status()


def mission_control() -> Dict:
    return {
        "system": "Kyle Apex Trader",
        "mode": "paper",
        "status": autonomous_status(),
        "account": account,
        "positions": get_positions(),
        "recent_trades": trades[-10:],
        "prices": prices,
        "watchlist": watchlist,
        "performance": performance_summary(),
        "operator_notes": [
            "Paper trading only.",
            "Autonomous loop respects max open positions and per-position notional cap.",
            "Use /api/autonomous-trader/stop before changing strategy settings.",
        ],
    }


# =========================
# CORE ROUTES
# =========================
@app.get("/")
def root():
    return {"status": "ok", "service": "Kyle Apex Trader API"}


@app.get("/api/account")
def get_account():
    _refresh_equity()
    return account


@app.get("/api/positions")
def get_positions():
    _refresh_positions()
    return positions


@app.get("/api/trades")
def get_trades():
    return trades


@app.get("/api/equity")
def get_equity():
    _refresh_equity()
    return equity_curve


@app.get("/api/prices")
def get_prices():
    return prices


@app.post("/api/prices")
def update_price(payload: PriceUpdate):
    symbol = _normalize_symbol(payload.symbol)
    prices[symbol] = round(payload.price, 2)
    if symbol not in watchlist:
        watchlist.append(symbol)
    _manage_positions()
    _refresh_equity()
    return {"ok": True, "symbol": symbol, "price": prices[symbol], "account": account}


@app.get("/api/watchlist")
def get_watchlist():
    return watchlist


@app.get("/api/performance")
def get_performance():
    return performance_summary()


@app.get("/api/mission-control")
def get_mission_control():
    return mission_control()


# =========================
# AUTONOMOUS TRADER ROUTES
# =========================
@app.get("/api/autonomous-trader")
def autonomous_trader_status():
    return autonomous_status()


@app.get("/api/autonomous-trader/status")
def autonomous_trader_status_alias():
    return autonomous_status()


@app.get("/api/autonomous-trader/summary")
def autonomous_trader_summary():
    status = autonomous_status()
    return {
        "running": status["running"],
        "thread_alive": status["thread_alive"],
        "last_status": status["last_status"],
        "last_action": status["last_action"],
        "last_reason": status["last_reason"],
        "cycles": status["cycles"],
        "open_positions": status["open_positions"],
        "trade_count": status["trade_count"],
        "equity": status["account"]["equity"],
        "performance": status["performance"],
    }


@app.post("/api/autonomous-trader/start")
def start_autonomous_trader_route():
    return start_autonomous_trader()


@app.post("/api/autonomous-trader/stop")
def stop_autonomous_trader_route():
    return stop_autonomous_trader()


@app.post("/api/autonomous-trader/reset")
def reset_autonomous_trader_route():
    return reset_autonomous_trader()


@app.post("/api/autonomous-trader/run")
def run_autonomous_trader_route():
    return run_autonomous_cycle()


@app.post("/api/autonomous-trader/config")
def update_autonomous_config(payload: ConfigUpdate):
    updates = payload.dict(exclude_none=True)
    if not updates:
        return {"ok": True, "message": "No config changes supplied.", "config": config}

    key_map = {
        "interval_seconds": "interval_seconds",
        "min_confidence": "min_confidence",
        "max_open_positions": "max_open_positions",
        "max_position_value": "max_position_value",
        "stop_loss_pct": "stop_loss_pct",
        "take_profit_pct": "take_profit_pct",
    }
    for request_key, config_key in key_map.items():
        if request_key in updates:
            config[config_key] = updates[request_key]

    _autonomous_state["last_action"] = "CONFIG_UPDATED"
    _autonomous_state["last_reason"] = "Autonomous trader config updated."
    return {"ok": True, "config": config, "status": autonomous_status()}


@app.post("/api/autonomous-trader/exit")
def manual_exit(payload: ManualExitRequest):
    result = _sell_position(payload.symbol, payload.reason)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result["message"])
    _autonomous_state["last_action"] = "MANUAL_EXIT"
    _autonomous_state["last_reason"] = result["message"]
    return {"ok": True, "result": result, "status": autonomous_status()}


@app.post("/api/autonomous-trader/liquidate")
def liquidate_all_paper_positions():
    results = []
    for position in list(positions):
        results.append(_sell_position(position["symbol"], "Manual paper liquidation."))
    _autonomous_state["last_action"] = "LIQUIDATED"
    _autonomous_state["last_reason"] = "All paper positions liquidated."
    return {"ok": True, "results": results, "status": autonomous_status()}
