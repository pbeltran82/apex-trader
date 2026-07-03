from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import random

app = FastAPI()

# CORS FIX (this is REQUIRED — your earlier issue)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# SIMULATED STATE
# -----------------------------
account = {
    "balance": 10000.0,
    "equity": 10000.0
}

positions = []
trades = []

equity_curve = [{"time": 0, "equity": 10000.0}]

prices = {
    "AAPL": 182.0,
    "TSLA": 250.0,
    "NVDA": 450.0
}

tick = 0


# -----------------------------
# HELPERS
# -----------------------------
def calc_equity():
    unrealized = 0.0

    for p in positions:
        price = prices[p["symbol"]]
        unrealized += (price - p["avg_price"]) * p["qty"]

    return round(account["balance"] + unrealized, 2)


def update_curve():
    equity_curve.append({
        "time": tick,
        "equity": calc_equity()
    })


# -----------------------------
# PRICE SIMULATION
# -----------------------------
def update_prices():
    for k in prices:
        drift = random.uniform(-1.5, 1.5)
        prices[k] = round(prices[k] + drift, 2)


# -----------------------------
# ROUTES
# -----------------------------
@app.get("/api/account")
def get_account():
    account["equity"] = calc_equity()
    return account


@app.get("/api/positions")
def get_positions():
    enriched = []
    for p in positions:
        price = prices[p["symbol"]]
        pnl = round((price - p["avg_price"]) * p["qty"], 2)
        enriched.append({**p, "pnl": pnl})
    return enriched


@app.get("/api/trades")
def get_trades():
    return trades


@app.get("/api/prices")
def get_prices():
    return prices


@app.get("/api/equity")
def get_equity():
    return equity_curve


# -----------------------------
# SIMPLE BUY ENGINE
# -----------------------------
@app.post("/api/buy/{symbol}")
def buy(symbol: str):
    global tick

    price = prices[symbol]

    # check if exists
    for p in positions:
        if p["symbol"] == symbol:
            new_qty = p["qty"] + 1
            p["avg_price"] = round(
                (p["avg_price"] * p["qty"] + price) / new_qty, 2
            )
            p["qty"] = new_qty
            break
    else:
        positions.append({
            "symbol": symbol,
            "qty": 1,
            "avg_price": price
        })

    account["balance"] -= price

    trades.append({
        "side": "BUY",
        "symbol": symbol,
        "qty": 1,
        "price": price,
        "time": tick
    })

    tick += 1
    update_prices()
    update_curve()

    return {"ok": True}