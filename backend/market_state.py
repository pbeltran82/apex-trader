import random

MARKET_REGIMES = [
    "BULL",
    "BEAR",
    "SIDEWAYS",
]

market_state = {
    "regime": random.choice(MARKET_REGIMES),
    "sentiment": random.uniform(-1.0, 1.0),
    "volatility_multiplier": 1.0,
}

BASE_PRICES = {
    "AAPL": 210,
    "MSFT": 520,
    "NVDA": 175,
    "AMD": 155,
    "META": 740,
    "AMZN": 235,
    "GOOGL": 205,
    "AVGO": 320,
    "TSLA": 320,
    "NFLX": 1350,
    "PLTR": 150,
    "SMCI": 65,
    "ARM": 165,
    "QCOM": 175,
    "MU": 145,
    "INTC": 28,
    "TXN": 215,
    "AMAT": 205,
    "LRCX": 98,
    "KLAC": 930,
    "JPM": 305,
    "BAC": 52,
    "GS": 745,
    "MS": 165,
    "LLY": 820,
    "UNH": 330,
    "COST": 1010,
    "WMT": 108,
    "HD": 375,
    "MCD": 305,
    "XOM": 112,
    "CVX": 158,
    "SPY": 625,
    "QQQ": 565,
    "IWM": 225,
}