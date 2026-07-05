from backend.portfolio_live import build_portfolio_live
from backend.trade_history import get_trade_history

STARTING_EQUITY = 10000.0


def build_performance():
    portfolio = build_portfolio_live()
    trades = get_trade_history()

    current_equity = portfolio["equity"]
    unrealized_pnl = portfolio["unrealized_pnl"]

    buys = [t for t in trades if t["side"] == "BUY"]
    sells = [t for t in trades if t["side"] == "SELL"]

    return_pct = (
        ((current_equity - STARTING_EQUITY) / STARTING_EQUITY) * 100
        if STARTING_EQUITY
        else 0
    )

    return {
        "starting_equity": STARTING_EQUITY,
        "current_equity": current_equity,
        "cash": portfolio["cash"],
        "position_value": portfolio["position_value"],
        "unrealized_pnl": unrealized_pnl,
        "realized_pnl": 0.0,
        "total_pnl": round(current_equity - STARTING_EQUITY, 2),
        "return_pct": round(return_pct, 2),
        "open_positions": portfolio["open_positions"],
        "exposure_pct": portfolio["exposure_pct"],
        "total_trades": len(trades),
        "buy_trades": len(buys),
        "sell_trades": len(sells),
        "win_rate": 0.0,
        "profit_factor": 0.0,
        "avg_win": 0.0,
        "avg_loss": 0.0,
        "max_drawdown": 0.0,
        "best_trade": 0.0,
        "worst_trade": 0.0,
        "summary": (
            f"Portfolio is worth ${current_equity}. "
            f"Total P/L is ${round(current_equity - STARTING_EQUITY, 2)}. "
            f"Exposure is {portfolio['exposure_pct']}%."
        ),
    }