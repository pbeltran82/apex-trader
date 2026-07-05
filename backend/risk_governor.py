from datetime import datetime

from backend.portfolio_live import build_portfolio_live
from backend.trade_history import get_trade_stats
from backend.activity_log import log_event


risk_state = {
    "enabled": True,
    "safe": True,
    "shutdown": False,
    "reason": None,
    "last_check": None,
    "daily_loss_limit": -300.0,
    "max_drawdown_pct": 5.0,
    "max_positions": 5,
    "max_exposure_pct": 25.0,
    "max_consecutive_losses": 3,
    "manual_stop": False,
}


def check_risk():
    portfolio = build_portfolio_live()
    stats = get_trade_stats()

    total_pnl = round(portfolio["equity"] - 10000.0, 2)
    exposure_pct = portfolio["exposure_pct"]
    open_positions = portfolio["open_positions"]
    realized_pnl = stats.get("realized_pnl", 0.0)

    risk_state["last_check"] = datetime.utcnow().isoformat()
    risk_state["safe"] = True
    risk_state["shutdown"] = False
    risk_state["reason"] = None

    if not risk_state["enabled"]:
        risk_state["safe"] = False
        risk_state["shutdown"] = True
        risk_state["reason"] = "Risk Governor disabled trading."
    elif risk_state["manual_stop"]:
        risk_state["safe"] = False
        risk_state["shutdown"] = True
        risk_state["reason"] = "Manual emergency stop is active."
    elif total_pnl <= risk_state["daily_loss_limit"]:
        risk_state["safe"] = False
        risk_state["shutdown"] = True
        risk_state["reason"] = "Daily loss limit exceeded."
    elif open_positions > risk_state["max_positions"]:
        risk_state["safe"] = False
        risk_state["shutdown"] = True
        risk_state["reason"] = "Maximum open positions exceeded."
    elif exposure_pct > risk_state["max_exposure_pct"]:
        risk_state["safe"] = False
        risk_state["shutdown"] = True
        risk_state["reason"] = "Maximum portfolio exposure exceeded."

    result = {
        "safe": risk_state["safe"],
        "shutdown": risk_state["shutdown"],
        "reason": risk_state["reason"],
        "total_pnl": total_pnl,
        "realized_pnl": realized_pnl,
        "exposure_pct": exposure_pct,
        "open_positions": open_positions,
        "limits": {
            "daily_loss_limit": risk_state["daily_loss_limit"],
            "max_drawdown_pct": risk_state["max_drawdown_pct"],
            "max_positions": risk_state["max_positions"],
            "max_exposure_pct": risk_state["max_exposure_pct"],
            "max_consecutive_losses": risk_state["max_consecutive_losses"],
        },
        "state": risk_state,
    }

    if risk_state["shutdown"]:
        log_event(f"Risk Governor shutdown: {risk_state['reason']}", "ERROR")

    return result


def get_risk_status():
    return check_risk()


def activate_manual_stop():
    risk_state["manual_stop"] = True
    risk_state["safe"] = False
    risk_state["shutdown"] = True
    risk_state["reason"] = "Manual emergency stop is active."
    log_event("Manual emergency stop activated.", "ERROR")
    return risk_state


def clear_manual_stop():
    risk_state["manual_stop"] = False
    risk_state["safe"] = True
    risk_state["shutdown"] = False
    risk_state["reason"] = None
    log_event("Manual emergency stop cleared.", "SYSTEM")
    return risk_state