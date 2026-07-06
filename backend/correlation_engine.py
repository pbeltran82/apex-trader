from backend.portfolio_live import build_portfolio_live


CORRELATION_GROUPS = {
    "Mega Cap Tech": ["AAPL", "MSFT", "NVDA", "AMD", "META", "GOOGL", "QQQ"],
    "Consumer Giants": ["AMZN", "WMT", "COST", "HD", "MCD"],
    "Financials": ["JPM", "GS", "BAC", "MS"],
    "Healthcare": ["UNH", "LLY", "JNJ", "PFE"],
    "Energy": ["XOM", "CVX"],
}


def find_group(symbol):
    symbol = symbol.upper()

    for group_name, symbols in CORRELATION_GROUPS.items():
        if symbol in symbols:
            return group_name

    return "Unclassified"


def analyze_correlation_risk(symbol):
    symbol = symbol.upper()
    portfolio = build_portfolio_live()
    positions = portfolio.get("positions", [])

    group = find_group(symbol)

    related_positions = [
        p for p in positions
        if find_group(p["symbol"]) == group
    ]

    related_value = round(
        sum(p.get("value", 0) for p in related_positions),
        2,
    )

    equity = portfolio.get("equity", 0) or 1

    related_exposure_pct = round(
        (related_value / equity) * 100,
        2,
    )

    if group == "Unclassified":
        return {
            "symbol": symbol,
            "group": group,
            "risk": "UNKNOWN",
            "confidence_adjustment": 0,
            "allocation_multiplier": 1.0,
            "related_positions": [],
            "related_exposure_pct": 0.0,
            "reason": "No correlation group available for this symbol.",
        }

    if related_exposure_pct >= 40:
        risk = "HIGH"
        confidence_adjustment = -8
        allocation_multiplier = 0.5
        reason = (
            f"{group} exposure is already high at "
            f"{related_exposure_pct}%."
        )
    elif related_exposure_pct >= 25:
        risk = "ELEVATED"
        confidence_adjustment = -4
        allocation_multiplier = 0.75
        reason = (
            f"{group} exposure is elevated at "
            f"{related_exposure_pct}%."
        )
    elif related_positions:
        risk = "MODERATE"
        confidence_adjustment = -2
        allocation_multiplier = 0.9
        reason = (
            f"Portfolio already has exposure to {group}."
        )
    else:
        risk = "LOW"
        confidence_adjustment = 0
        allocation_multiplier = 1.0
        reason = (
            f"No current portfolio overlap in {group}."
        )

    return {
        "symbol": symbol,
        "group": group,
        "risk": risk,
        "confidence_adjustment": confidence_adjustment,
        "allocation_multiplier": allocation_multiplier,
        "related_positions": related_positions,
        "related_exposure_pct": related_exposure_pct,
        "reason": reason,
    }