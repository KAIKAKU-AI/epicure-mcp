"""Optional bearer-token authentication for the public MCP transport."""

from __future__ import annotations

import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Require a configured bearer token on every non-public endpoint."""

    def __init__(
        self,
        app: ASGIApp,
        token: str | None,
        exempt_paths: tuple[str, ...] = ("/healthz", "/favicon.ico", "/favicon.png"),
    ) -> None:
        super().__init__(app)
        self.token = token
        self.exempt_paths = exempt_paths

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if not self.token or request.url.path in self.exempt_paths:
            return await call_next(request)

        authorization = request.headers.get("authorization", "")
        supplied = (
            authorization.removeprefix("Bearer ").strip()
            if authorization.startswith("Bearer ")
            else ""
        )
        if not supplied or not hmac.compare_digest(supplied, self.token):
            return JSONResponse(
                {"error": "authentication_required"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await call_next(request)
