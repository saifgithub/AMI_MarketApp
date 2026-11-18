"""DEF490: a request carrying the admin secret in `x-ami-ratelimit-exempt` is
not counted by the IP limiters; every other request still is.

The UAT harness runs from one IP and files more bug reports per hour than the
shared per-IP budget allows. The exemption is keyed on the admin secret
(compared in constant time), never on a spoofable client header, so DEF464's
guarantee (forwarded headers from an untrusted peer open no bucket) is intact.
"""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.services.rate_limit import RateLimiter

EXEMPT_HEADER = "x-ami-ratelimit-exempt"
TEST_SECRET = "def490-test-secret-not-a-real-one"
PEER = ("192.168.20.77", 50000)


def _client(limiter: RateLimiter) -> TestClient:
    app = FastAPI()

    @app.get("/probe", dependencies=[Depends(limiter)])
    def probe() -> dict[str, str]:
        return {"ok": "yes"}

    return TestClient(app, client=PEER)


def test_valid_secret_header_is_exempt(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "admin_secret", TEST_SECRET)
    limiter = RateLimiter(name="def490_valid", per_minute=2)
    client = _client(limiter)
    for _ in range(10):
        assert client.get("/probe", headers={EXEMPT_HEADER: TEST_SECRET}).status_code == 200
    # Exempt traffic recorded nothing: the full budget is still there.
    assert client.get("/probe").status_code == 200
    assert client.get("/probe").status_code == 200
    assert client.get("/probe").status_code == 429


def test_wrong_secret_is_counted(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "admin_secret", TEST_SECRET)
    limiter = RateLimiter(name="def490_wrong", per_minute=2)
    client = _client(limiter)
    h = {EXEMPT_HEADER: "not-the-secret"}
    assert client.get("/probe", headers=h).status_code == 200
    assert client.get("/probe", headers=h).status_code == 200
    assert client.get("/probe", headers=h).status_code == 429


def test_missing_header_is_counted(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "admin_secret", TEST_SECRET)
    limiter = RateLimiter(name="def490_missing", per_minute=2)
    client = _client(limiter)
    assert client.get("/probe").status_code == 200
    assert client.get("/probe").status_code == 200
    assert client.get("/probe").status_code == 429


@pytest.mark.parametrize("header_value", ["", "anything"])
def test_unset_secret_never_exempts(monkeypatch: pytest.MonkeyPatch, header_value: str):
    monkeypatch.setattr(settings, "admin_secret", "")
    limiter = RateLimiter(name="def490_empty", per_minute=2)
    client = _client(limiter)
    h = {EXEMPT_HEADER: header_value}
    assert client.get("/probe", headers=h).status_code == 200
    assert client.get("/probe", headers=h).status_code == 200
    assert client.get("/probe", headers=h).status_code == 429


def test_forwarded_headers_alone_never_exempt(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "admin_secret", TEST_SECRET)
    limiter = RateLimiter(name="def490_spoof", per_minute=1)
    client = _client(limiter)
    spoof1 = {"x-forwarded-for": "9.9.9.1", "cf-connecting-ip": "9.9.9.1"}
    spoof2 = {"x-forwarded-for": "9.9.9.2", "cf-connecting-ip": "9.9.9.2"}
    assert client.get("/probe", headers=spoof1).status_code == 200
    assert client.get("/probe", headers=spoof2).status_code == 429
