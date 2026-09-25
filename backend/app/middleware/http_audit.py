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
    # CR202 removed the /link_apikey route entirely — the device now holds the
    # key and never sends it here. The entry stays: a stale scrub entry costs
    # nothing, and re-adding a route is far easier to remember than re-adding
    # its scrub entry, which is how DEF181 happened in the first place.
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

# CR202: not a secret — personal financial data. The device now sends its own
# Alpaca paper positions with each Room convene / 1-on-1 turn, and without this
# the whole holdings list would persist to http_audit.request_body for 90 days.
# Moving the *key* off this host while quietly logging the *positions* would be
# a partial defeat of the very change that moved it, so it is redacted here.
# Kept separate from _SECRET_FIELD_RE because the two are different claims:
# one says "this would be a credential leak", this says "we do not need this".
_PRIVATE_FIELD_RE = re.compile(r"^alpaca$", re.IGNORECASE)

# DEF430 MAJOR-1: the DEF419 mandate-preview snapshot
# (`toMandateSnapshotJson()` — `{kind, equity, cash, positions}`) rides
# `/v1/sim/preview` under the key `account`, not `alpaca`, so `_PRIVATE_FIELD_RE`
# above never touches it — it was persisted to http_audit.request_body verbatim
# for 90 days, which is exactly the outcome CR202's comment above says this
# module exists to prevent, and makes Privacy v2.1's "we do not store the
# summary as its own record" false for this one path. `account` is NOT added to
# `_PRIVATE_FIELD_RE` globally: that key name is generic (e.g. billing/auth
# payloads use it for unrelated things) and a blanket match would redact fields
# on routes that have nothing to do with Alpaca. Scoped by path instead — one
# entry per route whose body carries the Alpaca snapshot under a different key
# than `alpaca`. `/v1/sim/preview` is the only such route today (grepped
# `mobile/lib/services/api/api_client.dart` for every `toMandateSnapshotJson`/
# `toWireJson` call site: Room convene and 1-on-1 both use the `alpaca` key,
# already covered; order submit/cancel never send the snapshot at all).
_PATH_SCOPED_PRIVATE_FIELDS: dict[str, re.Pattern[str]] = {
    "/v1/sim/preview": re.compile(r"^account$", re.IGNORECASE),
}

# DEF430 round 2 MAJOR-A: the request-side fix above (`_PATH_SCOPED_PRIVATE_FIELDS`)
# only redacts the `account` key ON THE REQUEST. `preview_trade`'s RESPONSE also
# echoes part of that same Alpaca paper snapshot back — `cash_available` (the
# account's own cash) and `held_quantity` (a held position's own size), plus the
# same numbers folded into free-text `violations` strings (e.g. "insufficient
# cash: need $X, have $50000.00"; a concentration % next to the notional, from
# which equity is recoverable). Per-key redaction can't reach the violation
# strings, so — same posture as `SCRUB_PATHS` — the WHOLE response body is
# replaced with `[REDACTED]` instead, but only when the matching request
# actually carried the scoped key (i.e. only for a snapshot-path preview; a
# preview with no `account` is AMI's own sim and keeps its normal response).
# Keyed by path -> the request-body key whose presence triggers the response
# blackout; deliberately the SAME key as `_PATH_SCOPED_PRIVATE_FIELDS` above
# (today), but a distinct table because the two are different questions: "is
# this key sensitive" vs "does this response need to go dark".
_PATH_SCOPED_RESPONSE_SCRUB_ON_REQUEST_FIELD: dict[str, str] = {
    "/v1/sim/preview": "account",
}


def _normalize_scrub_path(path: str) -> str:
    """`_PATH_SCOPED_PRIVATE_FIELDS` / `_PATH_SCOPED_RESPONSE_SCRUB_ON_REQUEST_FIELD`
    are keyed by exact path. A trailing-slash variant of a scoped route (e.g. a
    proxy or future client build POSTing `/v1/sim/preview/`) 307-redirects at the
    route layer, but THIS middleware sees the pre-redirect path — an exact dict
    lookup would miss it and store the unredacted body. Strip exactly one
    trailing slash (never the bare root `/`) before every scoped lookup."""
    if len(path) > 1 and path.endswith("/"):
        return path.rstrip("/")
    return path


def _request_json_has_key(body: bytes, key: str) -> bool:
    try:
        parsed = json.loads(body)
    except Exception:
        return False
    return isinstance(parsed, dict) and key in parsed


def _scrub_secret_fields(body: bytes, path: str | None = None) -> bytes:
    """Redact values of secret-shaped and privacy-sensitive JSON keys,
    recursively. Returns the input unchanged if it isn't parseable JSON (e.g.
    already scrubbed, binary, or malformed) — never raises.

    `path` additionally applies `_PATH_SCOPED_PRIVATE_FIELDS`, so a key name
    that only carries Alpaca data on ONE route (e.g. `account` on the DEF419
    preview) doesn't get swept on every other route that happens to use the
    same generic key name for something unrelated."""
    try:
        parsed = json.loads(body)
    except Exception:
        return body

    scoped_re = (
        _PATH_SCOPED_PRIVATE_FIELDS.get(_normalize_scrub_path(path)) if path else None
    )

    def _walk(node):
        if isinstance(node, dict):
            out = {}
            for k, v in node.items():
                if isinstance(k, str) and (
                    _SECRET_FIELD_RE.search(k)
                    or _PRIVATE_FIELD_RE.search(k)
                    or (scoped_re is not None and scoped_re.search(k))
                ):
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
        normalized_path = _normalize_scrub_path(path)
        scrub = path in SCRUB_PATHS or normalized_path in SCRUB_PATHS
        content_type = request.headers.get("content-type", "")
        # DEF184: multipart bodies (file uploads) are never buffered here —
        # the handler streams them with its own cap. Reading them into RAM
        # in this middleware first would defeat that cap.
        is_multipart = content_type.lower().startswith("multipart/form-data")

        # DEF430 round 2 MAJOR-A: does this route's response need to go dark
        # if-and-only-if the request itself carried the scoped field (e.g. a
        # snapshot preview vs. AMI's own sim, both on `/v1/sim/preview`)?
        # Computed from the RAW request bytes, before request-side scrubbing
        # below, since scrubbing replaces the key's value but not its presence.
        response_scrub_field = _PATH_SCOPED_RESPONSE_SCRUB_ON_REQUEST_FIELD.get(
            normalized_path
        )
        scrub_response_for_request_field = False

        if scrub:
            captured_request = b"[REDACTED]"
        elif is_multipart:
            captured_request = b"[NOT_CAPTURED:multipart]"
        else:
            try:
                body_bytes = await request.body()
            except Exception:
                body_bytes = b""
            if response_scrub_field is not None:
                scrub_response_for_request_field = _request_json_has_key(
                    body_bytes, response_scrub_field
                )
            body_bytes = _scrub_secret_fields(body_bytes, path)
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

        if scrub or scrub_response_for_request_field:
            captured_response = b"[REDACTED]"
        elif not is_streaming:
            # Consume the underlying body iterator, buffer it, return a fresh
            # Response with the same bytes. Starlette's Response.body_iterator
            # is the canonical hook.
            body_chunks: list[bytes] = []
            async for chunk in response.body_iterator:  # type: ignore[attr-defined]
                body_chunks.append(chunk)
            full = b"".join(body_chunks)
            scrubbed = _scrub_secret_fields(full, path)
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
