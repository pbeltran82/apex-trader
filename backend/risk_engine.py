from backend.emergency_stop import status as emergency_stop_status
from backend.trade_history import get_today_realized_pnl
from backend.drawdown_guard import get_drawdown_status


# ===== Risk Policy =====

MAX_DAILY_LOSS = -500.0
MAX_DRAWDOWN_PCT = 10.0
MAX_CONSECUTIVE_LOSSES = 5


def build_risk_engine():
    """
    Enterprise Risk Engine.

    Determines whether Kyle is allowed to open NEW positions.

    Existing positions should still be managed even when
    new trading is blocked.
    """

    # Lazy import prevents circular imports.
    from backend.mission_control import build_mission_control

    mission = build_mission_control()

    portfolio = mission["portfolio"]

    reasons = []
    trading_allowed = True

    # ----------------------------------------------------
    # Emergency Stop
    # ----------------------------------------------------

    emergency = emergency_stop_status()

    if emergency["emergency_stop_enabled"]:
        trading_allowed = False
        reasons.append(
            f"Emergency stop is active: {emergency['reason']}"
        )

    # ----------------------------------------------------
    # Consecutive Loss Guard
    # ----------------------------------------------------

    consecutive_losses = mission["decision_mode"].get(
        "consecutive_losses",
        0,
    )

    if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
        trading_allowed = False
        reasons.append(
            f"{consecutive_losses} consecutive losses."
        )

    # ----------------------------------------------------
    # Drawdown Guard
    # ----------------------------------------------------

    drawdown = get_drawdown_status()
    drawdown_pct = drawdown["drawdown_pct"]

    if drawdown_pct >= MAX_DRAWDOWN_PCT:
        trading_allowed = False
        reasons.append(
            f"Drawdown exceeded {MAX_DRAWDOWN_PCT}%."
        )

    # ----------------------------------------------------
    # Daily Loss Guard
    # ----------------------------------------------------

    daily_pnl = get_today_realized_pnl()

    if daily_pnl <= MAX_DAILY_LOSS:
        trading_allowed = False
        reasons.append(
            f"Daily loss exceeded ${abs(MAX_DAILY_LOSS):,.0f}."
        )

    # ----------------------------------------------------
    # Default
    # ----------------------------------------------------

    if not reasons:
        reasons.append(
            "All enterprise risk checks passed."
        )

    return {

        "trading_allowed": trading_allowed,

        "daily_pnl": daily_pnl,

        "drawdown_pct": drawdown_pct,

        "drawdown": drawdown,

        "consecutive_losses": consecutive_losses,

        "emergency_stop": emergency,

        "limits": {

            "daily_loss_limit": MAX_DAILY_LOSS,

            "drawdown_limit_pct": MAX_DRAWDOWN_PCT,

            "max_consecutive_losses": MAX_CONSECUTIVE_LOSSES,

        },

        "portfolio": {

            "cash": portfolio["cash"],

            "equity": portfolio["equity"],

            "exposure_pct": portfolio["exposure_pct"],

            "open_positions": portfolio["open_positions"],

        },

        "reasons": reasons,
    }