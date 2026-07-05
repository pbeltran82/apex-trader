from datetime import datetime

from backend.market import prices, money
from backend.trade_intelligence import record_trade_intelligence

account = {"balance": 10000.0, "equity": 10000.0}

positions = []
trades = []


def calc_equity():
    position_value = 0.0
    for p in positions:
        position_value += prices[p["symbol"]] * p["qty"]
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


def buy_symbol(symbol, qty=1, sector="Other", confidence=0, strategy="Momentum", market_bias="Unknown"):
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
            p["avg_price"] = money(((p["avg_price"] * p["qty"]) + (price * qty)) / new_qty)
            p["qty"] = new_qty
            p["sector"] = sector
            p["confidence"] = confidence
            p["strategy"] = strategy
            p["market_bias"] = market_bias
            break
    else:
        positions.append({
            "symbol": symbol,
            "qty": qty,
            "avg_price": price,
            "sector": sector,
            "confidence": confidence,
            "strategy": strategy,
            "market_bias": market_bias,
        })

    account["balance"] = money(account["balance"] - total_cost)

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

    if symbol not in prices:
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

    price = prices[symbol]
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