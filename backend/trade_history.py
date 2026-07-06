from datetime import datetime

from backend.database import get_connection

trade_history = []


def _row_to_trade(row):
    return {
        "id": row["id"],
        "time": row["time"],
        "side": row["side"],
        "symbol": row["symbol"],
        "qty": row["qty"],
        "price": round(float(row["price"] or 0), 2),
        "total": round(float(row["total"] or 0), 2),
        "realized_pnl": round(float(row["realized_pnl"] or 0), 2),
        "source": row["source"] if "source" in row.keys() else "SYSTEM",
    }


def _ensure_source_column():
    conn = get_connection()
    cur = conn.cursor()

    columns = [row["name"] for row in cur.execute("PRAGMA table_info(trades)")]

    if "source" not in columns:
        cur.execute("ALTER TABLE trades ADD COLUMN source TEXT DEFAULT 'SYSTEM'")

    conn.commit()
    conn.close()


_ensure_source_column()


def record_trade(side, symbol, qty, price, total, source="SYSTEM", realized_pnl=0.0):
    trade_time = datetime.utcnow().isoformat()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO trades (
            time, side, symbol, qty, price, total, realized_pnl, source
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trade_time,
            side.upper(),
            symbol.upper(),
            int(qty),
            round(float(price), 2),
            round(float(total), 2),
            round(float(realized_pnl), 2),
            source,
        ),
    )

    trade_id = cur.lastrowid
    conn.commit()
    conn.close()

    trade = {
        "id": trade_id,
        "time": trade_time,
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
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT *
        FROM trades
        ORDER BY id DESC
        """
    ).fetchall()
    conn.close()

    return [_row_to_trade(row) for row in rows]


def clear_trade_history():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM trades")
    conn.commit()
    conn.close()

    trade_history.clear()
    return {"ok": True, "count": 0}


def get_trade_stats():
    history = get_trade_history()

    buys = [t for t in history if t["side"] == "BUY"]
    sells = [t for t in history if t["side"] == "SELL"]

    total_buy_value = round(sum(t["total"] for t in buys), 2)
    total_sell_value = round(sum(t["total"] for t in sells), 2)
    realized_pnl = round(sum(t.get("realized_pnl", 0) for t in sells), 2)

    winning_sells = [t for t in sells if t.get("realized_pnl", 0) > 0]
    losing_sells = [t for t in sells if t.get("realized_pnl", 0) < 0]

    closed_trades = len(sells)
    win_rate = round((len(winning_sells) / closed_trades) * 100, 2) if closed_trades else 0.0

    return {
        "total_trades": len(history),
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


def get_today_realized_pnl():
    today = datetime.utcnow().date().isoformat()
    trades = get_trade_history()

    today_sells = [
        trade for trade in trades
        if trade.get("side") == "SELL"
        and str(trade.get("time", "")).startswith(today)
    ]

    return round(
        sum(trade.get("realized_pnl", 0) for trade in today_sells),
        2,
    )    