from backend.portfolio_live import build_portfolio_live
from backend.trade_history import get_trade_history, get_trade_stats

STARTING_EQUITY = 10000.0


def build_performance():
    portfolio = build_portfolio_live()
    trades = get_trade_history()
    stats = get_trade_stats()

    current_equity = portfolio["equity"]
    total_pnl = round(current_equity - STARTING_EQUITY, 2)

    return_pct = (
        ((current_equity - STARTING_EQUITY) / STARTING_EQUITY) * 100
        if STARTING_EQUITY
        else 0
    )

    sells = [t for t in trades if t["side"] == "SELL"]
    realized_values = [t.get("realized_pnl", 0) for t in sells]

    wins = [p for p in realized_values if p > 0]
    losses = [p for p in realized_values if p < 0]

    avg_win = round(sum(wins) / len(wins), 2) if wins else 0.0
    avg_loss = round(sum(losses) / len(losses), 2) if losses else 0.0
    best_trade = round(max(realized_values), 2) if realized_values else 0.0
    worst_trade = round(min(realized_values), 2) if realized_values else 0.0

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss else 0.0

    return {
        "starting_equity": STARTING_EQUITY,
        "current_equity": current_equity,
        "cash": portfolio["cash"],
        "position_value": portfolio["position_value"],
        "unrealized_pnl": portfolio["unrealized_pnl"],
        "realized_pnl": stats["realized_pnl"],
        "total_pnl": total_pnl,
        "return_pct": round(return_pct, 2),
        "open_positions": portfolio["open_positions"],
        "exposure_pct": portfolio["exposure_pct"],
        "total_trades": stats["total_trades"],
        "buy_trades": stats["buy_trades"],
        "sell_trades": stats["sell_trades"],
        "closed_trades": stats.get("closed_trades", 0),
        "win_rate": stats.get("win_rate", 0.0),
        "profit_factor": profit_factor,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "max_drawdown": 0.0,
        "best_trade": best_trade,
        "worst_trade": worst_trade,
        "summary": (
            f"Portfolio is worth ${current_equity}. "
            f"Total P/L is ${total_pnl}. "
            f"Realized P/L is ${stats['realized_pnl']}. "
            f"Win rate is {stats.get('win_rate', 0.0)}%."
        ),
    }