"""UAT area: Watchlist & price alerts (CR263, cases/watchlist_alerts.yaml).

Watchlist add is idempotent and validated against the ticker reference; price
alerts are soft-cancelled audit rows capped at 10 active per user. Alert
*firing* is a background evaluator driven by live prices, so it is a manual
case, not an API test that would only pass at certain market states.
"""

import time
import uuid

import httpx
import pytest


def _user(seed, **kw):
    for _ in range(12):
        try:
            return seed.user(**kw)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 429:
                raise
            time.sleep(20)
    return seed.user(**kw)


@pytest.fixture(scope="module")
def me(seed):
    return _user(seed, plan="floor_pass")


@pytest.fixture(scope="module")
def other(seed):
    return _user(seed, plan="floor_pass")


def _wl(u):
    r = u.get(f"/v1/watchlist/{u.id}")
    assert r.status_code == 200, r.text
    return r.json()


def _alerts(u, **params):
    r = u.get(f"/v1/price_alerts/{u.id}", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _new_alert(u, ticker="AAPL", kind="stop", price=100.0, **extra):
    return u.post(f"/v1/price_alerts/{u.id}",
                  json={"ticker": ticker, "threshold_type": kind, "threshold_price": price, **extra})


# ---------------------------------------------------------------- watchlist
@pytest.mark.uat("UAT-WATCH-001")
def test_watchlist_add_is_idempotent_and_remove_is_final(me):
    assert _wl(me) == {"items": [], "total": 0}

    r = me.post(f"/v1/watchlist/{me.id}", json={"ticker": "aapl", "notes": "first"})
    assert r.status_code == 201, r.text
    row = r.json()
    assert row["entry"]["ticker"] == "AAPL" and row["entry"]["notes"] == "first"
    assert row["entry"]["user_id"] == me.id
    assert row["price"] > 0 and row["price_source"], "the row carries a live quote"

    dup = me.post(f"/v1/watchlist/{me.id}", json={"ticker": " AAPL "})
    assert dup.status_code == 201
    assert dup.json()["entry"]["id"] == row["entry"]["id"], "duplicate add made a second row"
    assert dup.json()["entry"]["notes"] == "first", "a re-add without notes must not erase them"
    upd = me.post(f"/v1/watchlist/{me.id}", json={"ticker": "AAPL", "notes": "second"})
    assert upd.json()["entry"]["notes"] == "second"

    me.post(f"/v1/watchlist/{me.id}", json={"ticker": "MSFT"})
    lst = _wl(me)
    assert lst["total"] == 2 == len(lst["items"])
    assert {i["entry"]["ticker"] for i in lst["items"]} == {"AAPL", "MSFT"}
    assert all(i["price"] and i["price"] > 0 for i in lst["items"])

    assert me.delete(f"/v1/watchlist/{me.id}/aapl").status_code == 204
    assert {i["entry"]["ticker"] for i in _wl(me)["items"]} == {"MSFT"}
    gone = me.delete(f"/v1/watchlist/{me.id}/AAPL")
    assert gone.status_code == 404
    assert me.delete(f"/v1/watchlist/{me.id}/MSFT").status_code == 204
    assert _wl(me)["total"] == 0


@pytest.mark.uat("UAT-WATCH-002")
def test_watchlist_rejects_unknown_and_blank_tickers(me):
    before = _wl(me)
    bogus = me.post(f"/v1/watchlist/{me.id}", json={"ticker": "ZZZZQ"})
    assert bogus.status_code == 422
    assert bogus.json()["detail"]["exists"] is False
    assert me.post(f"/v1/watchlist/{me.id}", json={"ticker": "   "}).status_code == 400
    assert me.post(f"/v1/watchlist/{me.id}", json={}).status_code == 422
    assert me.post(f"/v1/watchlist/{me.id}", json={"ticker": ["AAPL"]}).status_code == 422
    assert _wl(me) == before


@pytest.mark.uat("UAT-WATCH-003")
def test_watchlist_belongs_to_its_owner(me, other, api):
    me.post(f"/v1/watchlist/{me.id}", json={"ticker": "KO"})
    before = _wl(me)
    assert other.get(f"/v1/watchlist/{me.id}").status_code == 403
    assert other.post(f"/v1/watchlist/{me.id}", json={"ticker": "PEP"}).status_code == 403
    assert other.delete(f"/v1/watchlist/{me.id}/KO").status_code == 403
    for call in (lambda: api.get(f"/v1/watchlist/{me.id}"),
                 lambda: api.post(f"/v1/watchlist/{me.id}", json={"ticker": "PEP"}),
                 lambda: api.delete(f"/v1/watchlist/{me.id}/KO")):
        assert call().status_code == 401
    assert _wl(me) == before
    assert _wl(other)["total"] == 0, "the stranger's own list must be untouched"
    me.delete(f"/v1/watchlist/{me.id}/KO")


@pytest.mark.uat("UAT-WATCH-004")
def test_buying_a_ticker_puts_it_on_the_watchlist(seed):
    """A fill is a property of 'I am following this name' — the watchlist gains
    the ticker without a separate add."""
    u = _user(seed, plan="trader")
    assert _wl(u)["total"] == 0
    r = u.post("/v1/sim/submit", json={"user_id": u.id, "ticker": "KO", "side": "buy", "quantity": 1})
    assert r.status_code == 200 and r.json()["ok"] is True, r.text
    assert "KO" in {i["entry"]["ticker"] for i in _wl(u)["items"]}


# ---------------------------------------------------------------- price alerts
@pytest.mark.uat("UAT-WATCH-005")
def test_price_alert_create_list_filter_cancel(me):
    base = len(_alerts(me)["items"])
    made = {}
    for kind, price in (("stop", 90.0), ("target", 500.0), ("manual_above", 450.0),
                        ("manual_below", 120.0)):
        r = _new_alert(me, "aapl", kind, price)
        assert r.status_code == 201, (kind, r.text)
        a = r.json()
        assert a["ticker"] == "AAPL" and a["threshold_type"] == kind
        assert a["threshold_price"] == price and a["status"] == "active"
        assert a["fired_at"] is None and a["cancelled_at"] is None
        assert a["user_id"] == me.id
        made[kind] = a

    lst = _alerts(me)
    assert lst["total"] == base + 4 == len(lst["items"])
    created = [a["created_at"] for a in lst["items"]]
    assert created == sorted(created, reverse=True), "newest first"
    assert {a["id"] for a in made.values()} <= {a["id"] for a in _alerts(me, status="active")["items"]}

    victim = made["stop"]
    c = me.delete(f"/v1/price_alerts/{me.id}/{victim['id']}")
    assert c.status_code == 200
    assert c.json()["status"] == "cancelled" and c.json()["cancelled_at"]
    cancelled = _alerts(me, status="cancelled")["items"]
    assert victim["id"] in {a["id"] for a in cancelled}
    assert victim["id"] not in {a["id"] for a in _alerts(me, status="active")["items"]}
    # soft cancel: the row stays as an audit trail
    assert victim["id"] in {a["id"] for a in _alerts(me)["items"]}

    again = me.delete(f"/v1/price_alerts/{me.id}/{victim['id']}")
    assert again.status_code == 409 and "cancelled" in again.json()["detail"]
    assert me.delete(f"/v1/price_alerts/{me.id}/{uuid.uuid4()}").status_code == 404
    for a in made.values():
        me.delete(f"/v1/price_alerts/{me.id}/{a['id']}")


@pytest.mark.uat("UAT-WATCH-006")
def test_price_alert_rejects_bad_type_ticker_and_foreign_trade(me):
    before = _alerts(me)["total"]
    assert _new_alert(me, kind="bogus").status_code == 422
    r = _new_alert(me, "ZZZZQ")
    assert r.status_code == 422 and r.json()["detail"]["exists"] is False
    assert me.post(f"/v1/price_alerts/{me.id}",
                   json={"ticker": "AAPL", "threshold_type": "stop"}).status_code == 422
    assert _new_alert(me, price="cheap").status_code == 422
    foreign = _new_alert(me, "AAPL", "stop", 100.0, trade_ref=str(uuid.uuid4()))
    assert foreign.status_code == 400
    assert _alerts(me)["total"] == before


@pytest.mark.uat("UAT-WATCH-007")
@pytest.mark.xfail(strict=True, reason=(
    "FINDING: POST /v1/price_alerts accepts threshold_price 0 and negative values (201, "
    "status active). Such an alert can never be meaningfully evaluated and sits ACTIVE, "
    "occupying one of the user's 10 slots. The phone sheet blocks <= 0 client-side "
    "(price_alert_sheet.dart:_submit) but the API does not."))
def test_price_alert_rejects_non_positive_price(me):
    created = []
    try:
        for bad in (0, -5.0):
            r = _new_alert(me, "AAPL", "stop", bad)
            if r.status_code == 201:
                created.append(r.json()["id"])
            assert r.status_code in (400, 422), (bad, r.status_code)
    finally:
        for aid in created:
            me.delete(f"/v1/price_alerts/{me.id}/{aid}")


@pytest.mark.uat("UAT-WATCH-008")
@pytest.mark.xfail(strict=True, reason=(
    "FINDING: POST /v1/price_alerts with threshold_price 1e12 returns HTTP 500 "
    "'internal server error' (unhandled; likely a numeric-column overflow) instead of a 422. Any absurd "
    "price a client sends takes the alert route down for that request."))
def test_price_alert_absurd_price_is_a_client_error_not_a_500(me):
    r = _new_alert(me, "AAPL", "target", 1e12)
    try:
        assert r.status_code in (400, 422), (r.status_code, r.text)
    finally:
        if r.status_code == 201:
            me.delete(f"/v1/price_alerts/{me.id}/{r.json()['id']}")


@pytest.mark.uat("UAT-WATCH-009")
def test_active_alert_cap_closes_the_oldest(seed):
    u = _user(seed, plan="floor_pass")
    ids = []
    for i in range(10):
        r = _new_alert(u, "AAPL", "manual_above", 400.0 + i)
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    assert len(_alerts(u, status="active")["items"]) == 10

    eleventh = _new_alert(u, "AAPL", "manual_above", 999.0)
    assert eleventh.status_code == 201 and eleventh.json()["status"] == "active"
    active = {a["id"] for a in _alerts(u, status="active")["items"]}
    assert len(active) == 10, "cap is 10 active alerts"
    assert eleventh.json()["id"] in active, "the new alert must survive"
    assert ids[0] not in active, "the OLDEST alert is the one auto-closed"
    oldest = next(a for a in _alerts(u)["items"] if a["id"] == ids[0])
    assert oldest["status"] == "cancelled" and oldest["cancelled_at"]


@pytest.mark.uat("UAT-WATCH-010")
def test_price_alerts_belong_to_their_owner(me, other, api):
    mine = _new_alert(me, "MSFT", "stop", 100.0).json()
    before = _alerts(me)
    assert other.get(f"/v1/price_alerts/{me.id}").status_code == 403
    assert other.post(f"/v1/price_alerts/{me.id}",
                      json={"ticker": "AAPL", "threshold_type": "stop",
                            "threshold_price": 1.0}).status_code == 403
    assert other.delete(f"/v1/price_alerts/{me.id}/{mine['id']}").status_code == 403
    # their own namespace + my alert id must not reach my row either
    assert other.delete(f"/v1/price_alerts/{other.id}/{mine['id']}").status_code == 404
    assert api.get(f"/v1/price_alerts/{me.id}").status_code == 401
    assert api.delete(f"/v1/price_alerts/{me.id}/{mine['id']}").status_code == 401
    assert _alerts(me) == before
    assert _alerts(other)["total"] == 0
    me.delete(f"/v1/price_alerts/{me.id}/{mine['id']}")
