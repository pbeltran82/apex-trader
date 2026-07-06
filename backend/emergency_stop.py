from datetime import datetime

_state = {
    "enabled": False,
    "reason": None,
    "activated_at": None,
    "cleared_at": None,
}


def activate_emergency_stop(reason="Manual emergency stop activated."):
    _state["enabled"] = True
    _state["reason"] = reason
    _state["activated_at"] = datetime.utcnow().isoformat()
    _state["cleared_at"] = None

    return status()


def clear_emergency_stop():
    _state["enabled"] = False
    _state["reason"] = None
    _state["cleared_at"] = datetime.utcnow().isoformat()

    return status()


def status():
    return {
        "emergency_stop_enabled": _state["enabled"],
        "reason": _state["reason"],
        "activated_at": _state["activated_at"],
        "cleared_at": _state["cleared_at"],
    }