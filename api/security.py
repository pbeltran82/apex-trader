from __future__ import annotations

import hmac
import os
from typing import Any, Optional

from fastapi import Request
from fastapi.responses import JSONResponse


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
TOKEN_HEADER = "X-Kyle-Operator-Token"
PROTECTED_READ_PREFIXES = (
    "/api/backtest",
    "/api/intelligence/readiness",
)


def _operator_token() -> Optional[str]:
    value = os.getenv("KYLE_OPERATOR_TOKEN", "").strip()
    return value or None


def _is_direct_local_request(request: Request) -> bool:
    forwarded_for = request.headers.get("x-forwarded-for")
    client_host = request.client.host if request.client else ""
    return not forwarded_for and client_host in {"127.0.0.1", "::1", "localhost"}


def _requires_operator_auth(request: Request) -> bool:
    path = request.url.path
    if not path.startswith("/api/"):
        return False
    if any(path.startswith(prefix) for prefix in PROTECTED_READ_PREFIXES):
        return True
    return request.method.upper() not in SAFE_METHODS


def install_security(app_module: Any) -> None:
    if getattr(app_module, "_security_installed", False):
        return

    @app_module.app.middleware("http")
    async def operator_write_guard(request: Request, call_next):
        if not _requires_operator_auth(request):
            return await call_next(request)

        if _is_direct_local_request(request):
            return await call_next(request)

        expected = _operator_token()
        if expected is None:
            return JSONResponse(
                status_code=503,
                content={
                    "ok": False,
                    "error": "OPERATOR_TOKEN_NOT_CONFIGURED",
                    "message": "Remote control and protected diagnostics are disabled until KYLE_OPERATOR_TOKEN is configured.",
                },
            )

        supplied = request.headers.get(TOKEN_HEADER, "")
        if not supplied or not hmac.compare_digest(supplied, expected):
            return JSONResponse(
                status_code=401,
                content={
                    "ok": False,
                    "error": "INVALID_OPERATOR_TOKEN",
                    "message": "A valid Kyle operator token is required.",
                },
            )

        return await call_next(request)

    app_module._security_installed = True

    @app_module.app.get("/api/security/status")
    def security_status():
        return {
            "operator_token_configured": _operator_token() is not None,
            "remote_mutations_require_token": True,
            "protected_read_prefixes": list(PROTECTED_READ_PREFIXES),
            "direct_local_protected_access_allowed": True,
            "token_header": TOKEN_HEADER,
        }
