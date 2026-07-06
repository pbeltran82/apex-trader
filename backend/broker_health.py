from datetime import datetime

_state = {
    "connected": True,
    "provider": "SIMULATION",
    "last_heartbeat": None,
    "last_error": None,
}


def heartbeat():
    _state["connected"] = True
    _state["last_heartbeat"] = datetime.utcnow().isoformat()
    return status()


def disconnect(error="Broker unavailable"):
    _state["connected"] = False
    _state["last_error"] = error
    return status()


def reconnect():
    _state["connected"] = True
    _state["last_error"] = None
    _state["last_heartbeat"] = datetime.utcnow().isoformat()
    return status()


def status():
    return {
        "connected": _state["connected"],
        "provider": _state["provider"],
        "last_heartbeat": _state["last_heartbeat"],
        "last_error": _state["last_error"],
    }