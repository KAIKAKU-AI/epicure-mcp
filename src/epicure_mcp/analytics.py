"""Privacy-minimised per-tool operational telemetry.

One structured JSON record is emitted for each ``tools/call`` invocation.
Records contain timing, response size, success state, tool name, and a daily
unlinkable client hash. Tool arguments, ingredient queries, result content,
Claude prompts, chat history, and uploaded files are never logged.

The hash uses a process-local random salt that rotates at UTC midnight. It is
useful for same-day abuse detection but cannot track a requester across days.
"""

from __future__ import annotations

import asyncio
import contextvars
import datetime
import functools
import hashlib
import json
import logging
import secrets
import threading
import time
from collections.abc import Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

log = logging.getLogger("epicure_mcp.analytics")

_current_ip: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "epicure_mcp_current_ip", default=None
)

_salt_lock = threading.Lock()
_salt: str = secrets.token_hex(16)
_salt_date: str = datetime.datetime.now(datetime.UTC).date().isoformat()


def _request_ip(request: Request) -> str:
    cloudflare_ip = request.headers.get("cf-connecting-ip")
    if cloudflare_ip:
        return cloudflare_ip.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class ClientContextMiddleware(BaseHTTPMiddleware):
    """Expose a request IP only long enough to create a daily hash."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        token = _current_ip.set(_request_ip(request))
        try:
            return await call_next(request)
        finally:
            _current_ip.reset(token)


def _today_utc_iso() -> str:
    return datetime.datetime.now(datetime.UTC).date().isoformat()


def _current_salt() -> str:
    """Return today's salt, rotating lazily at UTC midnight."""
    global _salt, _salt_date
    today = _today_utc_iso()
    with _salt_lock:
        if today != _salt_date:
            _salt = secrets.token_hex(16)
            _salt_date = today
        return _salt


def _hashed_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    return hashlib.sha256(f"{_current_salt()}:{ip}".encode()).hexdigest()[:16]


def _result_size_bytes(result: Any) -> int:
    if result is None:
        return 0
    if isinstance(result, str):
        return len(result.encode("utf-8"))
    try:
        body = json.dumps(result, default=str, separators=(",", ":"))
    except Exception:
        body = repr(result)
    return len(body.encode("utf-8"))


def _emit(record: dict[str, Any]) -> None:
    try:
        log.info(json.dumps(record, default=str, separators=(",", ":")))
    except Exception:  # pragma: no cover - telemetry must never break a tool
        pass


def _emit_record(
    tool_name: str,
    result: Any,
    started: float,
    ok: bool,
    error_type: str | None,
) -> None:
    _emit(
        {
            "ts": datetime.datetime.now(datetime.UTC).isoformat(timespec="milliseconds"),
            "ip_hash": _hashed_ip(_current_ip.get()),
            "tool": tool_name,
            "result_size_bytes": _result_size_bytes(result) if ok else 0,
            "latency_ms": round((time.perf_counter() - started) * 1000.0, 2),
            "ok": ok,
            "error_type": error_type,
        }
    )


def log_call(tool_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Emit minimal telemetry while preserving FastMCP's function signature."""

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        is_async = asyncio.iscoroutinefunction(fn)

        if is_async:

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                started = time.perf_counter()
                result: Any = None
                succeeded = False
                try:
                    result = await fn(*args, **kwargs)
                    succeeded = True
                    return result
                except Exception as exc:
                    _emit_record(tool_name, None, started, False, type(exc).__name__)
                    raise
                finally:
                    if succeeded:
                        _emit_record(tool_name, result, started, True, None)

            return async_wrapper

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            started = time.perf_counter()
            result: Any = None
            succeeded = False
            try:
                result = fn(*args, **kwargs)
                succeeded = True
                return result
            except Exception as exc:
                _emit_record(tool_name, None, started, False, type(exc).__name__)
                raise
            finally:
                if succeeded:
                    _emit_record(tool_name, result, started, True, None)

        return sync_wrapper

    return decorator


def _force_salt_for_testing(salt: str, date_iso: str) -> None:
    """Override the rotating salt. Tests only."""
    global _salt, _salt_date
    with _salt_lock:
        _salt = salt
        _salt_date = date_iso


def _set_current_ip_for_testing(ip: str | None) -> contextvars.Token:
    """Set the IP context without an HTTP request. Tests only."""
    return _current_ip.set(ip)


def _reset_current_ip_for_testing(token: contextvars.Token) -> None:
    _current_ip.reset(token)
