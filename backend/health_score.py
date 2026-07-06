from backend.mission_control import build_mission_control


def build_health_score():
    mission = build_mission_control()

    score = 100
    reasons = []

    # Adaptive Mode
    mode = mission["decision_mode"]["mode"]

    if mode == "DEFENSIVE":
        score -= 25
        reasons.append("Kyle is operating in DEFENSIVE mode.")
    elif mode == "CAUTIOUS":
        score -= 10
        reasons.append("Kyle is operating in CAUTIOUS mode.")

    # Win Rate
    win_rate = mission["learning"]["win_rate"] or 0

    if win_rate < 40:
        score -= 20
        reasons.append("Recent win rate is below 40%.")
    elif win_rate < 55:
        score -= 10
        reasons.append("Recent win rate is average.")

    # Profit Factor
    pf = mission["learning"]["profit_factor"] or 0

    if pf < 1:
        score -= 15
        reasons.append("Profit factor is below 1.")

    # Autopilot
    if not mission["autopilot"]["running"]:
        score -= 5
        reasons.append("Autopilot is currently stopped.")

    # Position Monitor
    if not mission["health"]["position_monitor_thread_alive"]:
        score -= 25
        reasons.append("Position Monitor is offline.")

    # Portfolio Exposure
    exposure = mission["portfolio"]["exposure_pct"]

    if exposure > 90:
        score -= 10
        reasons.append("Portfolio exposure is very high.")

    score = max(0, min(score, 100))

    if score >= 90:
        grade = "A"
        status = "EXCELLENT"
    elif score >= 80:
        grade = "B"
        status = "HEALTHY"
    elif score >= 70:
        grade = "C"
        status = "CAUTION"
    elif score >= 60:
        grade = "D"
        status = "AT RISK"
    else:
        grade = "F"
        status = "CRITICAL"

    return {
        "score": score,
        "grade": grade,
        "status": status,
        "reasons": reasons,
    }