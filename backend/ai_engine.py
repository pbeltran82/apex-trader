from backend.indicators import analyze


def money(n):
    return round(float(n), 2)


def clamp(value, low, high):
    return max(low, min(high, value))


def get_regime(ind):
    trend = ind["trend"]
    atr_pct = (ind["atr"] / ind["last_price"]) * 100 if ind["last_price"] else 0

    if atr_pct > 2.2:
        volatility = "High Volatility"
    elif atr_pct < 0.7:
        volatility = "Low Volatility"
    else:
        volatility = "Normal Volatility"

    if "Bullish" in trend or "Bearish" in trend:
        structure = "Trending"
    else:
        structure = "Ranging"

    return f"{structure} / {volatility}"


def score_market(ind):
    score = 0
    reasons = []

    # Trend stack
    if ind["ema9"] > ind["ema20"] > ind["ema50"] > ind["ema200"]:
        score += 30
        reasons.append("EMA stack is strongly bullish.")
    elif ind["ema9"] > ind["ema20"] > ind["ema50"]:
        score += 22
        reasons.append("Short and medium-term EMAs are bullish.")
    elif ind["ema9"] < ind["ema20"] < ind["ema50"] < ind["ema200"]:
        score -= 30
        reasons.append("EMA stack is strongly bearish.")
    elif ind["ema9"] < ind["ema20"] < ind["ema50"]:
        score -= 22
        reasons.append("Short and medium-term EMAs are bearish.")
    else:
        reasons.append("EMA structure is mixed.")

    # VWAP
    if ind["last_price"] > ind["vwap"]:
        score += 10
        reasons.append("Price is trading above VWAP.")
    else:
        score -= 10
        reasons.append("Price is trading below VWAP.")

    # RSI
    rsi = ind["rsi"]
    if rsi >= 70:
        score -= 10
        reasons.append("RSI is overbought.")
    elif rsi <= 30:
        score += 10
        reasons.append("RSI is oversold and may attract mean-reversion buyers.")
    elif rsi > 55:
        score += 12
        reasons.append("RSI supports bullish momentum.")
    elif rsi < 45:
        score -= 12
        reasons.append("RSI confirms weak momentum.")
    else:
        reasons.append("RSI is neutral.")

    # MACD
    if ind["macd"] > ind["signal"] and ind["histogram"] > 0:
        score += 15
        reasons.append("MACD is bullish with positive histogram.")
    elif ind["macd"] < ind["signal"] and ind["histogram"] < 0:
        score -= 15
        reasons.append("MACD is bearish with negative histogram.")
    else:
        reasons.append("MACD is mixed.")

    # Bollinger position
    if ind["last_price"] > ind["bollinger_upper"]:
        score += 8
        reasons.append("Price is breaking above the upper Bollinger Band.")
    elif ind["last_price"] < ind["bollinger_lower"]:
        score -= 8
        reasons.append("Price is below the lower Bollinger Band.")
    else:
        reasons.append("Price is inside Bollinger Bands.")

    # ROC
    if ind["roc"] > 1:
        score += 8
        reasons.append("Rate of change is positive.")
    elif ind["roc"] < -1:
        score -= 8
        reasons.append("Rate of change is negative.")

    # OBV rough confirmation
    if ind["obv"] > 0:
        score += 5
        reasons.append("OBV shows net accumulation.")
    else:
        score -= 5
        reasons.append("OBV shows net distribution.")

    # Relative volume
    if ind["relative_volume"] > 1.5:
        score += 8
        reasons.append("Relative volume is elevated.")
    elif ind["relative_volume"] < 0.7:
        score -= 4
        reasons.append("Relative volume is weak.")
    else:
        reasons.append("Relative volume is normal.")

    # Crossovers
    if ind["crossover"] == "bullish":
        score += 15
        reasons.append("Fresh bullish EMA crossover detected.")
    elif ind["crossover"] == "bearish":
        score -= 15
        reasons.append("Fresh bearish EMA crossover detected.")

    return score, reasons


def build_recommendation(score):
    if score >= 65:
        return "STRONG BUY"
    if score >= 30:
        return "BUY WATCH"
    if score <= -65:
        return "STRONG SELL"
    if score <= -30:
        return "AVOID / SELL WATCH"
    return "NEUTRAL"


def build_risk(ind):
    atr_pct = (ind["atr"] / ind["last_price"]) * 100 if ind["last_price"] else 0
    volatility_component = atr_pct * 18

    rsi_component = 0
    if ind["rsi"] > 75 or ind["rsi"] < 25:
        rsi_component = 12

    band_component = 0
    if ind["last_price"] > ind["bollinger_upper"] or ind["last_price"] < ind["bollinger_lower"]:
        band_component = 10

    risk = volatility_component + rsi_component + band_component
    return clamp(risk, 5, 100)


def build_position_size(risk_score, confidence):
    if confidence < 45:
        return 0

    base = 1.0

    if confidence >= 80:
        base = 1.25
    elif confidence >= 65:
        base = 1.0
    elif confidence >= 50:
        base = 0.5

    risk_adjustment = 1 - (risk_score / 140)
    size_pct = clamp(base * risk_adjustment, 0, 1.25)

    return money(size_pct)


def build_probabilities(score):
    buy_probability = clamp(50 + score / 2, 5, 95)
    sell_probability = clamp(50 - score / 2, 5, 95)
    return money(buy_probability), money(sell_probability)


def build_summary(symbol, recommendation, regime, ind, confidence):
    return (
        f"{symbol} is rated {recommendation} with {money(confidence)}% confidence. "
        f"The current market regime is {regime}. "
        f"Price is {money(ind['last_price'])}, with support near {money(ind['support'])} "
        f"and resistance near {money(ind['resistance'])}. "
        f"RSI is {money(ind['rsi'])}, MACD histogram is {money(ind['histogram'])}, "
        f"and price is {'above' if ind['last_price'] > ind['vwap'] else 'below'} VWAP."
    )


def analyze_symbol(symbol, candles):
    symbol = symbol.upper()

    if len(candles) < 220:
        return {"error": "Not enough candle history for AI engine"}

    ind = analyze(candles)
    score, reasons = score_market(ind)

    recommendation = build_recommendation(score)
    risk_score = build_risk(ind)
    confidence = clamp(55 + abs(score) * 0.65 - risk_score * 0.15, 20, 95)
    buy_probability, sell_probability = build_probabilities(score)
    regime = get_regime(ind)
    suggested_size = build_position_size(risk_score, confidence)

    return {
        "symbol": symbol,
        "recommendation": recommendation,
        "score": money(score),
        "confidence": money(confidence),
        "buy_probability": buy_probability,
        "sell_probability": sell_probability,
        "risk_score": money(risk_score),
        "suggested_position_size_pct": suggested_size,

        "market_regime": regime,
        "trend": ind["trend"],
        "crossover": ind["crossover"],

        "last_price": money(ind["last_price"]),
        "support": money(ind["support"]),
        "resistance": money(ind["resistance"]),

        "ema9": money(ind["ema9"]),
        "ema20": money(ind["ema20"]),
        "ema50": money(ind["ema50"]),
        "ema200": money(ind["ema200"]),
        "vwap": money(ind["vwap"]),

        "rsi": money(ind["rsi"]),
        "macd": money(ind["macd"]),
        "signal": money(ind["signal"]),
        "histogram": money(ind["histogram"]),
        "atr": money(ind["atr"]),
        "volatility": money(ind["volatility"]),
        "relative_volume": money(ind["relative_volume"]),
        "roc": money(ind["roc"]),

        "bollinger_upper": money(ind["bollinger_upper"]),
        "bollinger_middle": money(ind["bollinger_middle"]),
        "bollinger_lower": money(ind["bollinger_lower"]),

        "reasoning": reasons,
        "summary": build_summary(symbol, recommendation, regime, ind, confidence),
        "warnings": build_warnings(ind, risk_score, confidence),
        "disclaimer": "AI-style technical analysis on simulated data. Not financial advice.",
    }


def build_warnings(ind, risk_score, confidence):
    warnings = []

    if risk_score > 70:
        warnings.append("High volatility. Reduce size or wait for confirmation.")

    if confidence < 45:
        warnings.append("Low confidence. Avoid autonomous execution.")

    if ind["relative_volume"] < 0.7:
        warnings.append("Weak relative volume. Signal confirmation is limited.")

    if ind["rsi"] > 75:
        warnings.append("RSI is extremely overbought.")
    elif ind["rsi"] < 25:
        warnings.append("RSI is extremely oversold.")

    return warnings