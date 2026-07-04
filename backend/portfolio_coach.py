from backend.portfolio_ai import analyze_portfolio
from backend.scanner import scan_market


def build_portfolio_coach(limit=3):
    portfolio = analyze_portfolio()

    scan = scan_market(limit=limit)

    ideas = []

    opportunities = scan.get("opportunities", [])

    for trade in opportunities:

        ideas.append(
            {
                "symbol": trade["symbol"],
                "action": trade["trade_action"],
                "confidence": trade["confidence"],
                "summary": trade["summary"],
            }
        )

    messages = []

    if portfolio["cash_pct"] >= 80:
        messages.append(
            "You have significant cash available. Consider deploying capital gradually into high-confidence setups."
        )

    elif portfolio["cash_pct"] < 20:
        messages.append(
            "Cash reserves are becoming limited. Be selective with new positions."
        )

    if portfolio["risk_level"] == "High":
        messages.append(
            "Portfolio risk is elevated. Prioritize reducing concentration before opening new trades."
        )

    elif portfolio["risk_level"] == "Low":
        messages.append(
            "Overall portfolio risk is currently low."
        )

    if opportunities:

        best = opportunities[0]

        messages.append(
            f"Today's highest-rated opportunity is {best['symbol']} with {best['confidence']}% confidence."
        )

    return {
        "portfolio": portfolio,
        "ideas": ideas,
        "coach_messages": messages,
    }