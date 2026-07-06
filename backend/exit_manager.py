from datetime import datetime

from backend.market import prices
from backend.portfolio import positions, sell_symbol, _save_position


STOP_LOSS_PCT = 3.0
TAKE_PROFIT_PCT = 5.0
TRAILING_STOP_PCT = 3.0


def initialize_position(position):
    if not position.get("highest_price"):
        position["highest_price"] = position["avg_price"]

    if not position.get("stop_loss"):
        position["stop_loss"] = round(
            position["avg_price"] * (1 - STOP_LOSS_PCT / 100),
            2,
        )

    if not position.get("take_profit"):
        position["take_profit"] = round(
            position["avg_price"] * (1 + TAKE_PROFIT_PCT / 100),
            2,
        )

    if not position.get("trailing_stop"):
        position["trailing_stop"] = position["stop_loss"]


def evaluate_position(position):
    initialize_position(position)

    symbol = position["symbol"]

    if symbol not in prices:
        return None

    current_price = prices[symbol]

    if current_price > position["highest_price"]:
        position["highest_price"] = current_price

        new_trailing = round(
            current_price * (1 - TRAILING_STOP_PCT / 100),
            2,
        )

        if new_trailing > position["trailing_stop"]:
            position["trailing_stop"] = new_trailing

    if current_price <= position["stop_loss"]:
        return {
            "action": "SELL",
            "reason": "STOP_LOSS",
            "price": current_price,
        }

    if current_price <= position["trailing_stop"]:
        return {
            "action": "SELL",
            "reason": "TRAILING_STOP",
            "price": current_price,
        }

    if current_price >= position["take_profit"]:
        return {
            "action": "SELL",
            "reason": "TAKE_PROFIT",
            "price": current_price,
        }

    return {
        "action": "HOLD",
        "price": current_price,
        "highest_price": position["highest_price"],
        "stop_loss": position["stop_loss"],
        "take_profit": position["take_profit"],
        "trailing_stop": position["trailing_stop"],
    }


def run_exit_manager():
    updates = []

    for position in positions.copy():
        result = evaluate_position(position)

        if result is None:
            continue

        _save_position(position)

        if result["action"] == "SELL":
            sell = sell_symbol(
                position["symbol"],
                exit_reason=result["reason"],
            )

            updates.append({
                "symbol": position["symbol"],
                "action": "SELL",
                "reason": result["reason"],
                "sell": sell,
                "time": datetime.utcnow().isoformat(),
            })
        else:
            updates.append({
                "symbol": position["symbol"],
                "action": "HOLD",
                "current_price": result["price"],
                "highest_price": result["highest_price"],
                "stop_loss": result["stop_loss"],
                "take_profit": result["take_profit"],
                "trailing_stop": result["trailing_stop"],
            })

    return {
        "checked": len(updates),
        "updates": updates,
    }