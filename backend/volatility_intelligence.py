from backend import market


def calculate_atr(candles, period=14):
    if not candles or len(candles) < period + 1:
        return None

    true_ranges = []

    for i in range(1, len(candles)):
        high = float(candles[i]["high"])
        low = float(candles[i]["low"])
        prev_close = float(candles[i - 1]["close"])

        true_range = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close),
        )

        true_ranges.append(true_range)

    recent = true_ranges[-period:]

    if not recent:
        return None

    return round(sum(recent) / len(recent), 2)


def get_symbol_candles(symbol):
    symbol = symbol.upper()

    candles = getattr(market, "candles", None)
    if isinstance(candles, dict):
        return candles.get(symbol)

    historical_prices = getattr(market, "historical_prices", None)
    if isinstance(historical_prices, dict):
        return historical_prices.get(symbol)

    price_history = getattr(market, "price_history", None)
    if isinstance(price_history, dict):
        return price_history.get(symbol)

    return None


def classify_atr_volatility(symbol, price, atr):
    atr_pct = round((atr / price) * 100, 2) if price else 0.0

    if atr_pct >= 5:
        level = "HIGH"
        confidence_adjustment = -5
        allocation_multiplier = 0.65
    elif atr_pct >= 3:
        level = "ELEVATED"
        confidence_adjustment = -3
        allocation_multiplier = 0.8
    elif atr_pct <= 1:
        level = "LOW"
        confidence_adjustment = 1
        allocation_multiplier = 1.05
    else:
        level = "NORMAL"
        confidence_adjustment = 0
        allocation_multiplier = 1.0

    return {
        "symbol": symbol,
        "available": True,
        "method": "ATR",
        "price": round(price, 2),
        "atr": atr,
        "atr_pct": atr_pct,
        "volatility_level": level,
        "confidence_adjustment": confidence_adjustment,
        "allocation_multiplier": allocation_multiplier,
        "can_affect_decision": True,
        "reason": f"ATR volatility is {level.lower()} at {atr_pct}% of price.",
    }


def classify_proxy_volatility(symbol, price):
    if price >= 800:
        level = "HIGH"
        confidence_adjustment = -4
        allocation_multiplier = 0.7
        reason = "High-priced instrument; proxy suggests elevated risk."
    elif price >= 300:
        level = "ELEVATED"
        confidence_adjustment = -2
        allocation_multiplier = 0.85
        reason = "Price proxy suggests elevated risk."
    else:
        level = "NORMAL"
        confidence_adjustment = 0
        allocation_multiplier = 1.0
        reason = "Price proxy is normal."

    return {
        "symbol": symbol,
        "available": True,
        "method": "PRICE_PROXY",
        "price": round(price, 2),
        "atr": None,
        "atr_pct": None,
        "volatility_level": level,
        "confidence_adjustment": confidence_adjustment,
        "allocation_multiplier": allocation_multiplier,
        "can_affect_decision": False,
        "reason": reason + " Informational only until ATR candle data is available.",
    }


def analyze_volatility(symbol):
    symbol = symbol.upper()
    prices = getattr(market, "prices", {})

    if symbol not in prices:
        return {
            "symbol": symbol,
            "available": False,
            "method": "UNAVAILABLE",
            "volatility_level": "UNKNOWN",
            "confidence_adjustment": 0,
            "allocation_multiplier": 1.0,
            "can_affect_decision": False,
            "reason": "No price data available for volatility analysis.",
        }

    price = float(prices[symbol])
    candles = get_symbol_candles(symbol)
    atr = calculate_atr(candles)

    if atr:
        return classify_atr_volatility(symbol, price, atr)

    return classify_proxy_volatility(symbol, price)