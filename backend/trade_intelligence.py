from datetime import datetime

from backend.database import get_connection

trade_intelligence = []


def classify_outcome(realized_pnl):
    realized_pnl = float(realized_pnl)

    if realized_pnl > 0:
        return "WIN"
    if realized_pnl < 0:
        return "LOSS"
    return "SCRATCH"


def _ensure_trade_learning_table():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS trade_learning (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        time TEXT,
        symbol TEXT,
        strategy TEXT,
        sector TEXT,
        confidence REAL,
        market_bias TEXT,
        entry_price REAL,
        exit_price REAL,
        qty INTEGER,
        realized_pnl REAL,
        return_pct REAL,
        outcome TEXT,
        won INTEGER,
        exit_reason TEXT
    )
    """)

    conn.commit()
    conn.close()


_ensure_trade_learning_table()


def _row_to_record(row):
    return {
        "id": row["id"],
        "time": row["time"],
        "symbol": row["symbol"],
        "strategy": row["strategy"],
        "sector": row["sector"],
        "confidence": round(float(row["confidence"] or 0), 2),
        "market_bias": row["market_bias"],
        "entry_price": round(float(row["entry_price"] or 0), 2),
        "exit_price": round(float(row["exit_price"] or 0), 2),
        "qty": int(row["qty"] or 0),
        "realized_pnl": round(float(row["realized_pnl"] or 0), 2),
        "return_pct": round(float(row["return_pct"] or 0), 2),
        "outcome": row["outcome"],
        "won": bool(row["won"]),
        "exit_reason": row["exit_reason"],
    }


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
    outcome = classify_outcome(realized_pnl)
    now = datetime.utcnow().isoformat()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO trade_learning (
            time, symbol, strategy, sector, confidence, market_bias,
            entry_price, exit_price, qty, realized_pnl, return_pct,
            outcome, won, exit_reason
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now,
            symbol.upper(),
            strategy,
            sector,
            round(float(confidence), 2),
            market_bias,
            round(entry_price, 2),
            round(exit_price, 2),
            qty,
            round(realized_pnl, 2),
            round(return_pct, 2),
            outcome,
            1 if outcome == "WIN" else 0,
            exit_reason,
        ),
    )

    record_id = cur.lastrowid
    conn.commit()
    conn.close()

    return {
        "id": record_id,
        "time": now,
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
        "outcome": outcome,
        "won": outcome == "WIN",
        "exit_reason": exit_reason,
    }


def get_trade_intelligence_records():
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT *
        FROM trade_learning
        ORDER BY id DESC
        """
    ).fetchall()
    conn.close()

    return [_row_to_record(row) for row in rows]


def clear_trade_intelligence():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM trade_learning")
    conn.commit()
    conn.close()

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
                "scratches": 0,
                "total_pnl": 0.0,
                "total_return_pct": 0.0,
            }

        group = groups[name]
        group["trades"] += 1
        group["total_pnl"] += record["realized_pnl"]
        group["total_return_pct"] += record["return_pct"]

        outcome = record.get("outcome") or classify_outcome(record["realized_pnl"])

        if outcome == "WIN":
            group["wins"] += 1
        elif outcome == "LOSS":
            group["losses"] += 1
        else:
            group["scratches"] += 1

    for group in groups.values():
        trades = group["trades"]
        decisive_trades = group["wins"] + group["losses"]

        group["win_rate"] = round((group["wins"] / decisive_trades) * 100, 2) if decisive_trades else 0.0
        group["loss_rate"] = round((group["losses"] / decisive_trades) * 100, 2) if decisive_trades else 0.0
        group["scratch_rate"] = round((group["scratches"] / trades) * 100, 2) if trades else 0.0
        group["avg_return_pct"] = round(group["total_return_pct"] / trades, 2) if trades else 0.0
        group["total_pnl"] = round(group["total_pnl"], 2)

    return groups


def get_trade_intelligence_summary():
    records = get_trade_intelligence_records()

    wins = [r for r in records if (r.get("outcome") or classify_outcome(r["realized_pnl"])) == "WIN"]
    losses = [r for r in records if (r.get("outcome") or classify_outcome(r["realized_pnl"])) == "LOSS"]
    scratches = [r for r in records if (r.get("outcome") or classify_outcome(r["realized_pnl"])) == "SCRATCH"]

    total_trades = len(records)
    decisive_trades = len(wins) + len(losses)

    total_pnl = round(sum(r["realized_pnl"] for r in records), 2)

    win_rate = round((len(wins) / decisive_trades) * 100, 2) if decisive_trades else 0.0
    loss_rate = round((len(losses) / decisive_trades) * 100, 2) if decisive_trades else 0.0
    scratch_rate = round((len(scratches) / total_trades) * 100, 2) if total_trades else 0.0

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
        "decisive_trades": decisive_trades,
        "wins": len(wins),
        "losses": len(losses),
        "scratches": len(scratches),
        "total_pnl": total_pnl,
        "win_rate": win_rate,
        "loss_rate": loss_rate,
        "scratch_rate": scratch_rate,
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