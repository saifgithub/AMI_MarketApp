"""Cloudflare Turnstile verification — server-side bot protection.

The static site renders a Turnstile widget; every public POST forwards the
resulting token here for siteverify. This closes the biggest pre-launch gap:
the website had no bot protection at all.

DEF361 — the bypass used to be unconditional and silent. `verify_turnstile`
returned True whenever TURNSTILE_SECRET was unset, with no log line, on the
strength of a comment that read "in prod the secret is present". That was an
assumption, not a control, and on 2026-08-22 it was measured false: melehost's
`ami_website_api` had been running `ENV: prod` for two weeks with the secret
unset, so every public POST — including the LLM-backed concierge — would have
been accepted as human-verified the moment Cloudflare routed traffic to it,
and nothing anywhere would have said so.

That is precisely the rule CLAUDE.md states: a feature gated on config presence
must fail VISIBLY, never silently fall back. So the bypass is now scoped to
`env == "local"` and says so on every request; outside local a missing secret
fails CLOSED, the same shape DEF182 gave ALPACA_ENCRYPTION_KEY. A dev machine
still works with no dashboard config; a deployed host cannot be quietly
unprotected.
"""

from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.logging import logger

_SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_turnstile(token: str | None, *, remote_ip: str | None = None) -> bool:
    """True if the token verifies, or if this is a local dev box (DEF361)."""
    if not settings.turnstile_secret:
        if settings.env == "local":
            logger.warning(
                "turnstile_bypassed_local",
                reason="TURNSTILE_SECRET unset and env=local",
            )
            return True
        logger.error(
            "turnstile_not_configured",
            env=settings.env,
            reason=(
                "TURNSTILE_SECRET is unset outside local — refusing the request "
                "rather than accepting it as human-verified"
            ),
        )
        return False

    if not token:
        return False

    data = {"secret": settings.turnstile_secret, "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(_SITEVERIFY_URL, data=data, timeout=10.0)
        ok = bool(resp.json().get("success"))
        if not ok:
            logger.warning("turnstile_failed", body=resp.text[:200])
        return ok
    except Exception as exc:
        # Fail closed on a hard verification error in prod.
        logger.warning("turnstile_error", error=str(exc))
        return False
