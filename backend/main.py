import os
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Apex Trader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_PAPER = os.getenv("ALPACA_PAPER", "true").lower() == "true"
ALPACA_BASE_URL = "https://paper-api.alpaca.markets" if ALPACA_PAPER else "https://api.alpaca.markets"

ALPACA_HEADERS = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}

@app.get("/")
def root():
    return {"status": "Apex Trader is running"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/api/account")
def get_account():
    response = requests.get(f"{ALPACA_BASE_URL}/v2/account", headers=ALPACA_HEADERS)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    data = response.json()
    return {
        "account_number": data.get("account_number"),
        "status": data.get("status"),
        "cash": float(data.get("cash", 0)),
        "buying_power": float(data.get("buying_power", 0)),
        "portfolio_value": float(data.get("portfolio_value", 0)),
        "equity": float(data.get("equity", 0)),
        "long_market_value": float(data.get("long_market_value", 0)),
        "short_market_value": float(data.get("short_market_value", 0)),
        "daytrade_count": data.get("daytrade_count", 0),
        "pattern_day_trader": data.get("pattern_day_trader", False),
        "trading_blocked": data.get("trading_blocked", False),
        "paper": ALPACA_PAPER,
    }
