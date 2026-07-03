from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# =========================
# CORS (GLOBAL FIX)
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://*.github.dev",
        "https://*.app.github.dev"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# MOCK PAPER TRADING STATE
# =========================
account = {
    "balance": 10000,
    "equity": 10000,
    "buying_power": 10000
}

positions = []
trades = []
equity_curve = [{"equity": 10000}]
prices = {
    "AAPL": 190.12,
    "TSLA": 245.55,
    "NVDA": 455.10
}

# =========================
# ROUTES
# =========================

@app.get("/api/account")
def get_account():
    return account


@app.get("/api/positions")
def get_positions():
    return positions


@app.get("/api/trades")
def get_trades():
    return trades


@app.get("/api/equity")
def get_equity():
    return equity_curve


@app.get("/api/prices")
def get_prices():
    return prices


# health check
@app.get("/")
def root():
    return {"status": "ok"}