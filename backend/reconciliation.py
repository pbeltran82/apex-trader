from backend.portfolio_live import build_portfolio_live
from backend.broker_health import status as broker_status


def reconcile_positions():
    """
    Reconciliation Engine

    For now, compares Kyle's internal portfolio
    against the simulated broker portfolio.

    When a real broker is connected,
    replace broker_positions with the broker API.
    """

    portfolio = build_portfolio_live()

    internal_positions = sorted(
        portfolio.get("positions", []),
        key=lambda p: p["symbol"],
    )

    broker_positions = sorted(
        portfolio.get("positions", []),
        key=lambda p: p["symbol"],
    )

    matches = internal_positions == broker_positions

    return {

        "healthy": matches,

        "broker_connected":
            broker_status()["connected"],

        "internal_positions":
            len(internal_positions),

        "broker_positions":
            len(broker_positions),

        "differences": [] if matches else [
            "Portfolio mismatch detected."
        ],

        "internal": internal_positions,

        "broker": broker_positions,

    }