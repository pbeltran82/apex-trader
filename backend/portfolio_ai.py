from backend.portfolio import account, positions
from backend.market import prices
from backend.market_profiles import MARKET_PROFILES


def money(n):
    return round(float(n), 2)


def get_sector(symbol):
    return MARKET_PROFILES.get(symbol, {"sector": "Other"})["sector"]


def build_recommendations(cash_pct, largest_sector, largest_position, diversification_score):
    recommendations = []

    if cash_pct >= 80:
        recommendations.append("Cash is very high. Portfolio is conservative and has room to deploy capital.")
    elif cash_pct >= 40:
        recommendations.append("Cash allocation is healthy. You can selectively take high-confidence setups.")
    elif cash_pct < 15:
        recommendations.append("Cash is low. Avoid overtrading and preserve liquidity.")

    if largest_sector and largest_sector["weight"] >= 45:
        recommendations.append(
            f"Sector concentration is elevated in {largest_sector['sector']} at {largest_sector['weight']}%."
        )
    elif largest_sector:
        recommendations.append(
            f"Largest sector is {largest_sector['sector']} at {largest_sector['weight']}%, which is acceptable."
        )

    if largest_position and largest_position["weight"] >= 25:
        recommendations.append(
            f"Largest position is {largest_position['symbol']} at {largest_position['weight']}%. Consider reducing concentration."
        )
    elif largest_position:
        recommendations.append(
            f"Largest position is {largest_position['symbol']} at {largest_position['weight']}%, which is currently manageable."
        )

    if diversification_score >= 85:
        recommendations.append("Diversification is strong.")
    elif diversification_score >= 70:
        recommendations.append("Diversification is acceptable but can improve.")
    else:
        recommendations.append("Diversification is weak. Avoid adding to the same sector.")

    return recommendations


def analyze_portfolio():
    cash = account["balance"]
    holdings = []
    sector_totals = {}
    portfolio_value = cash

    for p in positions:
        symbol = p["symbol"]
        current_price = prices.get(symbol, p["avg_price"])
        value = current_price * p["qty"]
        portfolio_value += value

        sector = get_sector(symbol)
        sector_totals[sector] = sector_totals.get(sector, 0) + value

        holdings.append({
            "symbol": symbol,
            "sector": sector,
            "value": money(value),
            "qty": p["qty"],
            "avg_price": p["avg_price"],
            "current_price": current_price,
            "weight": 0,
        })

    if portfolio_value == 0:
        portfolio_value = 1

    for h in holdings:
        h["weight"] = money((h["value"] / portfolio_value) * 100)

    cash_pct = money((cash / portfolio_value) * 100)

    largest_position = max(holdings, key=lambda x: x["value"]) if holdings else None

    sector_breakdown = [
        {
            "sector": sector,
            "value": money(value),
            "weight": money((value / portfolio_value) * 100),
        }
        for sector, value in sector_totals.items()
    ]

    sector_breakdown.sort(key=lambda x: x["weight"], reverse=True)

    largest_sector = sector_breakdown[0] if sector_breakdown else None

    diversification_score = money(
        max(0, 100 - (largest_sector["weight"] if largest_sector else 0))
    )

    if diversification_score >= 85:
        grade = "A"
        risk_level = "Low"
    elif diversification_score >= 70:
        grade = "B"
        risk_level = "Moderate"
    elif diversification_score >= 55:
        grade = "C"
        risk_level = "Elevated"
    else:
        grade = "D"
        risk_level = "High"

    recommendations = build_recommendations(
        cash_pct=cash_pct,
        largest_sector=largest_sector,
        largest_position=largest_position,
        diversification_score=diversification_score,
    )

    return {
        "portfolio_value": money(portfolio_value),
        "cash": money(cash),
        "cash_pct": cash_pct,
        "positions": holdings,
        "largest_position": largest_position,
        "sector_breakdown": sector_breakdown,
        "largest_sector": largest_sector,
        "diversification_score": diversification_score,
        "portfolio_grade": grade,
        "risk_level": risk_level,
        "recommendations": recommendations,
        "summary": (
            f"Portfolio grade is {grade}. Cash is {cash_pct}%. "
            f"Risk level is {risk_level}. "
            f"Diversification score is {diversification_score}%."
        ),
    }