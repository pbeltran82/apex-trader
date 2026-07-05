from datetime import datetime

from backend.market import prices, money

account = {
    "balance": 10000.0,
    "equity": 10000.0,
}

positions = []
trades = []


def calc_equity():
    position_value = 0.0

    for p in positions:
        price = prices[p["symbol"]]
        position_value += price * p["qty"]

    return money(account["balance"] + position_value)


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
        "side": "BUY",
        "symbol": symbol,
        "qty": qty,
        "price": price,
        "total": total_cost,
    }


def sell_symbol(symbol, qty=None):
    symbol = symbol.upper()

    if symbol not in prices:
        return {"error": "Unknown symbol"}

    position = None

    for p in positions:
        if p["symbol"] == symbol:
            position = p
            break

    if not position:
        return {"error": "No open position"}

    if qty is None:
        qty = position["qty"]

    qty = int(qty)

    if qty <= 0:
        return {"error": "Quantity must be greater than zero"}

    if qty > position["qty"]:
        return {"error": "Not enough shares to sell"}

    price = prices[symbol]
    total = money(price * qty)
    realized_pnl = money((price - position["avg_price"]) * qty)

    account["balance"] = money(account["balance"] + total)

    position["qty"] -= qty

    if position["qty"] <= 0:
        positions.remove(position)

    trades.append({
        "side": "SELL",
        "symbol": symbol,
        "qty": qty,
        "price": price,
        "total": total,
        "realized_pnl": realized_pnl,
        "time": datetime.utcnow().isoformat(),
    })

    return {
        "ok": True,
        "side": "SELL",
        "symbol": symbol,
        "qty": qty,
        "price": price,
        "total": total,
        "realized_pnl": realized_pnl,
    }