from datetime import datetime

from backend.portfolio_ai import analyze_portfolio
from backend.scanner import scan_market
from backend.position_advisor import build_position_advice


def build_daily_plan(limit=3):
    portfolio = analyze_portfolio()

    scan = scan_market(limit=10)
    opportunities = scan.get("opportunities", [])

    approved = []
    rejected = []

    for opp in opportunities:
        symbol = opp["symbol"]

        advice = build_position_advice(symbol)

        if advice.get("approved"):
            approved.append({
                "symbol": symbol,
                "confidence": advice["trade_plan"]["confidence"],
                "allocation_pct": advice["recommended_allocation_pct"],
                "shares": advice["recommended_shares"],
                "estimated_cost": advice["recommended_dollars"],
                "action": advice["action"],
            })
        else:
            rejected.append({
                "symbol": symbol,
                "reason": advice.get("reason", "Rejected"),
            })

    approved = sorted(
        approved,
        key=lambda x: x["confidence"],
        reverse=True,
    )

    recommended_capital = round(
        sum(x["estimated_cost"] for x in approved[:limit]),
        2,
    )

    if approved:
        avg_confidence = (
            sum(x["confidence"] for x in approved[:limit])
            / len(approved[:limit])
        )

        if avg_confidence >= 85:
            market_bias = "Bullish"
        elif avg_confidence >= 70:
            market_bias = "Neutral"
        else:
            market_bias = "Cautious"
    else:
        market_bias = "Defensive"

    return {
        "generated": datetime.utcnow().isoformat(),
        "market_bias": market_bias,
        "portfolio_risk": portfolio["risk_level"],
        "cash_available": portfolio["cash"],
        "recommended_capital": recommended_capital,
        "max_trades": limit,
        "top_picks": approved[:limit],
        "avoid": rejected[:5],
        "summary": (
            f"Today's plan recommends up to "
            f"{limit} trades using approximately "
            f"${recommended_capital}."
        ),
    }