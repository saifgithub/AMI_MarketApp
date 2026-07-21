"""Cloudflare Turnstile verification — server-side bot protection.

The static site renders a Turnstile widget; every public POST forwards the
resulting token here for siteverify. This closes the biggest pre-launch gap:
the website had no bot protection at all.

Degrade-loudly-but-usable: when TURNSTILE_SECRET is unset (local/dev) verification
is bypassed so the flow works without dashboard config. In prod the secret is
present and a missing/invalid token is rejected.
"""

from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.logging import logger

_SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_turnstile(token: str | None, *, remote_ip: str | None = None) -> bool:
    """Return True if the token is valid (or verification is bypassed in dev)."""
    if not settings.turnstile_secret:
        return True  # local/dev bypass — no secret provisioned

    if not token:
        return False

    data = {"secret": settings.turnstile_secret, "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip
    try:
        resp = httpx.post(_SITEVERIFY_URL, data=data, timeout=10.0)
        ok = bool(resp.json().get("success"))
        if not ok:
            logger.warning("turnstile_failed", body=resp.text[:200])
        return ok
    except Exception as exc:
        # Fail closed on a hard verification error in prod.
        logger.warning("turnstile_error", error=str(exc))
        return False
