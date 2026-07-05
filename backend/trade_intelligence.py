from datetime import datetime

trade_intelligence = []


def record_trade_intelligence(
    symbol,
    entry_price,
    exit_price,
    qty,
    realized_pnl,
    strategy="Momentum",
    sector="Other",
    confidence=0,
    market_bias="Unknown",
    exit_reason="Manual Exit",
):
    entry_price = float(entry_price)
    exit_price = float(exit_price)
    qty = int(qty)
    realized_pnl = float(realized_pnl)

    cost_basis = entry_price * qty
    return_pct = (realized_pnl / cost_basis) * 100 if cost_basis else 0

    record = {
        "id": len(trade_intelligence) + 1,
        "time": datetime.utcnow().isoformat(),
        "symbol": symbol.upper(),
        "strategy": strategy,
        "sector": sector,
        "confidence": round(float(confidence), 2),
        "market_bias": market_bias,
        "entry_price": round(entry_price, 2),
        "exit_price": round(exit_price, 2),
        "qty": qty,
        "realized_pnl": round(realized_pnl, 2),
        "return_pct": round(return_pct, 2),
        "won": realized_pnl > 0,
        "exit_reason": exit_reason,
    }

    trade_intelligence.insert(0, record)
    return record


def get_trade_intelligence_records():
    return trade_intelligence


def clear_trade_intelligence():
    trade_intelligence.clear()
    return {"ok": True, "count": 0}


def summarize_group(records, key):
    groups = {}

    for record in records:
        name = record.get(key) or "Unknown"

        if name not in groups:
            groups[name] = {
                "name": name,
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "total_pnl": 0.0,
                "total_return_pct": 0.0,
            }

        group = groups[name]
        group["trades"] += 1
        group["total_pnl"] += record["realized_pnl"]
        group["total_return_pct"] += record["return_pct"]

        if record["realized_pnl"] > 0:
            group["wins"] += 1
        elif record["realized_pnl"] < 0:
            group["losses"] += 1

    for group in groups.values():
        trades = group["trades"]
        group["win_rate"] = round((group["wins"] / trades) * 100, 2) if trades else 0
        group["avg_return_pct"] = round(group["total_return_pct"] / trades, 2) if trades else 0
        group["total_pnl"] = round(group["total_pnl"], 2)

    return groups


def get_trade_intelligence_summary():
    records = trade_intelligence

    wins = [r for r in records if r["realized_pnl"] > 0]
    losses = [r for r in records if r["realized_pnl"] < 0]

    total_trades = len(records)
    total_pnl = round(sum(r["realized_pnl"] for r in records), 2)
    win_rate = round((len(wins) / total_trades) * 100, 2) if total_trades else 0.0

    avg_win = round(sum(r["realized_pnl"] for r in wins) / len(wins), 2) if wins else 0.0
    avg_loss = round(sum(r["realized_pnl"] for r in losses) / len(losses), 2) if losses else 0.0

    gross_profit = sum(r["realized_pnl"] for r in wins)
    gross_loss = abs(sum(r["realized_pnl"] for r in losses))
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss else 0.0

    strategies = summarize_group(records, "strategy")
    sectors = summarize_group(records, "sector")

    best_strategy = max(strategies.values(), key=lambda x: x["total_pnl"], default=None)
    best_sector = max(sectors.values(), key=lambda x: x["total_pnl"], default=None)

    return {
        "total_trades_learned": total_trades,
        "total_pnl": total_pnl,
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "best_strategy": best_strategy,
        "best_sector": best_sector,
        "strategies": strategies,
        "sectors": sectors,
        "recent_learning": records[:10],
        "summary": (
            "Kyle is collecting trade intelligence."
            if total_trades == 0
            else f"Kyle has learned from {total_trades} closed trade(s)."
        ),
    }