from backend.trade_planner import build_trade_plan
from backend.portfolio_ai import analyze_portfolio
from backend.market import candles, prices
from backend.market_profiles import MARKET_PROFILES


def money(n):
    return round(float(n), 2)


def get_sector(symbol):
    return MARKET_PROFILES.get(symbol, {"sector": "Other"}).get("sector", "Other")


def clamp(value, low, high):
    return max(low, min(high, value))


def build_position_advice(symbol, risk_pct=1.0, max_allocation_pct=10.0):
    symbol = symbol.upper()

    portfolio = analyze_portfolio()
    trade_plan = build_trade_plan(
        symbol=symbol,
        candles=candles.get(symbol, []),
        account_equity=portfolio["portfolio_value"],
        risk_pct=risk_pct,
    )

    if trade_plan.get("error"):
        return trade_plan

    if trade_plan.get("action") == "NO TRADE":
        return {
            "symbol": symbol,
            "approved": False,
            "action": "NO TRADE",
            "reason": trade_plan.get("reason", "Trade setup rejected."),
            "trade_plan": trade_plan,
            "portfolio": portfolio,
        }

    cash = portfolio["cash"]
    portfolio_value = portfolio["portfolio_value"]
    current_price = prices.get(symbol)

    if not current_price:
        return {
            "symbol": symbol,
            "approved": False,
            "action": "NO TRADE",
            "reason": "No current price available.",
            "trade_plan": trade_plan,
            "portfolio": portfolio,
        }

    sector = get_sector(symbol)

    current_sector_weight = 0
    for sector_row in portfolio.get("sector_breakdown", []):
        if sector_row["sector"] == sector:
            current_sector_weight = sector_row["weight"]
            break

    confidence = trade_plan.get("confidence", 0)

    if confidence >= 90:
        base_allocation = 4.0
    elif confidence >= 80:
        base_allocation = 3.0
    elif confidence >= 70:
        base_allocation = 2.0
    else:
        base_allocation = 1.0

    if portfolio["cash_pct"] < 20:
        base_allocation *= 0.5

    if current_sector_weight >= 35:
        base_allocation *= 0.5

    if portfolio["risk_level"] in ["Elevated", "High"]:
        base_allocation *= 0.5

    recommended_allocation_pct = clamp(base_allocation, 0.5, max_allocation_pct)
    recommended_dollars = portfolio_value * (recommended_allocation_pct / 100)

    if recommended_dollars > cash:
        recommended_dollars = cash

    recommended_shares = int(recommended_dollars / current_price)

    if recommended_shares <= 0 and cash >= current_price:
        recommended_shares = 1
        recommended_dollars = current_price
        recommended_allocation_pct = (current_price / portfolio_value) * 100

    if recommended_shares <= 0:
        return {
            "symbol": symbol,
            "approved": False,
            "action": "NO TRADE",
            "reason": "Insufficient cash to buy one share.",
            "recommended_allocation_pct": money(recommended_allocation_pct),
            "recommended_dollars": money(recommended_dollars),
            "current_price": money(current_price),
            "trade_plan": trade_plan,
            "portfolio": portfolio,
        }

    estimated_cost = recommended_shares * current_price
    cash_after_trade = cash - estimated_cost

    existing_sector_value = 0
    for sector_row in portfolio.get("sector_breakdown", []):
        if sector_row["sector"] == sector:
            existing_sector_value = sector_row["value"]
            break

    new_sector_value = existing_sector_value + estimated_cost
    sector_exposure_after_trade = (
        (new_sector_value / portfolio_value) * 100 if portfolio_value else 0
    )

    approved = True
    warnings = []

    if sector_exposure_after_trade > 45:
        approved = False
        warnings.append("Trade would create excessive sector concentration.")

    if (cash_after_trade / portfolio_value) * 100 < 10:
        approved = False
        warnings.append("Trade would reduce cash below 10%.")

    if trade_plan.get("risk_score", 0) > 70:
        approved = False
        warnings.append("Trade risk score is too high.")

    reason = (
        f"{symbol} has a {trade_plan.get('quality', 'UNKNOWN')} setup. "
        f"Recommended allocation is {money(recommended_allocation_pct)}% "
        f"because portfolio cash is {portfolio['cash_pct']}%, "
        f"risk level is {portfolio['risk_level']}, and current {sector} exposure is "
        f"{money(current_sector_weight)}%."
    )

    return {
        "symbol": symbol,
        "approved": approved,
        "action": "BUY" if approved else "NO TRADE",
        "recommended_allocation_pct": money(recommended_allocation_pct),
        "recommended_dollars": money(estimated_cost),
        "recommended_shares": recommended_shares,
        "current_price": money(current_price),
        "cash_after_trade": money(cash_after_trade),
        "sector": sector,
        "sector_exposure_before_trade": money(current_sector_weight),
        "sector_exposure_after_trade": money(sector_exposure_after_trade),
        "portfolio_risk_after_trade": portfolio["risk_level"],
        "warnings": warnings,
        "reason": reason,
        "trade_plan": trade_plan,
        "portfolio": portfolio,
    }