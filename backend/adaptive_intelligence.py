from backend.trade_intelligence import get_trade_intelligence_records, classify_outcome


def get_adaptive_state(limit=20):
    records = get_trade_intelligence_records()[:limit]

    if not records:
        return {
            "mode": "NORMAL",
            "confidence_adjustment": 0,
            "allocation_multiplier": 1.0,
            "reason": "Not enough recent trade history yet.",
            "recent_trades": 0,
            "decisive_trades": 0,
            "recent_win_rate": 0.0,
            "recent_loss_rate": 0.0,
            "recent_scratch_rate": 0.0,
            "consecutive_losses": 0,
        }

    wins = []
    losses = []
    scratches = []

    for record in records:
        outcome = record.get("outcome") or classify_outcome(record.get("realized_pnl", 0))

        if outcome == "WIN":
            wins.append(record)
        elif outcome == "LOSS":
            losses.append(record)
        else:
            scratches.append(record)

    decisive_trades = len(wins) + len(losses)

    recent_win_rate = (
        round((len(wins) / decisive_trades) * 100, 2)
        if decisive_trades
        else 0.0
    )

    recent_loss_rate = (
        round((len(losses) / decisive_trades) * 100, 2)
        if decisive_trades
        else 0.0
    )

    recent_scratch_rate = round((len(scratches) / len(records)) * 100, 2)

    consecutive_losses = 0
    for record in records:
        outcome = record.get("outcome") or classify_outcome(record.get("realized_pnl", 0))

        if outcome == "LOSS":
            consecutive_losses += 1
            continue

        if outcome == "SCRATCH":
            continue

        break

    if consecutive_losses >= 3 or (decisive_trades >= 3 and recent_loss_rate >= 65):
        return {
            "mode": "DEFENSIVE",
            "confidence_adjustment": -6,
            "allocation_multiplier": 0.6,
            "reason": "Recent losses are elevated. Kyle is reducing risk.",
            "recent_trades": len(records),
            "decisive_trades": decisive_trades,
            "recent_win_rate": recent_win_rate,
            "recent_loss_rate": recent_loss_rate,
            "recent_scratch_rate": recent_scratch_rate,
            "consecutive_losses": consecutive_losses,
        }

    if len(records) >= 3 and recent_scratch_rate >= 70:
        return {
            "mode": "CAUTIOUS",
            "confidence_adjustment": 0,
            "allocation_multiplier": 0.75,
            "reason": "Recent trades are mostly breakeven. Kyle is reducing size while waiting for clearer edge.",
            "recent_trades": len(records),
            "decisive_trades": decisive_trades,
            "recent_win_rate": recent_win_rate,
            "recent_loss_rate": recent_loss_rate,
            "recent_scratch_rate": recent_scratch_rate,
            "consecutive_losses": consecutive_losses,
        }

    if decisive_trades >= 5 and recent_win_rate >= 70:
        return {
            "mode": "AGGRESSIVE",
            "confidence_adjustment": 3,
            "allocation_multiplier": 1.2,
            "reason": "Recent performance is strong. Kyle can increase conviction slightly.",
            "recent_trades": len(records),
            "decisive_trades": decisive_trades,
            "recent_win_rate": recent_win_rate,
            "recent_loss_rate": recent_loss_rate,
            "recent_scratch_rate": recent_scratch_rate,
            "consecutive_losses": consecutive_losses,
        }

    return {
        "mode": "NORMAL",
        "confidence_adjustment": 0,
        "allocation_multiplier": 1.0,
        "reason": "Recent performance is normal.",
        "recent_trades": len(records),
        "decisive_trades": decisive_trades,
        "recent_win_rate": recent_win_rate,
        "recent_loss_rate": recent_loss_rate,
        "recent_scratch_rate": recent_scratch_rate,
        "consecutive_losses": consecutive_losses,
    }