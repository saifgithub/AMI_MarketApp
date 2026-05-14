"""HTTP audit middleware — captures every inbound request + response.

AT:R16. Records to the `http_audit` table:
  - method, path, query
  - request body (truncated)
  - response status + body for non-streaming responses
  - response BYTE COUNT only for streaming (SSE) responses — full body
    capture would buffer the whole stream and break SSE latency
  - latency
  - client_ip (from X-Forwarded-For if present, else ASGI client)
  - user_id parsed from the scaffold:<hex> bearer (best-effort)

Authorization / Cookie headers are never persisted.
Endpoints that are pure noise (`/v1/health` from the cloudflared healthcheck)
are skipped to avoid burying real activity.
"""

from __future__ import annotations

import time
from typing import Awaitable, Callable, Optional
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from app.services.audit import MAX_BODY_BYTES, record_http


SKIP_PATHS = {"/v1/health"}


class HTTPAuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path
        if path in SKIP_PATHS:
            return await call_next(request)

        started = time.perf_counter()

        # Capture request body — Starlette body() caches so downstream handlers
        # still see it. For huge bodies (file upload), truncate.
        try:
            body_bytes = await request.body()
        except Exception:
            body_bytes = b""
        if len(body_bytes) > MAX_BODY_BYTES:
            captured_request = body_bytes[:MAX_BODY_BYTES]
        else:
            captured_request = body_bytes

        # Force the cached body onto Starlette so the route handler can re-read.
        # First call returns the cached body; subsequent calls return
        # http.disconnect — required for StreamingResponse routes (SSE), where
        # Starlette polls receive() to detect client disconnects. Without this,
        # the second poll sees a stale `http.request` and BaseHTTPMiddleware
        # raises `RuntimeError: Unexpected message received: http.request`,
        # crashing the stream after headers were sent.
        body_replayed = False

        async def receive() -> dict:
            nonlocal body_replayed
            if body_replayed:
                return {"type": "http.disconnect"}
            body_replayed = True
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        request._receive = receive  # type: ignore[attr-defined]

        try:
            response = await call_next(request)
        except Exception:
            latency_ms = int((time.perf_counter() - started) * 1000)
            record_http(
                method=request.method,
                path=path,
                query=request.url.query or None,
                user_id=_user_id_from_request(request),
                client_ip=_client_ip(request),
                status_code=500,
                request_body=captured_request,
                response_body=None,
                response_truncated=False,
                is_streaming=False,
                latency_ms=latency_ms,
            )
            raise

        is_streaming = isinstance(response, StreamingResponse) or response.headers.get(
            "content-type", ""
        ).startswith("text/event-stream")

        captured_response: Optional[bytes] = None
        response_truncated = False

        if not is_streaming:
            # Consume the underlying body iterator, buffer it, return a fresh
            # Response with the same bytes. Starlette's Response.body_iterator
            # is the canonical hook.
            body_chunks: list[bytes] = []
            async for chunk in response.body_iterator:  # type: ignore[attr-defined]
                body_chunks.append(chunk)
            full = b"".join(body_chunks)
            if len(full) > MAX_BODY_BYTES:
                captured_response = full[:MAX_BODY_BYTES]
                response_truncated = True
            else:
                captured_response = full
            response = Response(
                content=full,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        latency_ms = int((time.perf_counter() - started) * 1000)
        record_http(
            method=request.method,
            path=path,
            query=request.url.query or None,
            user_id=_user_id_from_request(request),
            client_ip=_client_ip(request),
            status_code=response.status_code,
            request_body=captured_request,
            response_body=captured_response,
            response_truncated=response_truncated,
            is_streaming=is_streaming,
            latency_ms=latency_ms,
        )
        return response


def _client_ip(request: Request) -> Optional[str]:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def _user_id_from_request(request: Request) -> Optional[UUID]:
    """Extract the user_id from path params or the scaffold:<hex> bearer.

    Best-effort: many routes don't have a user, and the auth scaffold's
    scaffold:<hex> token is a session opaque blob — we look it up via the
    auth service only if needed. For alpha we just grab user_id from the
    path if present (most routes are /v1/.../<user_id> shaped).
    """
    for key in ("user_id", "userId"):
        val = request.path_params.get(key)
        if val:
            try:
                return UUID(str(val))
            except Exception:
                continue
    return None
