from datetime import datetime

from backend.portfolio_live import build_portfolio_live
from backend.trade_intelligence import get_trade_intelligence_summary
from backend.autopilot_orchestrator import status as autopilot_status
from backend.position_monitor import monitor_status
from backend.adaptive_intelligence import get_adaptive_state


def build_recommendation(adaptive, portfolio):
    mode = adaptive.get("mode", "NORMAL")
    exposure = portfolio.get("exposure_pct", 0)
    cash = portfolio.get("cash", 0)
    positions = portfolio.get("open_positions", 0)

    if mode == "DEFENSIVE":
        return {
            "level": "WARNING",
            "action": "Reduce Risk",
            "message": (
                "Kyle is in DEFENSIVE mode after recent losses. "
                "Avoid opening new positions unless an exceptional setup appears."
            ),
        }

    if mode == "CAUTIOUS":
        return {
            "level": "CAUTION",
            "action": "Trade Selectively",
            "message": (
                "Kyle recommends reducing position size until performance improves."
            ),
        }

    if exposure > 80:
        return {
            "level": "WARNING",
            "action": "Manage Existing Positions",
            "message": (
                "Portfolio exposure is already high. "
                "Focus on managing current trades instead of opening new ones."
            ),
        }

    if positions == 0 and cash > 5000:
        return {
            "level": "INFO",
            "action": "Deploy Capital",
            "message": (
                "Kyle has significant cash available and is ready "
                "to deploy capital into qualified opportunities."
            ),
        }

    return {
        "level": "GOOD",
        "action": "Operate Normally",
        "message": "Kyle is operating within normal risk parameters.",
    }


def build_mission_control():
    portfolio = build_portfolio_live()
    learning = get_trade_intelligence_summary()
    autopilot = autopilot_status()
    monitor = monitor_status()
    adaptive = get_adaptive_state()

    recommendation = build_recommendation(adaptive, portfolio)

    return {
        "generated": datetime.utcnow().isoformat(),

        "system": {
            "name": "Kyle",
            "status": "RUNNING" if monitor.get("running") else "IDLE",
            "autopilot_running": autopilot.get("running"),
            "position_monitor_running": monitor.get("running"),
        },

        "portfolio": {
            "cash": portfolio.get("cash"),
            "equity": portfolio.get("equity"),
            "exposure_pct": portfolio.get("exposure_pct"),
            "open_positions": portfolio.get("open_positions"),
            "unrealized_pnl": portfolio.get("unrealized_pnl"),
            "positions": portfolio.get("positions", []),
        },

        "learning": {
            "total_trades": learning.get("total_trades_learned"),
            "wins": learning.get("wins"),
            "losses": learning.get("losses"),
            "scratches": learning.get("scratches"),
            "win_rate": learning.get("win_rate"),
            "loss_rate": learning.get("loss_rate"),
            "scratch_rate": learning.get("scratch_rate"),
            "profit_factor": learning.get("profit_factor"),
            "best_strategy": learning.get("best_strategy"),
            "best_sector": learning.get("best_sector"),
        },

        "decision_mode": {
            "mode": adaptive.get("mode"),
            "confidence_adjustment": adaptive.get("confidence_adjustment"),
            "allocation_multiplier": adaptive.get("allocation_multiplier"),
            "reason": adaptive.get("reason"),
            "recent_trades": adaptive.get("recent_trades"),
            "recent_win_rate": adaptive.get("recent_win_rate"),
            "recent_loss_rate": adaptive.get("recent_loss_rate"),
            "recent_scratch_rate": adaptive.get("recent_scratch_rate"),
            "consecutive_losses": adaptive.get("consecutive_losses"),
        },

        "recommendation": recommendation,

        "autopilot": autopilot,

        "health": {
            "position_monitor_thread_alive": monitor.get("thread_alive"),
            "autopilot_thread_alive": autopilot.get("thread_alive"),
            "last_autopilot_tick": autopilot.get("last_tick"),
            "last_autopilot_error": autopilot.get("last_error"),
        },

        "summary": (
            f"Kyle is managing {portfolio.get('open_positions', 0)} open position(s) "
            f"with ${portfolio.get('cash', 0):,.2f} cash and "
            f"{portfolio.get('exposure_pct', 0)}% exposure."
        ),
    }