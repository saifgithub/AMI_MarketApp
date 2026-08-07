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

import json
import re
import time
from typing import Awaitable, Callable, Optional
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse

from app.services.audit import MAX_BODY_BYTES, record_http
from app.services.auth_service import parse_scaffold_token_user_id


SKIP_PATHS = {"/v1/health"}

# DEF184 (security review N3): this middleware used to call
# `await request.body()` unconditionally for every non-skipped route,
# buffering the ENTIRE body into RAM *before* any handler-level cap (e.g.
# the 5 MB streaming upload cap in bug_attachments.py) ever got a chance
# to run — a single multi-GB POST to any route OOM-kills the whole
# process (Postgres + API), with no compose `mem_limit` to backstop it.
# Two mitigations here, both applied before any bytes are read:
#   1. A declared Content-Length above this hard ceiling is rejected with
#      413 before `request.body()` is ever called.
#   2. multipart/form-data bodies (file uploads) are never captured at
#      the middleware level at all — that's exactly the path with its
#      own purpose-built streaming cap; buffering it here would defeat
#      that cap even when Content-Length is absent/understated.
# 10 MB is comfortably above the 5 MB attachment cap (room for form
# fields alongside the file) and far below "OOM the box."
MAX_REQUEST_BODY_BYTES = 10 * 1024 * 1024

# Auth routes that issue or accept credentials (bearer tokens, magic-link
# codes, Apple JWTs). Bodies are replaced with [REDACTED] before being
# written to http_audit rows — the token stays out of the audit log.
# Method / path / status / latency / IP are still recorded.
# Adversarial audit (2026-05-18) finding B4.
SCRUB_PATHS = {
    "/v1/auth/anon",
    "/v1/auth/magic_link/start",
    "/v1/auth/magic_link/verify",
    "/v1/auth/apple",
    "/v1/auth/google",
    "/v1/auth/session",
    # DEF181 (security review H4): both were persisted CLEARTEXT to
    # http_audit.request_body for 90 days — bypassing the DEF044
    # encryption-at-rest control on Alpaca broker credentials.
    "/v1/alpaca/link",
    "/v1/alpaca/link_apikey",
}

# DEF181: SCRUB_PATHS is a hand-maintained list — every past leak (this
# one included) was a route someone forgot to add to it. Structural
# backstop: ANY JSON body, on ANY route, has values redacted wherever the
# KEY looks secret-shaped, whether or not the route is in SCRUB_PATHS.
# Path-level scrubbing above still wins for routes carrying a whole
# credential blob under a non-obvious key name; this catches the rest.
_SECRET_FIELD_RE = re.compile(
    r"(secret|token|api[_-]?key|password|credential)",
    re.IGNORECASE,
)


def _scrub_secret_fields(body: bytes) -> bytes:
    """Redact values of secret-shaped JSON keys, recursively. Returns the
    input unchanged if it isn't parseable JSON (e.g. already scrubbed,
    binary, or malformed) — never raises."""
    try:
        parsed = json.loads(body)
    except Exception:
        return body

    def _walk(node):
        if isinstance(node, dict):
            out = {}
            for k, v in node.items():
                if isinstance(k, str) and _SECRET_FIELD_RE.search(k):
                    out[k] = "[REDACTED]"
                else:
                    out[k] = _walk(v)
            return out
        if isinstance(node, list):
            return [_walk(v) for v in node]
        return node

    try:
        return json.dumps(_walk(parsed)).encode("utf-8")
    except Exception:
        return body


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

        # DEF184: reject an oversized declared body BEFORE any buffering.
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared_len = int(content_length)
            except ValueError:
                declared_len = None
            if declared_len is not None and declared_len > MAX_REQUEST_BODY_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "request body too large"},
                )

        # Capture request body — Starlette body() caches so downstream handlers
        # still see it. For huge bodies (file upload), truncate.
        scrub = path in SCRUB_PATHS
        content_type = request.headers.get("content-type", "")
        # DEF184: multipart bodies (file uploads) are never buffered here —
        # the handler streams them with its own cap. Reading them into RAM
        # in this middleware first would defeat that cap.
        is_multipart = content_type.lower().startswith("multipart/form-data")

        if scrub:
            captured_request = b"[REDACTED]"
        elif is_multipart:
            captured_request = b"[NOT_CAPTURED:multipart]"
        else:
            try:
                body_bytes = await request.body()
            except Exception:
                body_bytes = b""
            body_bytes = _scrub_secret_fields(body_bytes)
            if len(body_bytes) > MAX_BODY_BYTES:
                captured_request = body_bytes[:MAX_BODY_BYTES]
            else:
                captured_request = body_bytes

        # NOTE: we deliberately do NOT replace request._receive.
        #
        # Starlette caches request.body() in request._body, so the downstream
        # handler can re-read the body without ever calling receive() again.
        # _CachedRequest.wrapped_receive checks for _body first and returns
        # the cached bytes directly. So nothing more is needed here.
        #
        # Earlier versions of this middleware replaced request._receive with a
        # synthetic that always returned http.request. That broke SSE routes
        # (1-on-1 chat, room stream, coach chat): once Starlette had wrapped
        # the response and the streaming body started, _CachedRequest polled
        # receive() to detect client disconnect, got our http.request back,
        # and raised `RuntimeError: Unexpected message received: http.request`.
        # The stream died after status 200 was already sent — the iPhone saw
        # an empty response.

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

        if scrub:
            captured_response = b"[REDACTED]"
        elif not is_streaming:
            # Consume the underlying body iterator, buffer it, return a fresh
            # Response with the same bytes. Starlette's Response.body_iterator
            # is the canonical hook.
            body_chunks: list[bytes] = []
            async for chunk in response.body_iterator:  # type: ignore[attr-defined]
                body_chunks.append(chunk)
            full = b"".join(body_chunks)
            scrubbed = _scrub_secret_fields(full)
            if len(scrubbed) > MAX_BODY_BYTES:
                captured_response = scrubbed[:MAX_BODY_BYTES]
                response_truncated = True
            else:
                captured_response = scrubbed
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
    """Extract the user_id that performed this request, for attribution.

    DEF181 (security review H4 + N5): this used to ONLY check path params
    despite its docstring claiming to also parse the bearer — it never
    did, so the audit record had `user_id = NULL` for nearly every
    authenticated action (most routes derive the caller from the Bearer
    token, not a path segment), leaving the post-breach forensic trail
    blind. Bearer now takes priority — it identifies the ACTUAL caller;
    a `user_id`-shaped path param can name someone ELSE entirely (e.g.
    `/v1/auth/merge/preview/{from_user_id}` — that's the orphan being
    inspected, not the caller). Path param is only a fallback for the
    rare unauthenticated-but-path-scoped route.
    """
    authorization = request.headers.get("authorization")
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
        try:
            user_id = parse_scaffold_token_user_id(token)
        except Exception:
            user_id = None
        if user_id is not None:
            return user_id
    for key in ("user_id", "userId"):
        val = request.path_params.get(key)
        if val:
            try:
                return UUID(str(val))
            except Exception:
                continue
    return None
