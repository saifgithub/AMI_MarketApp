"""In-memory sliding-window rate limiter.

B-tier audit close (AT:R37). The alpha backend runs one FastAPI process
behind a Cloudflare Tunnel — no Redis cluster, no Lua scripts. A
per-process deque-of-timestamps keyed by (route, principal) is enough
to bracket abuse at this scale; when we shard to multiple replicas the
limiter moves to Redis but the public dep signature stays the same.

Usage:

    limiter = RateLimiter(name="auth_anon", per_minute=10)

    @router.post("/anon", dependencies=[Depends(limiter)])
    def anon_session(...): ...

Keying: Cloudflare `cf-connecting-ip` → `x-forwarded-for` first hop →
`request.client.host` fallback. CF Tunnel always populates the first;
the chain handles dev + tests where neither header is set.

Threshold breach raises HTTP 429 with a `Retry-After` header containing
the seconds until the oldest timestamp in the window expires.

The limiter is process-local so tests can swap or reset it via `reset()`.
Production process restart also resets — fine, because a stable abuser
gets re-throttled within seconds of the next request.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import RLock

from fastapi import HTTPException, Request, status

from app.core.logging import logger


WINDOW_SECONDS = 60


class RateLimiter:
    """Per-(route, ip) sliding-window counter.

    Each instance covers ONE route; the `name` parameter only affects log
    keys and HTTP 429 bodies, not the storage layout.
    """

    def __init__(
        self,
        *,
        name: str,
        per_minute: int,
    ) -> None:
        self.name = name
        self.per_minute = per_minute
        # key -> deque of unix-second timestamps within the window.
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = RLock()

    def reset(self) -> None:
        """Drop every counter — for tests."""
        with self._lock:
            self._hits.clear()

    def _resolve_key(self, request: Request) -> str:
        # Prefer Cloudflare's authenticated header, then the standard XFF
        # first-hop, then the socket peer (only useful in tests).
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
            # Trim aged entries off the left.
            while window and window[0] < cutoff:
                window.popleft()
            if len(window) >= self.per_minute:
                # Compute Retry-After from the oldest hit still in the window.
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


# ── Module-level limiters (one per route — registered at import) ────────

# /v1/auth/anon — generous, since legit retries can fire on reconnect
# and the route mints users (cheap, in-process, no email send).
anon_rate_limit = RateLimiter(name="auth_anon", per_minute=10)

# /v1/auth/magic_link/start — expensive (sends an email; abuse vector for
# spamming arbitrary inboxes). Tight by IP.
magic_link_start_rate_limit = RateLimiter(
    name="auth_magic_link_start", per_minute=3,
)

# /v1/room/stream — LLM-heavy (12 agents × ~1k tokens each per run on
# vLLM). 5/min per IP is comfortably above any legit pattern at alpha.
room_stream_rate_limit = RateLimiter(
    name="room_stream", per_minute=5,
)
