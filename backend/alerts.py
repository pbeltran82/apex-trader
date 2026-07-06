from backend.mission_control import build_mission_control
from backend.event_log import get_events


def build_alerts():
    mission = build_mission_control()

    alerts = []

    mode = mission["decision_mode"]["mode"]

    if mode == "DEFENSIVE":
        alerts.append({
            "severity": "WARNING",
            "title": "Defensive Mode",
            "message": (
                "Kyle has reduced confidence and allocation "
                "because of recent performance."
            ),
        })

    if mission["recommendation"]["level"] in ("INFO", "GOOD"):
        alerts.append({
            "severity": mission["recommendation"]["level"],
            "title": mission["recommendation"]["action"],
            "message": mission["recommendation"]["message"],
    })

    exposure = mission["portfolio"]["exposure_pct"]

    if exposure > 80:
        alerts.append({
            "severity": "WARNING",
            "title": "High Exposure",
            "message": (
                f"Portfolio exposure is {exposure:.1f}%."
            ),
        })

    cash = mission["portfolio"]["cash"]

    if cash < 1000:
        alerts.append({
            "severity": "INFO",
            "title": "Low Cash",
            "message": (
                "Available cash is becoming limited."
            ),
        })

    recent = get_events(limit=5)

    for event in recent:
        if event["severity"] in ("WARNING", "ERROR"):
            alerts.append({
                "severity": event["severity"],
                "title": event["type"],
                "message": event["message"],
            })

    return alerts