import random
import time

prices = {
    "AAPL": 182.0,
    "TSLA": 250.0,
    "NVDA": 450.0,
}

candles = {
    "AAPL": [],
    "TSLA": [],
    "NVDA": [],
}


def money(n):
    return round(float(n), 2)


def seed_candles():
    now = int(time.time()) - 1200 * 60

    for symbol, start in prices.items():
        price = start
        candles[symbol] = []

        for i in range(1200):
            open_price = price
            close_price = open_price + random.uniform(-1.25, 1.25)
            high = max(open_price, close_price) + random.uniform(0.2, 1.1)
            low = min(open_price, close_price) - random.uniform(0.2, 1.1)

            candles[symbol].append({
                "time": now + i * 60,
                "open": money(open_price),
                "high": money(high),
                "low": money(low),
                "close": money(close_price),
                "volume": random.randint(2500, 12000),
            })

            price = close_price

        prices[symbol] = money(price)


def update_market():
    for symbol in prices:
        last = candles[symbol][-1]
        next_time = last["time"] + 60

        open_price = last["close"]
        close_price = open_price + random.uniform(-1.4, 1.4)
        high = max(open_price, close_price) + random.uniform(0.15, 0.9)
        low = min(open_price, close_price) - random.uniform(0.15, 0.9)

        candle = {
            "time": next_time,
            "open": money(open_price),
            "high": money(high),
            "low": money(low),
            "close": money(close_price),
            "volume": random.randint(2500, 15000),
        }

        candles[symbol].append(candle)
        candles[symbol] = candles[symbol][-2000:]
        prices[symbol] = candle["close"]


seed_candles()