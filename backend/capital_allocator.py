from typing import List


def allocate_capital(trades: List[dict]):
    """
    Rank approved trades and allocate capital proportionally
    to their decision scores.
    """

    approved = [
        trade
        for trade in trades
        if trade.get("approved")
    ]

    if not approved:
        return {
            "total_trades": 0,
            "allocations": [],
        }

    total_score = sum(
        trade["decision_score"]
        for trade in approved
    )

    allocations = []

    for trade in sorted(
        approved,
        key=lambda x: x["decision_score"],
        reverse=True,
    ):
        weight = trade["decision_score"] / total_score

        allocations.append({
            "symbol": trade["symbol"],
            "decision_score": trade["decision_score"],
            "sector": trade["sector"],
            "weight_pct": round(weight * 100, 2),
            "recommended_allocation_pct":
                trade["recommended_allocation_pct"],
        })

    return {
        "total_trades": len(approved),
        "allocations": allocations,
    }