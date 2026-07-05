from datetime import datetime

from backend.portfolio_live import build_portfolio_live
from backend.portfolio import sell_symbol
from backend.trade_history import record_trade
from backend.activity_log import log_event

auto_exit_state = {
    "enabled": True,
    "last_run": None,
    "last_exit": None,
    "checks": 0,
}


TAKE_PROFIT_PCT = 5.0
STOP_LOSS_PCT = -3.0


def run_auto_exit_manager():
    portfolio = build_portfolio_live()
    updates = []

    auto_exit_state["checks"] += 1
    auto_exit_state["last_run"] = datetime.utcnow().isoformat()

    for position in portfolio["positions"]:
        symbol = position["symbol"]
        pnl_pct = float(position.get("pnl_pct", 0))
        qty = int(position.get("qty", 0))

        if qty <= 0:
            continue

        should_exit = False
        reason = "Continue holding."

        if pnl_pct >= TAKE_PROFIT_PCT:
            should_exit = True
            reason = "Take profit target reached."

        elif pnl_pct <= STOP_LOSS_PCT:
            should_exit = True
            reason = "Stop loss triggered."

        if not should_exit:
            updates.append({
                "symbol": symbol,
                "action": "HOLD",
                "pnl_pct": pnl_pct,
                "reason": reason,
            })
            continue

        result = sell_symbol(symbol, qty=qty)

        if result.get("ok"):
            record_trade(
                side="SELL",
                symbol=result["symbol"],
                qty=result["qty"],
                price=result["price"],
                total=result["total"],
                realized_pnl=result["realized_pnl"],
                source="AUTO_EXIT_MANAGER",
            )

            event = {
                "symbol": symbol,
                "action": "SELL",
                "qty": qty,
                "price": result["price"],
                "realized_pnl": result["realized_pnl"],
                "reason": reason,
            }

            auto_exit_state["last_exit"] = event

            log_event(
                f"{symbol} auto-sold {qty} share(s) at ${result['price']}. P/L ${result['realized_pnl']}. Reason: {reason}",
                "SELL",
            )

            updates.append(event)
        else:
            updates.append({
                "symbol": symbol,
                "action": "ERROR",
                "reason": result.get("error", "Sell failed."),
            })

            log_event(
                f"{symbol} auto-exit error: {result.get('error', 'Sell failed.')}",
                "ERROR",
            )

    return {
        "ok": True,
        "checked_positions": len(portfolio["positions"]),
        "updates": updates,
        "state": auto_exit_state,
    }


def get_auto_exit_status():
    portfolio = build_portfolio_live()

    return {
        "enabled": auto_exit_state["enabled"],
        "watching_positions": portfolio["open_positions"],
        "last_run": auto_exit_state["last_run"],
        "last_exit": auto_exit_state["last_exit"],
        "checks": auto_exit_state["checks"],
        "take_profit_pct": TAKE_PROFIT_PCT,
        "stop_loss_pct": STOP_LOSS_PCT,
    }