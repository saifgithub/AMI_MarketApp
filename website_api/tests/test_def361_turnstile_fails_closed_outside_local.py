"""DEF361 — an unset Turnstile secret must not silently pass every caller.

`verify_turnstile` returned True whenever TURNSTILE_SECRET was unset, with no
log line at all, justified by a docstring that said "in prod the secret is
present". That was an assumption about deployment, not a control, and it was
measured false: on 2026-08-22 melehost's `ami_website_api` had been running
`ENV: prod` for two weeks with the secret unset. The container is loopback-only
today, which is the sole reason it did not matter — the moment Cloudflare
routes to it, all three public POSTs (contact, data-request and the
vLLM-backed concierge) accept anything as human-verified, silently.

CLAUDE.md's rule is explicit: a feature gated on config presence must fail
VISIBLY, never silently fall back. The bypass is therefore scoped to
`env == "local"` and logs on every use; anywhere else a missing secret fails
CLOSED — the shape DEF182 gave ALPACA_ENCRYPTION_KEY.
"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.services.turnstile import verify_turnstile


@pytest.mark.asyncio
async def test_local_still_works_without_a_secret(monkeypatch):
    """A dev box with no dashboard config must stay usable."""
    monkeypatch.setattr(settings, "turnstile_secret", "")
    monkeypatch.setattr(settings, "env", "local")
    assert await verify_turnstile(None) is True


@pytest.mark.parametrize("env", ["prod", "staging", "alpha", ""])
@pytest.mark.asyncio
async def test_every_non_local_env_fails_closed(monkeypatch, env):
    """The melehost case: ENV=prod, secret unset. Must refuse, not accept.

    Parametrised over the neighbours too, because the defect was a default
    that happened to be wrong for one value — pinning only "prod" would leave
    the same hole one env name away.
    """
    monkeypatch.setattr(settings, "turnstile_secret", "")
    monkeypatch.setattr(settings, "env", env)
    assert await verify_turnstile("any-token") is False


@pytest.mark.asyncio
async def test_a_configured_secret_still_reaches_siteverify(monkeypatch):
    """Non-vacuity: the new branch must not swallow the configured path.

    If this ever flipped, Turnstile would reject every real visitor — the
    opposite failure, and the one users would feel.
    """
    monkeypatch.setattr(settings, "turnstile_secret", "a-secret")
    monkeypatch.setattr(settings, "env", "prod")
    # No token at all is rejected before any network call.
    assert await verify_turnstile(None) is False

    called: dict = {}

    class _Resp:
        text = "{}"

        def json(self):
            return {"success": True}

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, data=None, timeout=None):
            called["url"] = url
            called["secret"] = data["secret"]
            return _Resp()

    import app.services.turnstile as ts

    monkeypatch.setattr(ts.httpx, "AsyncClient", lambda *a, **k: _Client())
    assert await verify_turnstile("a-token") is True
    assert "siteverify" in called["url"]
    assert called["secret"] == "a-secret"
