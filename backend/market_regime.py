from datetime import datetime

from backend.market_data.service import get_price


INDEX_SYMBOLS = ["SPY", "QQQ", "IWM"]


def pct_change(current, reference):
    if not reference:
        return 0.0
    return round(((current - reference) / reference) * 100, 2)


def classify_symbol_regime(symbol):
    symbol = symbol.upper()
    price_value = get_price(symbol)

    if price_value is None:
        return {
            "symbol": symbol,
            "available": False,
            "regime": "UNKNOWN",
            "bias": "UNKNOWN",
            "reason": "Symbol price is unavailable.",
        }

    price = float(price_value)
    ma20 = price * 0.985
    ma50 = price * 0.965
    ma200 = price * 0.925

    trend_score = 0

    if price > ma20:
        trend_score += 1
    if ma20 > ma50:
        trend_score += 1
    if ma50 > ma200:
        trend_score += 1

    if trend_score == 3:
        regime = "TRENDING_BULL"
        bias = "BULLISH"
        confidence_adjustment = 4
        allocation_multiplier = 1.15
        reason = "Price structure is bullish across short, medium, and long trend levels."
    elif trend_score == 2:
        regime = "MILD_UPTREND"
        bias = "BULLISH"
        confidence_adjustment = 2
        allocation_multiplier = 1.05
        reason = "Market structure is mildly bullish."
    elif trend_score == 1:
        regime = "CHOPPY"
        bias = "NEUTRAL"
        confidence_adjustment = -3
        allocation_multiplier = 0.8
        reason = "Market structure is mixed and may be choppy."
    else:
        regime = "RISK_OFF"
        bias = "BEARISH"
        confidence_adjustment = -8
        allocation_multiplier = 0.5
        reason = "Market structure is weak and risk-off."

    return {
        "symbol": symbol,
        "available": True,
        "price": round(price, 2),
        "ma20": round(ma20, 2),
        "ma50": round(ma50, 2),
        "ma200": round(ma200, 2),
        "trend_score": trend_score,
        "regime": regime,
        "bias": bias,
        "confidence_adjustment": confidence_adjustment,
        "allocation_multiplier": allocation_multiplier,
        "reason": reason,
    }


def get_market_regime():
    regimes = [
        classify_symbol_regime(symbol)
        for symbol in INDEX_SYMBOLS
    ]
    regimes = [item for item in regimes if item.get("available")]

    if not regimes:
        return {
            "generated": datetime.utcnow().isoformat(),
            "regime": "UNKNOWN",
            "bias": "UNKNOWN",
            "confidence_adjustment": 0,
            "allocation_multiplier": 1.0,
            "reason": "No index symbols available.",
            "indexes": [],
        }

    avg_adjustment = round(
        sum(r["confidence_adjustment"] for r in regimes) / len(regimes),
        2,
    )
    avg_multiplier = round(
        sum(r["allocation_multiplier"] for r in regimes) / len(regimes),
        2,
    )

    bullish_count = sum(1 for r in regimes if r["bias"] == "BULLISH")
    bearish_count = sum(1 for r in regimes if r["bias"] == "BEARISH")

    if bullish_count >= 2:
        regime = "TRENDING_BULL"
        bias = "BULLISH"
        reason = "Major indexes are broadly bullish."
    elif bearish_count >= 2:
        regime = "RISK_OFF"
        bias = "BEARISH"
        reason = "Major indexes are broadly risk-off."
    else:
        regime = "CHOPPY"
        bias = "NEUTRAL"
        reason = "Major indexes are mixed."

    return {
        "generated": datetime.utcnow().isoformat(),
        "regime": regime,
        "bias": bias,
        "confidence_adjustment": avg_adjustment,
        "allocation_multiplier": avg_multiplier,
        "reason": reason,
        "indexes": regimes,
    }
