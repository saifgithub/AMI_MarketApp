"""In-memory sliding-window rate limiter — ported from the app backend.

The website API runs as a single FastAPI process behind the same Cloudflare
Tunnel, so a per-process deque-of-timestamps keyed by (route, IP) brackets
abuse well enough at launch scale. Ported (not imported) to keep the website
stack free of any `backend/` dependency.

Keying: Cloudflare `cf-connecting-ip` → `x-forwarded-for` first hop →
`request.client.host`. Threshold breach → HTTP 429 with `Retry-After`.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import RLock

from fastapi import HTTPException, Request, status

from app.core.logging import logger

WINDOW_SECONDS = 60


class RateLimiter:
    """Per-(route, ip) sliding-window counter. One instance covers one route."""

    def __init__(self, *, name: str, per_minute: int) -> None:
        self.name = name
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = RLock()

    def reset(self) -> None:
        """Drop every counter — for tests."""
        with self._lock:
            self._hits.clear()

    def _resolve_key(self, request: Request) -> str:
        cf_ip = request.headers.get("cf-connecting-ip")
        if cf_ip:
            return f"ip:{cf_ip.strip()}"
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return f"ip:{xff.split(',', 1)[0].strip()}"
        if request.client and request.client.host:
            return f"ip:{request.client.host}"
        return "ip:unknown"

    async def __call__(self, request: Request) -> None:
        key = self._resolve_key(request)
        now = time.time()
        cutoff = now - WINDOW_SECONDS
        with self._lock:
            window = self._hits[key]
            while window and window[0] < cutoff:
                window.popleft()
            if len(window) >= self.per_minute:
                oldest = window[0]
                retry_after = max(1, int((oldest + WINDOW_SECONDS) - now) + 1)
                logger.warning(
                    "rate_limit_hit",
                    limiter=self.name,
                    key=key,
                    per_minute=self.per_minute,
                    in_window=len(window),
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"rate_limit_exceeded: {self.name}",
                    headers={"Retry-After": str(retry_after)},
                )
            window.append(now)


# ── Module-level limiters (one per public route) ────────────────────────────

# Concierge chat — LLM-backed but read-only FAQ. 5/min per IP.
concierge_rate_limit = RateLimiter(name="concierge", per_minute=5)

# Contact form — triggers an email send + LLM call. Tight.
contact_rate_limit = RateLimiter(name="contact", per_minute=3)

# Data-request form — legal intake, triggers an email. Tight.
data_request_rate_limit = RateLimiter(name="data_request", per_minute=3)

# DEF372 (security review M7) — the waitlist had NO limiter at all while every
# neighbouring form had one. It writes a row per call, so unlimited is an
# unbounded write amplifier and a free way to fill the table with addresses
# nobody consented for. Looser than contact/data_request (3/min) because a
# person legitimately retrying a typo'd address should not be told to wait,
# and this one sends no email.
waitlist_rate_limit = RateLimiter(name="waitlist", per_minute=10)
