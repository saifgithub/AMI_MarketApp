"""UAT area: Alpaca paper link (CR263, cases/alpaca.yaml).

The backend holds no Alpaca credential (CR202); the only direct Alpaca calls here
are two read-only GET /v2/account probes with the dedicated UAT paper key. No
order is ever placed, and no credential is printed or put in an assertion message.
"""

from urllib.parse import urlparse

import httpx
import pytest

from client import env

LIVE_BASE = "https://api.alpaca.markets/v2"


def _headers():
    key, secret = env("ALPACA_PAPER_KEY_ID"), env("ALPACA_PAPER_SECRET")
    if not key or not secret:
        pytest.fail("no ALPACA_PAPER_KEY_ID / ALPACA_PAPER_SECRET in qa/uat/.uat.env")
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}


@pytest.mark.uat("UAT-ALPACA-001")
def test_alpaca_routes_refuse_unclaimed(api, seed):
    bodies = {
        "/v1/alpaca/link_state": {"linked": True},
        "/v1/alpaca/link": {"code": "uat-not-a-real-code"},
        "/v1/alpaca/order_log": {"symbol": "AAPL", "side": "buy", "qty": 1,
                                 "destination": "alpaca_only", "outcome": "submitted"},
    }
    for path, body in bodies.items():
        assert api.post(path, json=body).status_code == 401, path

    u = seed.anon_user()
    before = seed.detail(u)
    for path, body in bodies.items():
        r = u.post(path, json=body)
        assert r.status_code == 403, (path, r.status_code)
        assert "not claimed" in r.json()["detail"]
        assert "access_token" not in r.text
    after = seed.detail(u)
    assert after["plan"] == before["plan"]
    assert after["credit_balance"] == before["credit_balance"]
    assert len(after["recent_events"]) == len(before["recent_events"])
    me = u.get("/v1/auth/me").json()
    assert me["is_anonymous"] is True


@pytest.mark.uat("UAT-ALPACA-002")
def test_paper_key_reaches_paper_not_live():
    base = (env("ALPACA_PAPER_BASE_URL") or "").rstrip("/")
    assert urlparse(base).hostname and "paper-api" in urlparse(base).hostname
    h = _headers()
    paper = httpx.get(f"{base}/account", headers=h, timeout=20)
    assert paper.status_code == 200
    assert paper.json().get("status") == "ACTIVE"
    live = httpx.get(f"{LIVE_BASE}/account", headers=h, timeout=20)
    assert live.status_code in (401, 403)
