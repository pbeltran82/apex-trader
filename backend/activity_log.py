from datetime import datetime

activity_log = []


def log_event(message, event_type="INFO"):
    activity_log.insert(
        0,
        {
            "time": datetime.now().strftime("%H:%M:%S"),
            "type": event_type,
            "message": message,
        },
    )

    # Keep only the newest 250 events
    del activity_log[250:]


def get_activity():
    return activity_log


def clear_activity():
    activity_log.clear()

    return {"ok": True}