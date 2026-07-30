"""DEF183 (security review N2) — blocking JWKS fetch on the event loop.

`oidc_verifier.py` does a synchronous `httpx.Client` JWKS fetch. Called
directly (not threadpooled) from the `async def` /v1/auth/apple and
/v1/auth/google handlers, a slow/unknown-kid token stalls the whole
single-worker event loop for the duration of the fetch — every other
in-flight request (including /v1/health) freezes too.

Fix: the route layer now runs `AuthService.sign_in_with_apple/google`
via `starlette.concurrency.run_in_threadpool`, so a slow verifier no
longer blocks the loop. This test proves concurrency, not just absence
of a crash: while one request is stuck in a slow (fake) verifier, a
concurrent request to an unrelated fast endpoint must not be starved.
"""

from __future__ import annotations

import asyncio
import time

import httpx
import pytest
from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.services.auth_service import AuthService


class _SlowVerifier:
    """Simulates the blocking JWKS fetch stalling for `delay` seconds."""

    def __init__(self, delay: float) -> None:
        self.delay = delay

    def verify(self, identity_token: str) -> dict:
        time.sleep(self.delay)
        return {"sub": "slow-sub"}


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(auth_router)

    @a.get("/v1/ping")
    async def ping() -> dict[str, bool]:
        return {"ok": True}

    return a


@pytest.mark.asyncio
async def test_slow_oidc_verify_does_not_stall_concurrent_requests(app: FastAPI, monkeypatch):
    import app.services.auth_service as svc
    from app.services.auth_service import get_auth_service

    svc._service = None
    slow = AuthService(apple_verifier=_SlowVerifier(delay=1.5))
    svc._service = slow
    monkeypatch.setattr("app.api.auth.get_auth_service", lambda: slow)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Bootstrap an anon user for the Bearer.
        anon = await client.post("/v1/auth/anon", json={})
        token = anon.json()["token"]

        async def slow_apple_call():
            t0 = time.monotonic()
            r = await client.post(
                "/v1/auth/apple",
                json={"identity_token": "header.body.sig"},
                headers={"Authorization": f"Bearer {token}"},
            )
            return r, time.monotonic() - t0

        async def fast_ping():
            # Give the apple call a head start into its "slow verify".
            await asyncio.sleep(0.2)
            t0 = time.monotonic()
            r = await client.get("/v1/ping")
            return r, time.monotonic() - t0

        (apple_resp, apple_elapsed), (ping_resp, ping_elapsed) = await asyncio.gather(
            slow_apple_call(), fast_ping(),
        )

    assert apple_resp.status_code == 200
    assert ping_resp.status_code == 200
    # The whole point: /v1/ping must return fast even though a concurrent
    # request is stuck in a 1.5s "JWKS fetch". Pre-fix (no threadpool),
    # ping would be blocked behind the sync call on the single event loop
    # and take close to the full 1.5s too.
    assert ping_elapsed < 0.5, (
        f"ping took {ping_elapsed:.2f}s — the slow OIDC verify blocked the loop"
    )
