from datetime import datetime

trade_history = []


def record_trade(side, symbol, qty, price, total, source="SYSTEM", realized_pnl=0.0):
    trade = {
        "id": len(trade_history) + 1,
        "time": datetime.utcnow().isoformat(),
        "side": side.upper(),
        "symbol": symbol.upper(),
        "qty": int(qty),
        "price": round(float(price), 2),
        "total": round(float(total), 2),
        "realized_pnl": round(float(realized_pnl), 2),
        "source": source,
    }

    trade_history.insert(0, trade)
    return trade


def get_trade_history():
    return trade_history


def clear_trade_history():
    trade_history.clear()
    return {"ok": True, "count": 0}


def get_trade_stats():
    buys = [t for t in trade_history if t["side"] == "BUY"]
    sells = [t for t in trade_history if t["side"] == "SELL"]

    total_buy_value = round(sum(t["total"] for t in buys), 2)
    total_sell_value = round(sum(t["total"] for t in sells), 2)
    realized_pnl = round(sum(t.get("realized_pnl", 0) for t in sells), 2)

    winning_sells = [t for t in sells if t.get("realized_pnl", 0) > 0]
    losing_sells = [t for t in sells if t.get("realized_pnl", 0) < 0]

    closed_trades = len(sells)
    win_rate = round((len(winning_sells) / closed_trades) * 100, 2) if closed_trades else 0.0

    return {
        "total_trades": len(trade_history),
        "buy_trades": len(buys),
        "sell_trades": len(sells),
        "open_positions": len(buys) - len(sells),
        "total_buy_value": total_buy_value,
        "total_sell_value": total_sell_value,
        "realized_pnl": realized_pnl,
        "closed_trades": closed_trades,
        "winning_trades": len(winning_sells),
        "losing_trades": len(losing_sells),
        "win_rate": win_rate,
    }