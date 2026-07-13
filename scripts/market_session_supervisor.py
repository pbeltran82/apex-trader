#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sys
import time
from typing import Any, Callable, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# When this file is launched directly, Python puts scripts/ rather than the
# repository root on sys.path. Add the root explicitly so imports work from
# systemd, cron, shells, and tests without relying only on external PYTHONPATH.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.market_data import _fetch_alpaca_clock


API_BASE = os.getenv("KYLE_LOCAL_API_BASE", "http://127.0.0.1:8000").rstrip("/")
POLL_SECONDS = max(5, int(os.getenv("KYLE_SESSION_POLL_SECONDS", "30")))
MAX_WAIT_SECONDS = max(60, int(os.getenv("KYLE_SESSION_MAX_WAIT_SECONDS", "7200")))
REPORT_DIR = Path(os.getenv("KYLE_SESSION_REPORT_DIR", "data/session_reports"))
LOCK_FILE = Path(os.getenv("KYLE_SESSION_LOCK_FILE", "/tmp/kyle-session-supervisor.lock"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(message: str, **details: Any) -> None:
    payload = {"timestamp": utc_now(), "message": message, **details}
    print(json.dumps(payload, sort_keys=True), flush=True)


def api_json(path: str, method: str = "GET") -> Dict[str, Any]:
    request = Request(
        API_BASE + path,
        method=method,
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(f"{method} {path} failed: {error}") from error


@dataclass
class SessionResult:
    outcome: str
    reason: str
    started_observer: bool = False
    stopped_observer: bool = False
    opened_at: Optional[str] = None
    closed_at: Optional[str] = None


class MarketSessionSupervisor:
    def __init__(
        self,
        *,
        clock: Callable[[], Dict[str, Any]] = _fetch_alpaca_clock,
        request: Callable[[str, str], Dict[str, Any]] = api_json,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], str] = utc_now,
        poll_seconds: int = POLL_SECONDS,
        max_wait_seconds: int = MAX_WAIT_SECONDS,
    ) -> None:
        self.clock = clock
        self.request = request
        self.sleep = sleep
        self.now = now
        self.poll_seconds = poll_seconds
        self.max_wait_seconds = max_wait_seconds

    def _readiness_passes(self) -> tuple[bool, Dict[str, Any]]:
        readiness = self.request("/api/intelligence/readiness", "GET")
        operational = bool(readiness.get("operationally_ready_for_paper_trading"))
        hardening = readiness.get("hardening") or {}
        hardened = bool(
            hardening.get("history_freshness_enforced")
            and hardening.get("stop_before_execution_enforced")
        )
        return operational and hardened, readiness

    def _ensure_shadow(self) -> Dict[str, Any]:
        status = self.request("/api/shadow", "GET")
        if status.get("enabled"):
            return status
        enabled = self.request("/api/shadow/enable", "POST")
        if not enabled.get("ok"):
            raise RuntimeError(enabled.get("message") or "Shadow mode could not be enabled.")
        status = enabled.get("status") or {}
        if not status.get("enabled"):
            raise RuntimeError("Shadow enable response did not confirm enabled state.")
        return status

    def _ensure_observer_started(self) -> bool:
        status = self.request("/api/autonomous-trader/status", "GET")
        if status.get("running"):
            return False
        started = self.request("/api/autonomous-trader/start", "POST")
        if not started.get("running"):
            raise RuntimeError(
                started.get("last_reason")
                or "Observer start response did not confirm running state."
            )
        return True

    def _stop_observer(self) -> bool:
        status = self.request("/api/autonomous-trader/status", "GET")
        if not status.get("running"):
            return False
        stopped = self.request("/api/autonomous-trader/stop", "POST")
        if stopped.get("running"):
            raise RuntimeError("Observer stop response still reports running=true.")
        return True

    def run(self) -> SessionResult:
        self.request("/", "GET")
        readiness_ok, readiness = self._readiness_passes()
        if not readiness_ok:
            return SessionResult(
                "SKIPPED",
                "Operational readiness or mandatory hardening failed.",
            )

        clock = self.clock()
        if not clock.get("ok"):
            return SessionResult("SKIPPED", "Alpaca market clock could not be verified.")

        waited = 0
        while not clock.get("is_open"):
            if waited >= self.max_wait_seconds:
                return SessionResult(
                    "SKIPPED",
                    "Market did not open within the configured wait window.",
                )
            next_open = clock.get("next_open")
            log("Waiting for verified market open", next_open=next_open, waited_seconds=waited)
            self.sleep(self.poll_seconds)
            waited += self.poll_seconds
            clock = self.clock()
            if not clock.get("ok"):
                return SessionResult("SKIPPED", "Alpaca market clock failed while waiting.")

        self._ensure_shadow()
        started = self._ensure_observer_started()
        opened_at = clock.get("timestamp") or self.now()
        log("Shadow observer active", opened_at=opened_at, started_by_supervisor=started)

        while True:
            self.sleep(self.poll_seconds)
            clock = self.clock()
            if not clock.get("ok"):
                # Fail closed: stop observation when market state cannot be verified.
                stopped = self._stop_observer()
                return SessionResult(
                    "STOPPED_FAIL_CLOSED",
                    "Alpaca market clock failed during the session.",
                    started_observer=started,
                    stopped_observer=stopped,
                    opened_at=opened_at,
                    closed_at=self.now(),
                )
            if not clock.get("is_open"):
                stopped = self._stop_observer()
                closed_at = clock.get("timestamp") or self.now()
                return SessionResult(
                    "COMPLETED",
                    "Verified market close; shadow observer stopped.",
                    started_observer=started,
                    stopped_observer=stopped,
                    opened_at=opened_at,
                    closed_at=closed_at,
                )


def write_report(result: SessionResult) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = REPORT_DIR / f"session-{stamp}.json"
    shadow: Dict[str, Any] = {}
    observer: Dict[str, Any] = {}
    try:
        shadow = api_json("/api/shadow")
        observer = api_json("/api/autonomous-trader/status")
    except RuntimeError as error:
        observer = {"status_error": str(error)}
    payload = {
        "generated_at": utc_now(),
        "result": result.__dict__,
        "shadow": shadow,
        "observer": observer,
        "real_orders_allowed": False,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def main() -> int:
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_FILE.open("w", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log("Supervisor already running; duplicate invocation ignored")
            return 0

        supervisor = MarketSessionSupervisor()
        try:
            result = supervisor.run()
        except Exception as error:
            log("Supervisor failed closed", error=str(error))
            try:
                api_json("/api/autonomous-trader/stop", "POST")
            except RuntimeError:
                pass
            result = SessionResult("ERROR", str(error), closed_at=utc_now())

        report = write_report(result)
        log("Session supervisor finished", report=str(report), **result.__dict__)
        return 0 if result.outcome in {"COMPLETED", "SKIPPED"} else 1


if __name__ == "__main__":
    sys.exit(main())
