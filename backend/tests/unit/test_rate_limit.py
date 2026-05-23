"""Rate limiter — sliding-window counter behaviour + integration with FastAPI.

B-tier audit (AT:R37). Focused on the limiter's contract; the LLM-heavy
route integration is exercised via TestClient against /v1/auth/anon since
it's the cheapest of the three (no DB writes on a 429 path, no SSE).
"""

from __future__ import annotations

import time

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.services.rate_limit import RateLimiter, anon_rate_limit


def _make_app(limiter: RateLimiter) -> FastAPI:
    """Tiny app with one route guarded by the supplied limiter."""
    app = FastAPI()

    @app.get("/probe", dependencies=[Depends(limiter)])
    def probe() -> dict[str, str]:
        return {"ok": "yes"}

    return app


def test_allows_requests_under_limit():
    limiter = RateLimiter(name="t1", per_minute=3)
    client = TestClient(_make_app(limiter))
    for _ in range(3):
        r = client.get("/probe", headers={"cf-connecting-ip": "1.2.3.4"})
        assert r.status_code == 200


def test_blocks_when_over_limit():
    limiter = RateLimiter(name="t2", per_minute=3)
    client = TestClient(_make_app(limiter))
    for _ in range(3):
        client.get("/probe", headers={"cf-connecting-ip": "1.2.3.4"})
    r = client.get("/probe", headers={"cf-connecting-ip": "1.2.3.4"})
    assert r.status_code == 429
    assert r.json()["detail"].startswith("rate_limit_exceeded")
    assert "Retry-After" in r.headers
    assert int(r.headers["Retry-After"]) >= 1


def test_separate_ips_independently_counted():
    limiter = RateLimiter(name="t3", per_minute=2)
    client = TestClient(_make_app(limiter))
    # IP A burns its budget...
    for _ in range(2):
        assert client.get("/probe", headers={"cf-connecting-ip": "1.1.1.1"}).status_code == 200
    assert client.get("/probe", headers={"cf-connecting-ip": "1.1.1.1"}).status_code == 429
    # ... but IP B still has its full budget.
    for _ in range(2):
        assert client.get("/probe", headers={"cf-connecting-ip": "2.2.2.2"}).status_code == 200


def test_falls_back_to_xff_when_cf_header_absent():
    limiter = RateLimiter(name="t4", per_minute=2)
    client = TestClient(_make_app(limiter))
    # No cf-connecting-ip → use X-Forwarded-For first hop.
    for _ in range(2):
        r = client.get("/probe", headers={"x-forwarded-for": "9.9.9.9, 10.0.0.1"})
        assert r.status_code == 200
    r = client.get("/probe", headers={"x-forwarded-for": "9.9.9.9, 10.0.0.1"})
    assert r.status_code == 429


def test_window_release_lets_traffic_through_again(monkeypatch: pytest.MonkeyPatch):
    """After WINDOW_SECONDS, the oldest timestamp ages out and a fresh request
    is accepted. We fast-forward `time.time` rather than sleep 60s."""
    from app.services import rate_limit as rl_mod

    limiter = RateLimiter(name="t5", per_minute=1)
    client = TestClient(_make_app(limiter))
    t = [time.time()]
    monkeypatch.setattr(rl_mod.time, "time", lambda: t[0])
    assert client.get("/probe", headers={"cf-connecting-ip": "1.2.3.4"}).status_code == 200
    assert client.get("/probe", headers={"cf-connecting-ip": "1.2.3.4"}).status_code == 429
    # Advance past the window.
    t[0] += rl_mod.WINDOW_SECONDS + 1
    assert client.get("/probe", headers={"cf-connecting-ip": "1.2.3.4"}).status_code == 200


def test_reset_clears_all_counters():
    limiter = RateLimiter(name="t6", per_minute=1)
    client = TestClient(_make_app(limiter))
    client.get("/probe", headers={"cf-connecting-ip": "1.2.3.4"})
    assert client.get("/probe", headers={"cf-connecting-ip": "1.2.3.4"}).status_code == 429
    limiter.reset()
    assert client.get("/probe", headers={"cf-connecting-ip": "1.2.3.4"}).status_code == 200


def test_auth_anon_route_is_actually_wired(monkeypatch: pytest.MonkeyPatch):
    """End-to-end smoke against the real /v1/auth/anon route — confirms the
    `dependencies=[Depends(anon_rate_limit)]` wire-up actually fires."""
    from fastapi.testclient import TestClient

    from app.main import app

    anon_rate_limit.reset()
    client = TestClient(app)
    headers = {"cf-connecting-ip": "5.5.5.5"}
    body = {}
    # Burn the budget (per_minute=10 for anon).
    for _ in range(10):
        r = client.post("/v1/auth/anon", headers=headers, json=body)
        assert r.status_code == 200, r.text
    # 11th should 429.
    r = client.post("/v1/auth/anon", headers=headers, json=body)
    assert r.status_code == 429
    anon_rate_limit.reset()
