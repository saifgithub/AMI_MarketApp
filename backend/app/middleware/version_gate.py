"""CR121 — server-side enforcement of the client version floor.

Sits beside `HTTPAuditMiddleware` / `CORSMiddleware` in main.py. Every
client request carries an `X-App-Version` header (added at the single
existing choke point, `api_client.dart`'s `_AuthInterceptor.onRequest`); a
request below the active floor gets `426 Upgrade Required` with the same
shape `GET /v1/client/release-floor` returns, so a client that skips its own
startup/resume check (or a patched binary that never makes that call at
all) still can't transact against a build the server has condemned.

Client-side checking is the load-bearing mechanism (it's what shows the
user a screen and a way out); this is belt-and-braces on top of it — cheap,
because the header already exists, and it is what makes the gate real
against a bypass rather than merely a polite ask.

Exempt paths, so a blocked client can still: verify the server is even up
(`/v1/health`), find out WHY it's blocked (`/v1/client/release-floor`
itself — an already-blocked client must still be able to re-check after the
user updates), and report that it's stuck (`/v1/feedback/bug`).

This middleware is a defensive backstop, not the fail-open mechanism — the
CR's fail-open guarantee (an unreachable floor lookup must never brick the
app) lives client-side, where a lookup failure is real and common (a phone
going briefly offline). Here, a lookup failure only ever means "skip this
one extra server-side check for this one request" — it must never turn into
a 5xx on every request in the app.
"""

from __future__ import annotations

from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.logging import logger
from app.db import get_session
from app.services.client_release_floor import (
    get_active_floor,
    parse_build_number,
    resolve_action,
    resolve_body,
)

EXEMPT_PATHS = frozenset({
    "/v1/health",
    "/v1/client/release-floor",
    "/v1/feedback/bug",
})


class VersionGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        build = parse_build_number(request.headers.get("x-app-version"))
        if build is not None:
            try:
                with get_session() as session:
                    floor = get_active_floor(session)
                    if floor is not None and resolve_action(build, floor) == "block":
                        # This middleware sits OUTSIDE HTTPAuditMiddleware, so a
                        # 426 never reaches the audit log — without this line,
                        # raising the floor produces no signal anywhere about
                        # how many clients it just cut off (CR040). Logged at
                        # warning because a block is an operator-visible event,
                        # not routine traffic.
                        logger.warning(
                            "version_gate_blocked_request",
                            path=request.url.path,
                            client_build=build,
                            min_build=floor.min_build,
                        )
                        return JSONResponse(
                            status_code=426,
                            content={
                                "detail": {
                                    "min_build": floor.min_build,
                                    "recommended_build": floor.recommended_build,
                                    "action": "block",
                                    "headline": floor.headline,
                                    "body": resolve_body(floor, None),
                                    "store_url": None,
                                },
                            },
                        )
            except Exception:
                logger.exception("version_gate_middleware_check_failed")

        return await call_next(request)
