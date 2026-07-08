from datetime import datetime

from backend.database import get_connection
from backend.market import money
from backend.market_data.service import get_price
from backend.trade_intelligence import record_trade_intelligence

STARTING_BALANCE = 10000.0

account = {"balance": STARTING_BALANCE, "equity": STARTING_BALANCE}
positions = []
trades = []


def _ensure_portfolio_schema():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS portfolio (
        id INTEGER PRIMARY KEY,
        cash REAL,
        equity REAL,
        updated TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS positions (
        symbol TEXT PRIMARY KEY,
        qty INTEGER,
        avg_price REAL,
        sector TEXT,
        confidence REAL,
        strategy TEXT,
        market_bias TEXT,
        highest_price REAL,
        stop_loss REAL,
        take_profit REAL,
        trailing_stop REAL
    )
    """)

    columns = [row["name"] for row in cur.execute("PRAGMA table_info(positions)")]

    for name, ddl in {
        "sector": "ALTER TABLE positions ADD COLUMN sector TEXT DEFAULT 'Other'",
        "confidence": "ALTER TABLE positions ADD COLUMN confidence REAL DEFAULT 0",
        "strategy": "ALTER TABLE positions ADD COLUMN strategy TEXT DEFAULT 'Momentum'",
        "market_bias": "ALTER TABLE positions ADD COLUMN market_bias TEXT DEFAULT 'Unknown'",
        "highest_price": "ALTER TABLE positions ADD COLUMN highest_price REAL",
        "stop_loss": "ALTER TABLE positions ADD COLUMN stop_loss REAL",
        "take_profit": "ALTER TABLE positions ADD COLUMN take_profit REAL",
        "trailing_stop": "ALTER TABLE positions ADD COLUMN trailing_stop REAL",
    }.items():
        if name not in columns:
            cur.execute(ddl)

    cur.execute(
        """
        INSERT OR IGNORE INTO portfolio (id, cash, equity, updated)
        VALUES (1, ?, ?, ?)
        """,
        (STARTING_BALANCE, STARTING_BALANCE, datetime.utcnow().isoformat()),
    )

    conn.commit()
    conn.close()


def _save_portfolio():
    equity = calc_equity()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE portfolio
        SET cash = ?, equity = ?, updated = ?
        WHERE id = 1
        """,
        (account["balance"], equity, datetime.utcnow().isoformat()),
    )

    conn.commit()
    conn.close()

    account["equity"] = equity


def _save_position(position):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO positions (
            symbol, qty, avg_price, sector, confidence, strategy, market_bias,
            highest_price, stop_loss, take_profit, trailing_stop
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol) DO UPDATE SET
            qty = excluded.qty,
            avg_price = excluded.avg_price,
            sector = excluded.sector,
            confidence = excluded.confidence,
            strategy = excluded.strategy,
            market_bias = excluded.market_bias,
            highest_price = excluded.highest_price,
            stop_loss = excluded.stop_loss,
            take_profit = excluded.take_profit,
            trailing_stop = excluded.trailing_stop
        """,
        (
            position["symbol"],
            int(position["qty"]),
            float(position["avg_price"]),
            position.get("sector", "Other"),
            float(position.get("confidence", 0)),
            position.get("strategy", "Momentum"),
            position.get("market_bias", "Unknown"),
            position.get("highest_price"),
            position.get("stop_loss"),
            position.get("take_profit"),
            position.get("trailing_stop"),
        ),
    )

    conn.commit()
    conn.close()


def _delete_position(symbol):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM positions WHERE symbol = ?", (symbol.upper(),))
    conn.commit()
    conn.close()


def _load_portfolio():
    global positions

    _ensure_portfolio_schema()

    conn = get_connection()

    row = conn.execute("SELECT * FROM portfolio WHERE id = 1").fetchone()

    if row:
        account["balance"] = money(row["cash"])
        account["equity"] = money(row["equity"])

    rows = conn.execute("SELECT * FROM positions ORDER BY symbol").fetchall()
    conn.close()

    positions = [
        {
            "symbol": row["symbol"],
            "qty": int(row["qty"]),
            "avg_price": money(row["avg_price"]),
            "sector": row["sector"] or "Other",
            "confidence": float(row["confidence"] or 0),
            "strategy": row["strategy"] or "Momentum",
            "market_bias": row["market_bias"] or "Unknown",
            "highest_price": row["highest_price"],
            "stop_loss": row["stop_loss"],
            "take_profit": row["take_profit"],
            "trailing_stop": row["trailing_stop"],
        }
        for row in rows
    ]


def calc_equity():
    position_value = 0.0

    for p in positions:
        price = get_price(p["symbol"])

        if price is not None:
            position_value += price * p["qty"]

    return money(account["balance"] + position_value)


def get_enriched_positions():
    enriched = []

    for p in positions:
        price = get_price(p["symbol"])

        if price is None:
            continue

        enriched.append({
            **p,
            "current_price": money(price),
            "value": money(price * p["qty"]),
            "pnl": money((price - p["avg_price"]) * p["qty"]),
            "pnl_pct": round(((price - p["avg_price"]) / p["avg_price"]) * 100, 2)
            if p["avg_price"]
            else 0.0,
        })

    return enriched


def buy_symbol(
    symbol,
    qty=1,
    sector="Other",
    confidence=0,
    strategy="Momentum",
    market_bias="Unknown",
):
    symbol = symbol.upper()
    qty = int(qty)

    if qty <= 0:
        return {"error": "Quantity must be greater than zero"}

    price = get_price(symbol)

    if price is None:
        return {"error": "Unknown symbol"}

    total_cost = money(price * qty)

    if account["balance"] < total_cost:
        return {"error": "Insufficient cash"}

    saved_position = None

    for p in positions:
        if p["symbol"] == symbol:
            new_qty = p["qty"] + qty
            p["avg_price"] = money(
                ((p["avg_price"] * p["qty"]) + (price * qty)) / new_qty
            )
            p["qty"] = new_qty
            p["sector"] = sector
            p["confidence"] = confidence
            p["strategy"] = strategy
            p["market_bias"] = market_bias
            saved_position = p
            break
    else:
        saved_position = {
            "symbol": symbol,
            "qty": qty,
            "avg_price": price,
            "sector": sector,
            "confidence": confidence,
            "strategy": strategy,
            "market_bias": market_bias,
            "highest_price": None,
            "stop_loss": None,
            "take_profit": None,
            "trailing_stop": None,
        }
        positions.append(saved_position)

    account["balance"] = money(account["balance"] - total_cost)

    _save_position(saved_position)
    _save_portfolio()

    trade = {
        "side": "BUY",
        "symbol": symbol,
        "qty": qty,
        "price": price,
        "total": total_cost,
        "sector": sector,
        "confidence": confidence,
        "strategy": strategy,
        "market_bias": market_bias,
        "time": datetime.utcnow().isoformat(),
    }

    trades.append(trade)
    return {"ok": True, **trade}


def sell_symbol(symbol, qty=None, exit_reason="Manual Exit"):
    symbol = symbol.upper()

    price = get_price(symbol)

    if price is None:
        return {"error": "Unknown symbol"}

    position = next((p for p in positions if p["symbol"] == symbol), None)

    if not position:
        return {"error": "No open position"}

    if qty is None:
        qty = position["qty"]

    qty = int(qty)

    if qty <= 0:
        return {"error": "Quantity must be greater than zero"}

    if qty > position["qty"]:
        return {"error": "Not enough shares to sell"}

    entry_price = position["avg_price"]
    total = money(price * qty)
    realized_pnl = money((price - entry_price) * qty)

    sector = position.get("sector", "Other")
    confidence = position.get("confidence", 0)
    strategy = position.get("strategy", "Momentum")
    market_bias = position.get("market_bias", "Unknown")

    account["balance"] = money(account["balance"] + total)

    position["qty"] -= qty
    position_closed = position["qty"] <= 0

    if position_closed:
        positions.remove(position)
        _delete_position(symbol)

        record_trade_intelligence(
            symbol=symbol,
            entry_price=entry_price,
            exit_price=price,
            qty=qty,
            realized_pnl=realized_pnl,
            strategy=strategy,
            sector=sector,
            confidence=confidence,
            market_bias=market_bias,
            exit_reason=exit_reason,
        )
    else:
        _save_position(position)

    _save_portfolio()

    trade = {
        "side": "SELL",
        "symbol": symbol,
        "qty": qty,
        "price": price,
        "total": total,
        "realized_pnl": realized_pnl,
        "position_closed": position_closed,
        "sector": sector,
        "confidence": confidence,
        "strategy": strategy,
        "market_bias": market_bias,
        "time": datetime.utcnow().isoformat(),
    }

    trades.append(trade)
    return {"ok": True, **trade}


_load_portfolio()
