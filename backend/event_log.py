from datetime import datetime

events = []


def log_event(
    event_type,
    message,
    data=None,
    severity="INFO",
    category="SYSTEM",
):
    event = {
        "id": len(events) + 1,
        "time": datetime.utcnow().isoformat(),
        "type": event_type,
        "severity": severity.upper(),
        "category": category.upper(),
        "message": message,
        "data": data or {},
    }

    events.insert(0, event)
    events[:] = events[:500]

    return event


def get_events(
    limit=50,
    severity=None,
    category=None,
):
    results = events

    if severity:
        results = [
            e for e in results
            if e["severity"] == severity.upper()
        ]

    if category:
        results = [
            e for e in results
            if e["category"] == category.upper()
        ]

    return results[:limit]


def build_timeline(limit=25):
    return [
        {
            "time": e["time"],
            "icon": icon_for(e),
            "headline": e["message"],
            "severity": e["severity"],
            "category": e["category"],
        }
        for e in events[:limit]
    ]


def clear_events():
    events.clear()
    return {"ok": True, "count": 0}


def icon_for(event):
    icons = {
        "AUTOPILOT_TICK": "🤖",
        "DAILY_SCHEDULER": "📅",
        "EXECUTION_MANAGER": "⚡",
        "POSITION_MONITOR": "👀",
        "MISSION_CONTROL": "🧠",
        "EXIT_MANAGER": "🚪",
        "TRADE_FILLED": "✅",
        "TRADE_REJECTED": "❌",
        "ERROR": "🔥",
    }

    return icons.get(event["type"], "•")