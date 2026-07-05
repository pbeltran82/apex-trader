from backend.trade_intelligence import get_trade_intelligence_summary


def clamp(value, minimum=0, maximum=100):
    return max(minimum, min(maximum, value))


def get_strategy_adjustment(strategy_name):
    summary = get_trade_intelligence_summary()
    strategies = summary.get("strategies", {})
    strategy = strategies.get(strategy_name)

    if not strategy:
        return {
            "adjustment": 0,
            "reason": "Not enough strategy history yet.",
        }

    wins = strategy.get("wins", 0)
    losses = strategy.get("losses", 0)
    scratches = strategy.get("scratches", 0)
    decisive_trades = wins + losses
    avg_return = strategy.get("avg_return_pct", 0)

    if decisive_trades < 3:
        return {
            "adjustment": 0,
            "reason": (
                f"Not enough decisive {strategy_name} trades yet. "
                f"Scratches: {scratches}."
            ),
        }

    win_rate = round((wins / decisive_trades) * 100, 2)

    if win_rate >= 65 and avg_return > 0:
        return {
            "adjustment": 5,
            "reason": (
                f"{strategy_name} is strong: {wins} wins vs {losses} losses "
                f"over {decisive_trades} decisive trades."
            ),
        }

    if win_rate <= 40 or avg_return < 0:
        return {
            "adjustment": -8,
            "reason": (
                f"{strategy_name} is weak: {losses} losses vs {wins} wins "
                f"over {decisive_trades} decisive trades."
            ),
        }

    return {
        "adjustment": 0,
        "reason": (
            f"{strategy_name} is neutral: {wins} wins vs {losses} losses "
            f"over {decisive_trades} decisive trades."
        ),
    }


def get_sector_adjustment(sector_name):
    summary = get_trade_intelligence_summary()
    sectors = summary.get("sectors", {})
    sector = sectors.get(sector_name)

    if not sector:
        return {
            "adjustment": 0,
            "reason": "Not enough sector history yet.",
        }

    wins = sector.get("wins", 0)
    losses = sector.get("losses", 0)
    scratches = sector.get("scratches", 0)
    decisive_trades = wins + losses
    avg_return = sector.get("avg_return_pct", 0)

    if decisive_trades < 3:
        return {
            "adjustment": 0,
            "reason": (
                f"Not enough decisive {sector_name} sector trades yet. "
                f"Scratches: {scratches}."
            ),
        }

    win_rate = round((wins / decisive_trades) * 100, 2)

    if win_rate >= 65 and avg_return > 0:
        return {
            "adjustment": 4,
            "reason": (
                f"{sector_name} sector is strong: {wins} wins vs {losses} losses "
                f"over {decisive_trades} decisive trades."
            ),
        }

    if win_rate <= 40 or avg_return < 0:
        return {
            "adjustment": -6,
            "reason": (
                f"{sector_name} sector is weak: {losses} losses vs {wins} wins "
                f"over {decisive_trades} decisive trades."
            ),
        }

    return {
        "adjustment": 0,
        "reason": (
            f"{sector_name} sector is neutral: {wins} wins vs {losses} losses "
            f"over {decisive_trades} decisive trades."
        ),
    }


def adjust_trade_confidence(base_confidence, strategy="Momentum", sector="Other"):
    base_confidence = float(base_confidence)

    strategy_result = get_strategy_adjustment(strategy)
    sector_result = get_sector_adjustment(sector)

    adjusted = clamp(
        base_confidence
        + strategy_result["adjustment"]
        + sector_result["adjustment"]
    )

    return {
        "base_confidence": round(base_confidence, 2),
        "adjusted_confidence": round(adjusted, 2),
        "strategy": strategy,
        "sector": sector,
        "strategy_adjustment": strategy_result,
        "sector_adjustment": sector_result,
        "total_adjustment": round(adjusted - base_confidence, 2),
    }