from datetime import datetime
import threading
import time
from typing import Dict, List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
# MOCK PAPER TRADING STATE
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
AUTONOMOUS_INTERVAL_SECONDS = 60
MAX_POSITION_VALUE = 1500.0
MAX_OPEN_POSITIONS = 3
MIN_CONFIDENCE = 70
STOP_LOSS_PCT = 0.03
TAKE_PROFIT_PCT = 0.06

_autonomous_thread: Optional[threading.Thread] = None
_autonomous_running = False
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
    "interval_seconds": AUTONOMOUS_INTERVAL_SECONDS,
    "min_confidence": MIN_CONFIDENCE,
    "max_open_positions": MAX_OPEN_POSITIONS,
    "max_position_value": MAX_POSITION_VALUE,
    "stop_loss_pct": STOP_LOSS_PCT,
    "take_profit_pct": TAKE_PROFIT_PCT,
}


# =========================
# HELPERS
# =========================
def _now() -> str:
    return datetime.utcnow().isoformat()


def _open_position(symbol: str) -> Optional[Dict]:
    return next((position for position in positions if position["symbol"] == symbol), None)


def _refresh_equity() -> float:
    market_value = sum(
        position["qty"] * prices.get(position["symbol"], position["entry_price"])
        for position in positions
    )
    account["equity"] = round(account["balance"] + market_value, 2)
    equity_curve.append({"timestamp": _now(), "equity": account["equity"]})
    return account["equity"]


def _record_trade(symbol: str, side: str, qty: int, price: float, reason: str) -> Dict:
    trade = {
        "id": len(trades) + 1,
        "timestamp": _now(),
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "price": round(price, 2),
        "notional": round(qty * price, 2),
        "reason": reason,
        "mode": "paper",
    }
    trades.append(trade)
    return trade


def _score_symbol(symbol: str) -> Dict:
    """Simple deterministic paper signal until live AI signals are wired in."""
    price = prices[symbol]
    # Creates stable but varied mock confidence per symbol without external data.
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

    approved = confidence >= MIN_CONFIDENCE
    return {
        "symbol": symbol,
        "action": "BUY" if approved else "WAIT",
        "confidence": confidence,
        "approved": approved,
        "reason": "Confidence passed autonomous threshold." if approved else "Confidence below threshold.",
        "price": price,
    }


def _manage_positions() -> List[Dict]:
    updates = []

    for position in list(positions):
        symbol = position["symbol"]
        current_price = prices.get(symbol, position["entry_price"])
        entry_price = position["entry_price"]
        change_pct = (current_price - entry_price) / entry_price

        exit_reason = None
        if change_pct <= -STOP_LOSS_PCT:
            exit_reason = "Autonomous stop loss triggered."
        elif change_pct >= TAKE_PROFIT_PCT:
            exit_reason = "Autonomous take profit triggered."

        if not exit_reason:
            continue

        qty = position["qty"]
        proceeds = qty * current_price
        account["balance"] = round(account["balance"] + proceeds, 2)
        account["buying_power"] = account["balance"]
        positions.remove(position)
        trade = _record_trade(symbol, "SELL", qty, current_price, exit_reason)
        updates.append({"symbol": symbol, "trade": trade, "pnl_pct": round(change_pct * 100, 2)})

    return updates


def _place_paper_buy(candidate: Dict) -> Dict:
    price = candidate["price"]
    qty = int(min(MAX_POSITION_VALUE, account["buying_power"]) // price)

    if qty <= 0:
        return {"ok": False, "message": "Not enough buying power for at least one share."}

    notional = round(qty * price, 2)
    if notional > account["buying_power"]:
        return {"ok": False, "message": "Risk check failed: insufficient buying power."}

    account["balance"] = round(account["balance"] - notional, 2)
    account["buying_power"] = account["balance"]

    position = {
        "symbol": candidate["symbol"],
        "qty": qty,
        "entry_price": round(price, 2),
        "current_price": round(price, 2),
        "market_value": notional,
        "opened_at": _now(),
        "stop_loss": round(price * (1 - STOP_LOSS_PCT), 2),
        "take_profit": round(price * (1 + TAKE_PROFIT_PCT), 2),
    }
    positions.append(position)
    trade = _record_trade(candidate["symbol"], "BUY", qty, price, candidate["reason"])

    return {"ok": True, "message": "Paper buy executed.", "position": position, "trade": trade}


def autonomous_status(extra: Optional[Dict] = None) -> Dict:
    payload = {
        **_autonomous_state,
        "thread_alive": _autonomous_thread.is_alive() if _autonomous_thread else False,
        "open_positions": len(positions),
        "trade_count": len(trades),
        "account": account,
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

        if len(positions) >= MAX_OPEN_POSITIONS:
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
        _refresh_equity()

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

    while _autonomous_running:
        try:
            run_autonomous_cycle()
        except Exception as error:  # defensive guard for the background loop
            _autonomous_state["failures"] += 1
            _autonomous_state["last_error"] = str(error)
            _autonomous_state["last_status"] = "ERROR"
        time.sleep(AUTONOMOUS_INTERVAL_SECONDS)


def start_autonomous_trader() -> Dict:
    global _autonomous_thread, _autonomous_running

    if _autonomous_running:
        return autonomous_status()

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

    _autonomous_running = False
    _autonomous_state.update({
        "running": False,
        "stopped_at": _now(),
        "last_status": "STOPPED",
        "last_action": "STOPPED",
        "last_reason": "Autonomous paper trader stopped.",
    })
    return autonomous_status()


def reset_autonomous_trader() -> Dict:
    global _autonomous_running

    _autonomous_running = False
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
    for position in positions:
        current_price = prices.get(position["symbol"], position["entry_price"])
        position["current_price"] = round(current_price, 2)
        position["market_value"] = round(position["qty"] * current_price, 2)
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


@app.get("/api/watchlist")
def get_watchlist():
    return watchlist


# =========================
# AUTONOMOUS TRADER ROUTES
# =========================
@app.get("/api/autonomous-trader")
def autonomous_trader_status():
    return autonomous_status()


@app.get("/api/autonomous-trader/status")
def autonomous_trader_status_alias():
    return autonomous_status()


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
