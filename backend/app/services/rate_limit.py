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
from collections import OrderedDict, deque
from threading import RLock

from fastapi import HTTPException, Request, status

from app.core.config import settings
from app.core.logging import logger


WINDOW_SECONDS = 60

# DEF184 (security review N4): the key space used to be an unbounded
# `defaultdict` — an attacker sending a unique spoofed `cf-connecting-ip`
# per request grows it forever (a second OOM path, on top of never
# evicting a legitimate IP's entry once idle). Bounded LRU: the oldest
# (least-recently-touched) key is evicted once the limiter is tracking
# more distinct keys than this, so total memory is O(MAX_TRACKED_KEYS)
# regardless of how many distinct keys/IPs are thrown at it.
MAX_TRACKED_KEYS = 50_000


class RateLimiter:
    """Per-(route, key) sliding-window counter.

    Each instance covers ONE route; the `name` parameter only affects log
    keys and HTTP 429 bodies, not the storage layout. Keyed by client IP
    by default; pass `key_fn` to key by something else (e.g. a
    request-body field) instead of/in addition to IP.
    """

    def __init__(
        self,
        *,
        name: str,
        per_minute: int,
        key_fn=None,
        window_seconds: int = WINDOW_SECONDS,
    ) -> None:
        self.name = name
        self.per_minute = per_minute
        self.window_seconds = window_seconds
        self._key_fn = key_fn or self.resolve_ip_key
        # key -> deque of unix-second timestamps within the window.
        # OrderedDict for O(1) "move to end" (touch) + "popitem(last=False)"
        # (evict oldest) — the LRU bound in MAX_TRACKED_KEYS.
        self._hits: "OrderedDict[str, deque[float]]" = OrderedDict()
        self._lock = RLock()

    def reset(self) -> None:
        """Drop every counter — for tests."""
        with self._lock:
            self._hits.clear()

    def resolve_ip_key(self, request: Request) -> str:
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

    def check(self, key: str) -> None:
        """Raise 429 if `key` is over budget; otherwise record a hit.

        Synchronous, framework-agnostic core — `__call__` (the FastAPI
        dependency shape) and any hand-rolled in-route check both funnel
        through this so the LRU-bounded storage has one code path.
        """
        now = time.time()
        cutoff = now - self.window_seconds
        with self._lock:
            window = self._hits.get(key)
            if window is None:
                window = deque()
                self._hits[key] = window
            else:
                self._hits.move_to_end(key)
            # Trim aged entries off the left.
            while window and window[0] < cutoff:
                window.popleft()
            if len(window) >= self.per_minute:
                # Compute Retry-After from the oldest hit still in the window.
                oldest = window[0]
                retry_after = max(1, int((oldest + self.window_seconds) - now) + 1)
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
            # Evict the least-recently-touched key(s) once over budget —
            # bounds total memory regardless of key cardinality (N4).
            while len(self._hits) > MAX_TRACKED_KEYS:
                self._hits.popitem(last=False)

    async def __call__(self, request: Request) -> None:
        key = self._key_fn(request)
        self.check(key)


class ConcurrencyLimiter:
    """Per-key concurrent-usage cap — how many operations for this key are
    open RIGHT NOW, distinct from [RateLimiter]'s "how many in the last N
    seconds". A key can be well under its rate limit while holding many
    streams open simultaneously; this bounds that separately.

    DEF201 (H6 follow-up): DEF186 rate-limited 1-on-1 + Brief turns to
    12/min/user but that bounds pace, not concurrency — nothing stopped
    one account holding many simultaneous SSE streams open at once, each
    burning a full LLM turn's worth of compute for the run's duration.

    `acquire()`/`release()` must be paired by the caller — always release
    from a `finally` (or equivalent exception-safe teardown), since a
    leaked acquire permanently steals one of that key's slots.
    """

    def __init__(self, *, name: str, max_concurrent: int) -> None:
        self.name = name
        self.max_concurrent = max_concurrent
        self._counts: dict[str, int] = {}
        self._lock = RLock()

    def reset(self) -> None:
        """Drop every counter — for tests."""
        with self._lock:
            self._counts.clear()

    def acquire(self, key: str) -> None:
        """Raise 429 if `key` is already at its cap; otherwise claim a slot."""
        with self._lock:
            current = self._counts.get(key, 0)
            if current >= self.max_concurrent:
                logger.warning(
                    "concurrency_limit_hit",
                    limiter=self.name,
                    key=key,
                    max_concurrent=self.max_concurrent,
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"concurrency_limit_exceeded: {self.name}",
                )
            self._counts[key] = current + 1

    def release(self, key: str) -> None:
        """Free a slot claimed by `acquire`.

        Never raises: a release for a key with no counted slot (double
        release, or release without a matching acquire — a bug elsewhere)
        is a no-op rather than a crash in stream teardown, which runs
        inside a `finally` where raising would mask the real exception.
        """
        with self._lock:
            current = self._counts.get(key)
            if not current:
                return
            if current <= 1:
                del self._counts[key]
            else:
                self._counts[key] = current - 1


# ── Module-level limiters (one per route — registered at import) ────────

# /v1/auth/anon — generous, since legit retries can fire on reconnect
# and the route mints users (cheap, in-process, no email send).
anon_rate_limit = RateLimiter(name="auth_anon", per_minute=10)

# /v1/auth/magic_link/start — expensive (sends an email; abuse vector for
# spamming arbitrary inboxes). Tight by IP.
magic_link_start_rate_limit = RateLimiter(
    name="auth_magic_link_start", per_minute=3,
)

# DEF180 (security review H5): /start had no per-target-email throttle —
# only per-IP — so a botnet (or any attacker cycling source IPs) could
# still hammer a single victim's inbox / mint unlimited fresh challenges
# for one email. Checked manually in the route (keyed by the body's
# email, lowercased) alongside the per-IP dependency above.
magic_link_start_email_rate_limit = RateLimiter(
    name="auth_magic_link_start_email", per_minute=3,
)

# DEF180: /verify had NO rate limiter at all — only /start was throttled.
# Two layers: per-IP (generous — legit users mistype) and per-target-email
# (tight — this is the actual guess-budget knob, since attempts reset
# with every /start; without this an attacker chains fresh /start calls
# to keep re-arming 5 guesses each, ~21,600 guesses/day/IP against one
# victim). A third "global" limiter bounds AGGREGATE verify volume across
# every IP/email pair, per lane acceptance #3 ("per identifier AND
# globally") — closes distributed guessing spread across many emails.
magic_link_verify_ip_rate_limit = RateLimiter(
    name="auth_magic_link_verify_ip", per_minute=10,
)
magic_link_verify_email_rate_limit = RateLimiter(
    name="auth_magic_link_verify_email", per_minute=5,
)
magic_link_verify_global_rate_limit = RateLimiter(
    name="auth_magic_link_verify_global", per_minute=120,
)

# /v1/room/stream — LLM-heavy (12 agents × ~1k tokens each per run on
# vLLM). 5/min per IP is comfortably above any legit pattern at alpha.
room_stream_rate_limit = RateLimiter(
    name="room_stream", per_minute=5,
)

# DEF186 (security review H6): 1-on-1 and Brief turns spent zero credits
# and had no rate limiter at all — one free anon token bought unlimited
# LLM turns. Per-user (bearer-keyed, not IP — an anon user can rotate
# devices/IPs trivially but the bearer identifies the same billed user)
# limiters, generous enough for real conversation pacing but bounding
# a scripted loop.
one_on_one_message_rate_limit = RateLimiter(
    name="one_on_one_message", per_minute=12,
)
brief_message_rate_limit = RateLimiter(
    name="brief_message", per_minute=12,
)

# DEF201 (H6 follow-up to DEF186): rate limiting bounds pace, not how many
# turns one account can have in flight at once. Shared across 1-on-1 +
# Brief — same LLM compute budget regardless of which surface it's spent
# through. Configurable via settings so alpha can retune the cap with an
# env change + container restart, no code change needed.
agent_stream_concurrency_limit = ConcurrencyLimiter(
    name="agent_stream_concurrency",
    max_concurrent=settings.agent_stream_max_concurrent_per_user,
)

# DEF186 / H9: unauthenticated bug-report uploads had no rate limit and no
# aggregate quota — looping 5 MB uploads fills the disk. IP-keyed, tight:
# 5/hour per the review's own suggested figure (not 5/min — an upload
# endpoint needs a longer window than a login-guess oracle).
bug_upload_rate_limit = RateLimiter(
    name="feedback_bug_upload", per_minute=5, window_seconds=3600,
)
