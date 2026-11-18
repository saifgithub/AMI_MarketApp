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


# DEF464: cf-connecting-ip is honoured only from a trusted proxy peer. These
# tests simulate "arrived through the cloudflared container" by giving the
# TestClient a socket peer inside settings.rate_limit_trusted_proxy_cidrs.
TRUSTED_PEER = ("172.19.0.5", 50000)
UNTRUSTED_PEER = ("192.168.20.77", 50000)


def _cf_client(limiter: RateLimiter, peer=TRUSTED_PEER) -> TestClient:
    return TestClient(_make_app(limiter), client=peer)


def test_allows_requests_under_limit():
    limiter = RateLimiter(name="t1", per_minute=3)
    client = _cf_client(limiter)
    for _ in range(3):
        r = client.get("/probe", headers={"cf-connecting-ip": "1.2.3.4"})
        assert r.status_code == 200


def test_blocks_when_over_limit():
    limiter = RateLimiter(name="t2", per_minute=3)
    client = _cf_client(limiter)
    for _ in range(3):
        client.get("/probe", headers={"cf-connecting-ip": "1.2.3.4"})
    r = client.get("/probe", headers={"cf-connecting-ip": "1.2.3.4"})
    assert r.status_code == 429
    assert r.json()["detail"].startswith("rate_limit_exceeded")
    assert "Retry-After" in r.headers
    assert int(r.headers["Retry-After"]) >= 1


def test_separate_ips_independently_counted():
    limiter = RateLimiter(name="t3", per_minute=2)
    client = _cf_client(limiter)
    # IP A burns its budget...
    for _ in range(2):
        assert client.get("/probe", headers={"cf-connecting-ip": "1.1.1.1"}).status_code == 200
    assert client.get("/probe", headers={"cf-connecting-ip": "1.1.1.1"}).status_code == 429
    # ... but IP B still has its full budget.
    for _ in range(2):
        assert client.get("/probe", headers={"cf-connecting-ip": "2.2.2.2"}).status_code == 200


def test_xff_is_never_used_as_a_key():
    """X-Forwarded-For's first hop is client-controlled even behind a trusted
    proxy, so rotating it must not change the key (DEF464)."""
    limiter = RateLimiter(name="t4", per_minute=2)
    client = _cf_client(limiter)
    for i in range(2):
        r = client.get("/probe", headers={"x-forwarded-for": f"9.9.9.{i}, 10.0.0.1"})
        assert r.status_code == 200
    r = client.get("/probe", headers={"x-forwarded-for": "9.9.9.200, 10.0.0.1"})
    assert r.status_code == 429


def test_untrusted_peer_cannot_rotate_key_via_cf_header():
    """DEF464: a LAN-direct caller sends a fresh cf-connecting-ip every time.
    The limiter must key on its socket address and still trip."""
    limiter = RateLimiter(name="t_spoof", per_minute=2)
    client = _cf_client(limiter, peer=UNTRUSTED_PEER)
    codes = [
        client.get("/probe", headers={"cf-connecting-ip": f"7.7.7.{i}"}).status_code
        for i in range(3)
    ]
    assert codes == [200, 200, 429]
    assert "ip:192.168.20.77" in limiter._hits
    assert not any(k.startswith("ip:7.7.7.") for k in limiter._hits)


def test_trusted_peer_keys_on_cf_connecting_ip():
    limiter = RateLimiter(name="t_trusted", per_minute=1)
    client = _cf_client(limiter)
    assert client.get("/probe", headers={"cf-connecting-ip": "8.8.8.8"}).status_code == 200
    assert client.get("/probe", headers={"cf-connecting-ip": "8.8.8.8"}).status_code == 429
    assert client.get("/probe", headers={"cf-connecting-ip": "8.8.4.4"}).status_code == 200
    assert {"ip:8.8.8.8", "ip:8.8.4.4"} <= set(limiter._hits)


def test_trusted_peer_with_garbage_cf_header_falls_back_to_peer():
    limiter = RateLimiter(name="t_garbage", per_minute=5)
    client = _cf_client(limiter)
    client.get("/probe", headers={"cf-connecting-ip": "not-an-ip"})
    assert list(limiter._hits) == ["ip:172.19.0.5"]


def test_empty_trusted_cidrs_trusts_nobody(monkeypatch: pytest.MonkeyPatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "rate_limit_trusted_proxy_cidrs", "")
    limiter = RateLimiter(name="t_none", per_minute=1)
    client = _cf_client(limiter)
    client.get("/probe", headers={"cf-connecting-ip": "8.8.8.8"})
    assert list(limiter._hits) == ["ip:172.19.0.5"]


def test_malformed_trusted_cidr_fails_loudly(monkeypatch: pytest.MonkeyPatch):
    from app.core.config import settings
    from app.services.rate_limit import _parse_trusted_networks

    monkeypatch.setattr(settings, "rate_limit_trusted_proxy_cidrs", "172.16.0.0/12,bogus")
    with pytest.raises(ValueError):
        _parse_trusted_networks(settings.rate_limit_trusted_proxy_cidrs)


def test_window_release_lets_traffic_through_again(monkeypatch: pytest.MonkeyPatch):
    """After WINDOW_SECONDS, the oldest timestamp ages out and a fresh request
    is accepted. We fast-forward `time.time` rather than sleep 60s."""
    from app.services import rate_limit as rl_mod

    limiter = RateLimiter(name="t5", per_minute=1)
    client = _cf_client(limiter)
    t = [time.time()]
    monkeypatch.setattr(rl_mod.time, "time", lambda: t[0])
    assert client.get("/probe", headers={"cf-connecting-ip": "1.2.3.4"}).status_code == 200
    assert client.get("/probe", headers={"cf-connecting-ip": "1.2.3.4"}).status_code == 429
    # Advance past the window.
    t[0] += rl_mod.WINDOW_SECONDS + 1
    assert client.get("/probe", headers={"cf-connecting-ip": "1.2.3.4"}).status_code == 200


def test_reset_clears_all_counters():
    limiter = RateLimiter(name="t6", per_minute=1)
    client = _cf_client(limiter)
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
    client = TestClient(app, client=TRUSTED_PEER)
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
