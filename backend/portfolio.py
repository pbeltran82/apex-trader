from datetime import datetime

from backend.market import prices, money

account = {
    "balance": 10000.0,
    "equity": 10000.0,
}

positions = []
trades = []


def calc_equity():
    unrealized = 0.0

    for p in positions:
        price = prices[p["symbol"]]
        unrealized += (price - p["avg_price"]) * p["qty"]

    return money(account["balance"] + unrealized)


def get_enriched_positions():
    enriched = []

    for p in positions:
        price = prices[p["symbol"]]

        enriched.append({
            **p,
            "current_price": money(price),
            "pnl": money((price - p["avg_price"]) * p["qty"]),
        })

    return enriched


def buy_symbol(symbol, qty=1):
    symbol = symbol.upper()
    qty = int(qty)

    if qty <= 0:
        return {"error": "Quantity must be greater than zero"}

    if symbol not in prices:
        return {"error": "Unknown symbol"}

    price = prices[symbol]
    total_cost = money(price * qty)

    if account["balance"] < total_cost:
        return {"error": "Insufficient cash"}

    for p in positions:
        if p["symbol"] == symbol:
            new_qty = p["qty"] + qty

            p["avg_price"] = money(
                ((p["avg_price"] * p["qty"]) + (price * qty)) / new_qty
            )

            p["qty"] = new_qty
            break
    else:
        positions.append({
            "symbol": symbol,
            "qty": qty,
            "avg_price": price,
        })

    account["balance"] = money(account["balance"] - total_cost)

    trades.append({
        "side": "BUY",
        "symbol": symbol,
        "qty": qty,
        "price": price,
        "total": total_cost,
        "time": datetime.utcnow().isoformat(),
    })

    return {
        "ok": True,
        "symbol": symbol,
        "qty": qty,
        "price": price,
        "total": total_cost,
    }