import random
import time

from backend.universe import SYMBOLS
from backend.market_profiles import MARKET_PROFILES
from backend.market_state import BASE_PRICES, market_state

prices = {}
candles = {}


def money(n):
    return round(float(n), 2)


def get_profile(symbol):
    return MARKET_PROFILES.get(
        symbol,
        {
            "sector": "General",
            "trend": 0.04,
            "volatility": 1.0,
            "volume": 1.0,
        },
    )


def get_base_price(symbol):
    return BASE_PRICES.get(symbol, 100)


def regime_bias():
    regime = market_state.get("regime", "SIDEWAYS")

    if regime == "BULL":
        return 0.10
    if regime == "BEAR":
        return -0.10
    return 0.0


def make_candle(symbol, open_price, timestamp):
    profile = get_profile(symbol)
    base_price = get_base_price(symbol)

    trend = profile["trend"]
    volatility = profile["volatility"]
    volume_mult = profile["volume"]

    sentiment = market_state.get("sentiment", 0)
    regime = regime_bias()

    mean_reversion = -(open_price - base_price) * 0.012

    move = (
        trend
        + regime
        + sentiment * 0.25
        + random.gauss(0, volatility)
        + mean_reversion
    )

    close_price = max(1, open_price + move)

    wick_size = abs(random.gauss(0.45, 0.25)) * volatility
    high = max(open_price, close_price) + wick_size
    low = max(1, min(open_price, close_price) - wick_size)

    base_volume = random.randint(2500, 12000)
    volume = int(base_volume * volume_mult)

    return {
        "time": timestamp,
        "open": money(open_price),
        "high": money(high),
        "low": money(low),
        "close": money(close_price),
        "volume": volume,
    }


for symbol in SYMBOLS:
    prices[symbol] = money(get_base_price(symbol) * random.uniform(0.96, 1.04))
    candles[symbol] = []


def seed_candles():
    now = int(time.time()) - 1200 * 60

    for symbol in SYMBOLS:
        price = prices[symbol]
        candles[symbol] = []

        for i in range(1200):
            candle = make_candle(symbol, price, now + i * 60)
            candles[symbol].append(candle)
            price = candle["close"]

        prices[symbol] = money(price)


def update_market():
    market_state["sentiment"] += random.uniform(-0.05, 0.05)
    market_state["sentiment"] = max(-1.0, min(1.0, market_state["sentiment"]))

    for symbol in SYMBOLS:
        if not candles[symbol]:
            continue

        last = candles[symbol][-1]
        next_time = last["time"] + 60

        candle = make_candle(symbol, last["close"], next_time)

        candles[symbol].append(candle)
        candles[symbol] = candles[symbol][-2000:]
        prices[symbol] = candle["close"]


seed_candles()