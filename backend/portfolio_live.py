from backend.portfolio import account, positions, trades
from backend.market import prices, money


def build_portfolio_live():
    enriched_positions = []
    position_value = 0
    unrealized_pnl = 0

    for p in positions:
        symbol = p["symbol"]
        current_price = prices.get(symbol, p["avg_price"])
        value = current_price * p["qty"]
        pnl = (current_price - p["avg_price"]) * p["qty"]

        position_value += value
        unrealized_pnl += pnl

        enriched_positions.append({
            "symbol": symbol,
            "qty": p["qty"],
            "avg_price": money(p["avg_price"]),
            "current_price": money(current_price),
            "value": money(value),
            "pnl": money(pnl),
            "pnl_pct": money((pnl / (p["avg_price"] * p["qty"])) * 100)
            if p["avg_price"] * p["qty"] else 0,
        })

    cash = account["balance"]
    equity = cash + position_value
    exposure_pct = (position_value / equity) * 100 if equity else 0
    cash_pct = (cash / equity) * 100 if equity else 0

    return {
        "cash": money(cash),
        "equity": money(equity),
        "position_value": money(position_value),
        "unrealized_pnl": money(unrealized_pnl),
        "cash_pct": money(cash_pct),
        "exposure_pct": money(exposure_pct),
        "open_positions": len(positions),
        "positions": enriched_positions,
        "trades_count": len(trades),
        "latest_trade": trades[-1] if trades else None,
    }