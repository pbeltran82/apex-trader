from copy import deepcopy

MAX_POSITION_PCT = 10.0
MAX_SECTOR_PCT = 30.0


def apply_constraints(portfolio):
    """
    Apply portfolio-level limits to proposed allocations.
    """

    portfolio = deepcopy(portfolio)

    sector_totals = {}

    for trade in portfolio["allocations"]:

        # Position limit
        if trade["recommended_allocation_pct"] > MAX_POSITION_PCT:
            trade["recommended_allocation_pct"] = MAX_POSITION_PCT
            trade.setdefault("adjustments", []).append(
                f"Capped at {MAX_POSITION_PCT}% maximum position."
            )

        sector = trade["sector"]

        sector_totals.setdefault(sector, 0)
        sector_totals[sector] += trade["recommended_allocation_pct"]

    # Sector caps
    for sector, total in sector_totals.items():

        if total <= MAX_SECTOR_PCT:
            continue

        scale = MAX_SECTOR_PCT / total

        for trade in portfolio["allocations"]:

            if trade["sector"] != sector:
                continue

            original = trade["recommended_allocation_pct"]

            trade["recommended_allocation_pct"] = round(
                original * scale,
                2,
            )

            trade.setdefault("adjustments", []).append(
                f"Scaled because {sector} exceeded {MAX_SECTOR_PCT}%."
            )

    portfolio["constraints_applied"] = True

    return portfolio