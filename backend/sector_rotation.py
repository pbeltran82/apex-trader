from datetime import datetime

from backend.market_data.service import get_price


SECTOR_MAP = {
    "Technology": ["MSFT", "AAPL", "NVDA", "AMD", "META", "GOOGL"],
    "Consumer": ["AMZN", "WMT", "COST", "HD", "MCD"],
    "Financials": ["JPM", "GS", "BAC", "MS"],
    "Healthcare": ["UNH", "LLY", "JNJ", "PFE"],
    "Energy": ["XOM", "CVX"],
    "Industrial": ["CAT", "BA", "GE"],
}


def classify_sector(sector, symbols):
    symbol_prices = {}

    for symbol in symbols:
        price = get_price(symbol)
        if price is not None:
            symbol_prices[symbol] = float(price)

    available = list(symbol_prices.keys())

    if not available:
        return {
            "sector": sector,
            "available": False,
            "score": 0,
            "bias": "UNKNOWN",
            "confidence_adjustment": 0,
            "allocation_multiplier": 1.0,
            "reason": "No symbols available for this sector.",
        }

    sector_prices = list(symbol_prices.values())
    avg_price = sum(sector_prices) / len(sector_prices)

    strength_score = 0

    if avg_price > 100:
        strength_score += 1

    if len(available) >= 3:
        strength_score += 1

    if avg_price > 250:
        strength_score += 1

    if strength_score >= 3:
        bias = "LEADING"
        confidence_adjustment = 4
        allocation_multiplier = 1.15
        reason = f"{sector} sector is leading."
    elif strength_score == 2:
        bias = "STRONG"
        confidence_adjustment = 2
        allocation_multiplier = 1.05
        reason = f"{sector} sector is strong."
    elif strength_score == 1:
        bias = "NEUTRAL"
        confidence_adjustment = 0
        allocation_multiplier = 1.0
        reason = f"{sector} sector is neutral."
    else:
        bias = "WEAK"
        confidence_adjustment = -4
        allocation_multiplier = 0.75
        reason = f"{sector} sector is weak."

    return {
        "sector": sector,
        "available": True,
        "symbols": available,
        "avg_price": round(avg_price, 2),
        "score": strength_score,
        "bias": bias,
        "confidence_adjustment": confidence_adjustment,
        "allocation_multiplier": allocation_multiplier,
        "reason": reason,
    }


def get_sector_rotation():
    sectors = {
        sector: classify_sector(sector, symbols)
        for sector, symbols in SECTOR_MAP.items()
    }

    ranked = sorted(
        sectors.values(),
        key=lambda x: x["score"],
        reverse=True,
    )

    return {
        "generated": datetime.utcnow().isoformat(),
        "leaders": ranked[:3],
        "laggards": ranked[-3:],
        "sectors": sectors,
    }


def get_sector_rotation_adjustment(sector):
    rotation = get_sector_rotation()
    sector_data = rotation["sectors"].get(sector)

    if not sector_data:
        return {
            "sector": sector,
            "confidence_adjustment": 0,
            "allocation_multiplier": 1.0,
            "reason": "No sector rotation data available.",
        }

    return {
        "sector": sector,
        "bias": sector_data["bias"],
        "confidence_adjustment": sector_data["confidence_adjustment"],
        "allocation_multiplier": sector_data["allocation_multiplier"],
        "reason": sector_data["reason"],
    }
