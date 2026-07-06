from fastapi import APIRouter

from backend.mission_control import build_mission_control

router = APIRouter()


@router.get("/ceo-briefing")
def ceo_briefing():
    mc = build_mission_control()

    portfolio = mc.get("portfolio", {})
    learning = mc.get("learning", {})
    decision = mc.get("decision_mode", {})
    recommendation = mc.get("recommendation", {})
    system = mc.get("system", {})

    reason = decision.get("reason", "current market conditions")
    reason = reason.replace("Kyle is reducing risk.", "")
    reason = reason.replace("Kyle is ", "")
    reason = reason.strip().rstrip(".").lower()

    briefing = (
        f"Good morning. "
        f"Kyle is operating in {decision.get('mode')} mode because {reason}. "
        f"The portfolio currently holds "
        f"{portfolio.get('open_positions', 0)} open position(s) "
        f"with ${portfolio.get('cash', 0):,.2f} in cash and "
        f"{portfolio.get('exposure_pct', 0)}% exposure. "
        f"Trading performance stands at "
        f"{learning.get('wins')} win(s), "
        f"{learning.get('losses')} loss(es), "
        f"and {learning.get('scratches')} scratch trade(s), "
        f"for a win rate of {learning.get('win_rate')}%. "
        f"Today's priority is to "
        f"{recommendation.get('action', 'Operate Normally').lower()}."
    )

    return {
        "title": "Kyle CEO Briefing",
        "status": system.get("status"),
        "autopilot": (
            "RUNNING"
            if system.get("autopilot_running")
            else "OFF"
        ),
        "position_monitor": (
            "RUNNING"
            if system.get("position_monitor_running")
            else "OFF"
        ),
        "mode": decision.get("mode"),
        "headline": recommendation.get("action"),
        "briefing": briefing,
        "executive_priority": recommendation.get("message"),
        "recommendation": recommendation,
        "key_metrics": {
            "cash": portfolio.get("cash"),
            "equity": portfolio.get("equity"),
            "exposure_pct": portfolio.get("exposure_pct"),
            "open_positions": portfolio.get("open_positions"),
            "win_rate": learning.get("win_rate"),
            "profit_factor": learning.get("profit_factor"),
            "confidence_adjustment": decision.get("confidence_adjustment"),
            "allocation_multiplier": decision.get("allocation_multiplier"),
        },
    }