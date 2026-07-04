from backend.indicators import analyze


def money(n):
    return round(float(n), 2)


def clamp(value, low, high):
    return max(low, min(high, value))


def get_regime(ind):
    atr_pct = (ind["atr"] / ind["last_price"]) * 100 if ind["last_price"] else 0

    volatility = (
        "High Volatility" if atr_pct > 2.2 else
        "Low Volatility" if atr_pct < 0.7 else
        "Normal Volatility"
    )

    structure = "Trending" if "Bullish" in ind["trend"] or "Bearish" in ind["trend"] else "Ranging"

    return f"{structure} / {volatility}"


def score_market(ind):
    score = 0
    reasons = []
    blockers = []

    # Trend stack
    if ind["ema9"] > ind["ema20"] > ind["ema50"] > ind["ema200"]:
        score += 32
        reasons.append("EMA stack is strongly bullish.")
    elif ind["ema9"] > ind["ema20"] > ind["ema50"]:
        score += 20
        reasons.append("Short and medium-term EMAs are bullish.")
    elif ind["ema9"] < ind["ema20"] < ind["ema50"] < ind["ema200"]:
        score -= 32
        reasons.append("EMA stack is strongly bearish.")
    elif ind["ema9"] < ind["ema20"] < ind["ema50"]:
        score -= 20
        reasons.append("Short and medium-term EMAs are bearish.")
    else:
        reasons.append("EMA structure is mixed.")

    # Long-term filter
    if ind["last_price"] < ind["ema200"]:
        score -= 14
        blockers.append("Price is below the 200 EMA, so long trades need extra confirmation.")
    else:
        score += 8
        reasons.append("Price is above the 200 EMA.")

    # VWAP institutional filter
    if ind["last_price"] > ind["vwap"]:
        score += 14
        reasons.append("Price is trading above VWAP.")
    else:
        score -= 18
        blockers.append("Price is below VWAP, showing weak intraday/institutional confirmation.")

    # RSI
    rsi = ind["rsi"]
    if rsi >= 75:
        score -= 18
        blockers.append("RSI is extremely overbought.")
    elif rsi >= 70:
        score -= 12
        reasons.append("RSI is overbought.")
    elif rsi <= 25:
        score += 6
        blockers.append("RSI is extremely oversold; avoid chasing without reversal confirmation.")
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
        score += 14
        reasons.append("MACD is bullish with positive histogram.")
    elif ind["macd"] < ind["signal"] and ind["histogram"] < 0:
        score -= 14
        reasons.append("MACD is bearish with negative histogram.")
    else:
        reasons.append("MACD is mixed.")

    # Bollinger
    if ind["last_price"] > ind["bollinger_upper"]:
        score -= 6
        blockers.append("Price is extended above the upper Bollinger Band; breakout risk is elevated.")
    elif ind["last_price"] < ind["bollinger_lower"]:
        score -= 6
        blockers.append("Price is below the lower Bollinger Band; downside pressure is elevated.")
    else:
        reasons.append("Price is inside Bollinger Bands.")

    # ROC
    if ind["roc"] > 1:
        score += 7
        reasons.append("Rate of change is positive.")
    elif ind["roc"] < -1:
        score -= 7
        reasons.append("Rate of change is negative.")

    # OBV
    if ind["obv"] > 0:
        score += 8
        reasons.append("OBV shows net accumulation.")
    else:
        score -= 12
        blockers.append("OBV shows net distribution.")

    # Relative volume
    if ind["relative_volume"] > 1.5:
        score += 10
        reasons.append("Relative volume is elevated.")
    elif ind["relative_volume"] < 0.7:
        score -= 8
        blockers.append("Relative volume is weak.")
    else:
        reasons.append("Relative volume is normal.")

    # Crossover
    if ind["crossover"] == "bullish":
        score += 16
        reasons.append("Fresh bullish EMA crossover detected.")
    elif ind["crossover"] == "bearish":
        score -= 16
        blockers.append("Fresh bearish EMA crossover detected.")

    return score, reasons, blockers


def build_recommendation(score, blockers):
    major_blockers = len(blockers)

    if major_blockers >= 3 and score > 0:
        return "NEUTRAL"

    if score >= 70:
        return "STRONG BUY"
    if score >= 38:
        return "BUY WATCH"
    if score <= -70:
        return "STRONG SELL"
    if score <= -38:
        return "AVOID / SELL WATCH"
    return "NEUTRAL"


def build_risk(ind):
    atr_pct = (ind["atr"] / ind["last_price"]) * 100 if ind["last_price"] else 0
    risk = atr_pct * 20

    if ind["last_price"] > ind["bollinger_upper"] or ind["last_price"] < ind["bollinger_lower"]:
        risk += 14

    if ind["rsi"] > 75 or ind["rsi"] < 25:
        risk += 12

    if ind["relative_volume"] < 0.7:
        risk += 8

    return clamp(risk, 5, 100)


def build_probabilities(score):
    buy_probability = clamp(50 + score / 2, 5, 95)
    sell_probability = clamp(50 - score / 2, 5, 95)
    return money(buy_probability), money(sell_probability)


def build_position_size(risk_score, confidence):
    if confidence < 50:
        return 0

    base = 1.0
    if confidence >= 85:
        base = 1.25
    elif confidence >= 70:
        base = 1.0
    elif confidence >= 55:
        base = 0.5

    risk_adjustment = 1 - (risk_score / 125)
    return money(clamp(base * risk_adjustment, 0, 1.25))


def build_summary(symbol, recommendation, regime, ind, confidence):
    return (
        f"{symbol} is rated {recommendation} with {money(confidence)}% confidence. "
        f"The market regime is {regime}. Price is {money(ind['last_price'])}, "
        f"support is near {money(ind['support'])}, resistance is near {money(ind['resistance'])}, "
        f"RSI is {money(ind['rsi'])}, and price is "
        f"{'above' if ind['last_price'] > ind['vwap'] else 'below'} VWAP."
    )


def build_warnings(ind, blockers, risk_score, confidence):
    warnings = list(blockers)

    if risk_score > 70:
        warnings.append("High volatility. Reduce size or wait for confirmation.")

    if confidence < 50:
        warnings.append("Low confidence. Avoid autonomous execution.")

    return warnings


def analyze_symbol(symbol, candles):
    symbol = symbol.upper()

    if len(candles) < 220:
        return {"error": "Not enough candle history for AI engine"}

    ind = analyze(candles)
    score, reasons, blockers = score_market(ind)

    risk_score = build_risk(ind)
    confidence = clamp(55 + abs(score) * 0.55 - risk_score * 0.2 - len(blockers) * 4, 20, 95)
    recommendation = build_recommendation(score, blockers)
    buy_probability, sell_probability = build_probabilities(score)
    regime = get_regime(ind)

    return {
        "symbol": symbol,
        "recommendation": recommendation,
        "score": money(score),
        "confidence": money(confidence),
        "buy_probability": buy_probability,
        "sell_probability": sell_probability,
        "risk_score": money(risk_score),
        "suggested_position_size_pct": build_position_size(risk_score, confidence),

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
        "blockers": blockers,
        "warnings": build_warnings(ind, blockers, risk_score, confidence),
        "summary": build_summary(symbol, recommendation, regime, ind, confidence),
        "disclaimer": "AI-style technical analysis on simulated data. Not financial advice.",
    }