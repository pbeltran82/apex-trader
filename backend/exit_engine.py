from backend.portfolio_live import build_portfolio_live


def evaluate_exit(symbol):
    """
    Basic exit logic.

    Later this will include:
    - Profit targets
    - Stop losses
    - Trailing stops
    - AI exit reasoning
    """

    portfolio = build_portfolio_live()

    for position in portfolio["positions"]:
        if position["symbol"] != symbol.upper():
            continue

        pnl_pct = position["pnl_pct"]

        # Take profit
        if pnl_pct >= 5:
            return {
                "exit": True,
                "reason": "Profit target reached.",
                "action": "SELL"
            }

        # Stop loss
        if pnl_pct <= -3:
            return {
                "exit": True,
                "reason": "Stop loss triggered.",
                "action": "SELL"
            }

        return {
            "exit": False,
            "reason": "Continue holding.",
            "action": "HOLD"
        }

    return {
        "exit": False,
        "reason": "Position not found.",
        "action": "NONE"
    }