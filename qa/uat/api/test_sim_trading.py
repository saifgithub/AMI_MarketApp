"""UAT area: Sim trading & market data (CR263, cases/sim_trading.yaml).

Asserts the GOALS of the training simulator, not just status codes: a fill moves
cash by exactly qty x fill (+ toll when the flag is on) and creates the holding
and lot; a sell realises P&L from the real lot cost; an order that breaks the
mandate is refused by the deterministic floor with the book untouched; another
user's book is unreachable.

Off-hours behaviour (measured on Alpha, market CLOSED): the quote endpoints
serve the last Yahoo close with `source: yfinance`, and a market order still
fills at that price — so none of these tests depend on US market hours. Prices
can tick between two calls, so every money assertion is computed from the fill
the server reports, never from a number the test assumed.
"""

import time
import uuid

import httpx
import pytest

TOL = 0.02  # fills are rounded to cents server-side
PERIODS = ("1d", "1w", "1m", "3m", "1y", "5y")


# ---------------------------------------------------------------- helpers
def _snap(u):
    r = u.get(f"/v1/sim/portfolio/{u.id}")
    assert r.status_code == 200, r.text
    return r.json()


def _holding(snap, ticker):
    return next((h for h in snap["holdings"] if h["ticker"] == ticker), None)


def _submit(u, ticker, side="buy", quantity=1, **extra):
    r = u.post("/v1/sim/submit", json={
        "user_id": u.id, "ticker": ticker, "side": side, "quantity": quantity, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def _preview(u, ticker, side="buy", quantity=1, **extra):
    r = u.post("/v1/sim/preview", json={
        "user_id": u.id, "ticker": ticker, "side": side, "quantity": quantity, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def _patch_mandate(u, body):
    r = u.patch(f"/v1/mandate/{u.id}", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _toll(res):
    return res.get("toll_charged") or 0.0


def _assert_book_unchanged(before, after):
    assert after["current_cash"] == before["current_cash"]
    assert after["holdings"] == before["holdings"]
    assert after["resting_order_count"] == before["resting_order_count"]


def _user(seed, **kw):
    """`/v1/auth/anon` is 10/min per IP and parallel UAT suites share it; the
    shared Seeder gives up after ~3 min, so retry here for longer."""
    for _ in range(12):
        try:
            return seed.user(**kw)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 429:
                raise
            time.sleep(20)
    return seed.user(**kw)


# ---------------------------------------------------------------- fixtures
@pytest.fixture(scope="module")
def trader(seed):
    """Permissive mandate so the happy-path tests are not tripped by the
    day-1 over-trading brakes (4 trades/day, 3% single-name cap)."""
    u = _user(seed, plan="trader")
    _patch_mandate(u, {
        "single_name_cap_pct": 40.0, "sector_cap_pct": 100.0,
        "max_trades_per_day": 100, "max_trades_per_week": 200,
        "max_open_positions": 50, "post_loss_cooldown_hours": 0,
    })
    return u


@pytest.fixture(scope="module")
def rules(seed):
    """A second account for the mandate-refusal tests; each test sets and then
    restores only what it needs."""
    u = _user(seed, plan="trader")
    _patch_mandate(u, {
        "single_name_cap_pct": 40.0, "sector_cap_pct": 100.0,
        "max_trades_per_day": 100, "max_trades_per_week": 200,
        "max_open_positions": 50, "post_loss_cooldown_hours": 0,
    })
    return u


@pytest.fixture(scope="module")
def stranger(seed):
    return _user(seed, plan="trader")


# ---------------------------------------------------------------- market data
@pytest.mark.uat("UAT-SIM-001")
def test_quote_and_batch_quotes_are_sane(api):
    q = api.get("/v1/sim/quote/AAPL")
    assert q.status_code == 200
    body = q.json()
    assert body["ticker"] == "AAPL"
    assert body["price"] > 0
    assert body["source"] in ("yfinance", "mock_walk", "cache"), body
    assert body["source"] != "unavailable"
    assert isinstance(body["change_pct"], (int, float))
    assert body["market_state"], body

    batch = api.get("/v1/sim/quotes", params={"symbols": "aapl, MSFT"})
    assert batch.status_code == 200
    rows = batch.json()
    assert [r["ticker"] for r in rows] == ["AAPL", "MSFT"]
    assert all(r["price"] > 0 for r in rows)
    assert api.get("/v1/sim/quotes", params={"symbols": ""}).json() == []


@pytest.mark.uat("UAT-SIM-002")
@pytest.mark.xfail(strict=False, raises=TypeError, reason=(
    "DEF468 — /v1/sim/history intermittently serves a candle with null OHLC "
    "(yfinance NaN bar, seen 2026-10-20 03:00 after-hours). Non-strict: green when "
    "the feed is clean; any other assertion still fails."))
def test_history_candles_are_well_formed(api):
    for period in PERIODS:
        r = api.get("/v1/sim/history/AAPL", params={"period": period})
        assert r.status_code == 200, (period, r.text)
        body = r.json()
        assert body["period"] == period
        candles = body["candles"]
        assert len(candles) >= 2, period
        ts = [c["t"] for c in candles]
        assert ts == sorted(ts), f"{period}: candles not ascending in time"
        for c in candles:
            assert c["l"] <= c["o"] <= c["h"] and c["l"] <= c["c"] <= c["h"], c
            assert c["l"] > 0 and c["v"] >= 0
    # the chip labels are uppercase on the wire in old builds (DEF151)
    up = api.get("/v1/sim/history/AAPL", params={"period": "1M"})
    assert up.status_code == 200 and up.json()["period"] == "1m"
    bad = api.get("/v1/sim/history/AAPL", params={"period": "9y"})
    assert bad.status_code == 422


@pytest.mark.uat("UAT-SIM-003")
def test_earnings_and_dividend_fields(api):
    r = api.get("/v1/sim/earnings/AAPL")
    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == "AAPL"
    assert set(body) >= {"earnings_date", "quarter", "eps_estimate", "ex_dividend_date",
                         "dividend_rate", "source"}
    assert body["source"] != "unavailable", "earnings feed dark for AAPL"
    if body["earnings_date"]:
        assert len(body["earnings_date"]) == 10  # ISO date
    assert body["dividend_rate"] is None or body["dividend_rate"] > 0


@pytest.mark.uat("UAT-SIM-004")
@pytest.mark.xfail(strict=True, reason=(
    "DEF461 —  GET /v1/sim/news/AAPL and /MSFT return source 'unavailable' with no "
    "articles on Alpha (checked 2026-10-19, repeatedly); the Ticker Detail news list "
    "and Sector Watch card 3 (reason no_news) are therefore dark for every ticker"))
def test_news_for_a_major_ticker_is_served(api):
    r = api.get("/v1/sim/news/AAPL", params={"limit": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] != "unavailable"
    assert 1 <= len(body["articles"]) <= 3
    for a in body["articles"]:
        assert a["title"] and a["link"].startswith("http")


@pytest.mark.uat("UAT-SIM-005")
def test_company_profile_and_insider_activity(api):
    p = api.get("/v1/sim/company-profile/AAPL")
    assert p.status_code == 200
    body = p.json()
    assert body["ticker"] == "AAPL"
    assert body["cik"] == "0000320193"
    assert body["overview"]["state"] in ("live", "partial")
    assert body["overview"]["legal_name"]
    for section in ("overview", "financials", "filings", "ownership"):
        assert section in body, section
        assert body[section]["state"], f"{section} carries no state"

    i = api.get("/v1/sim/insider/AAPL")
    assert i.status_code == 200
    ib = i.json()
    assert ib["window_days"] == 90
    assert ib["state"] in ("live", "partial", "not_available")
    s = ib["summary"]
    assert s["buys"] + s["sells"] + s["other"] == len(ib["transactions"]) or ib["state"] == "partial"
    for t in ib["transactions"]:
        assert t["direction"] in ("buy", "sell", "other")
        if t["direction"] != "other":
            assert t["code"] in ("P", "S")


@pytest.mark.uat("UAT-SIM-006")
def test_bogus_ticker_is_never_passed_off_as_real(api, trader):
    v = api.get("/v1/tickers/validate", params={"ticker": "zzzzq"}).json()
    assert v["exists"] is False and v["ticker"] == "ZZZZQ"
    ok = api.get("/v1/tickers/validate", params={"ticker": "aapl"}).json()
    assert ok["exists"] is True and ok["ticker"] == "AAPL" and ok["company_name"]

    # Observed (not asserted as a defect): quote/history answer 200 with a
    # mock-walk series for an unknown symbol. The contract that matters is that
    # it is labelled as such, never as a live source (CR040).
    q = api.get("/v1/sim/quote/ZZZZQ")
    if q.status_code == 200:
        assert q.json()["source"] in ("mock_walk", "unavailable"), q.text
    h = api.get("/v1/sim/history/ZZZZQ", params={"period": "1m"})
    if h.status_code == 200:
        assert h.json()["source"] in ("mock_walk", "unavailable"), h.text

    assert api.get("/v1/sim/company-profile/ZZZZQ").status_code == 404
    assert api.get("/v1/sim/company-profile/BAD%20TICKER!!").status_code == 422
    ins = api.get("/v1/sim/insider/ZZZZQ").json()
    assert ins["state"] == "not_available" and ins["transactions"] == []

    # ... and no order can ever be placed on it.
    before = _snap(trader)
    for path in ("/v1/sim/preview", "/v1/sim/submit"):
        r = trader.post(path, json={"user_id": trader.id, "ticker": "ZZZZQ",
                                    "side": "buy", "quantity": 1})
        assert r.status_code == 422, (path, r.text)
        assert r.json()["detail"]["exists"] is False
    _assert_book_unchanged(before, _snap(trader))


# ---------------------------------------------------------------- fills
@pytest.mark.uat("UAT-SIM-007")
def test_buy_moves_cash_by_exactly_qty_times_fill_and_creates_holding_and_lot(trader):
    before = _snap(trader)
    assert before["starting_capital"] == 10000.0
    assert _holding(before, "AAPL") is None
    pv = _preview(trader, "AAPL", quantity=3)
    assert pv["accepted"] is True and pv["compliance"]["passed"] is True
    assert _snap(trader)["current_cash"] == before["current_cash"], "preview must not persist"

    res = _submit(trader, "AAPL", quantity=3)
    assert res["ok"] is True and res["resting"] is False
    trade = res["trade"]
    fill = trade["entry_price"]
    assert trade["side"] == "buy" and trade["quantity"] == 3 and trade["status"] == "open"
    assert abs(fill - pv["fill_price"]) < 5.0, "preview and fill disagree wildly"

    after = _snap(trader)
    spent = round(before["current_cash"] - after["current_cash"], 2)
    assert abs(spent - (3 * fill + _toll(res))) <= TOL, (spent, fill, res.get("toll_charged"))
    h = _holding(after, "AAPL")
    assert h and h["quantity"] == 3 and abs(h["avg_cost"] - fill) <= TOL
    assert abs(after["total_value"] - before["total_value"]) < 0.01 * before["total_value"]

    lots = trader.get(f"/v1/sim/lots/{trader.id}/AAPL").json()
    assert len(lots["lots"]) == 1
    lot = lots["lots"][0]
    assert lot["entry_trade_id"] == trade["id"] and lot["quantity_open"] == 3
    assert abs(lot["entry_price"] - fill) <= TOL and lot["status"] == "open"
    assert lots["totals"]["realised_pnl"] == 0.0

    listed = trader.get(f"/v1/sim/trades/{trader.id}").json()
    assert any(t["id"] == trade["id"] for t in listed["trades"])
    assert listed["total"] == len(listed["trades"])


@pytest.mark.uat("UAT-SIM-008")
def test_sell_realises_pnl_from_the_lot_and_cannot_oversell(trader):
    buy = _submit(trader, "MSFT", quantity=2)
    assert buy["ok"] is True
    entry = buy["trade"]["entry_price"]
    cash0 = _snap(trader)["current_cash"]

    sell = _submit(trader, "MSFT", side="sell", quantity=1)
    assert sell["ok"] is True, sell
    exit_px = sell["trade"]["entry_price"]  # the sell row records its own fill here
    snap = _snap(trader)
    gained = round(snap["current_cash"] - cash0, 2)
    assert abs(gained - (exit_px - _toll(sell))) <= TOL, (gained, exit_px)
    assert _holding(snap, "MSFT")["quantity"] == 1

    lots = trader.get(f"/v1/sim/lots/{trader.id}/MSFT").json()
    assert lots["lots"][0]["status"] == "partially_closed"
    assert lots["lots"][0]["quantity_closed"] == 1
    assert abs(lots["totals"]["realised_pnl"] - (exit_px - entry)) <= 0.05, lots["totals"]

    # cannot sell more than held (that would open a short on a long-only mandate)
    cash1 = snap["current_cash"]
    over = _submit(trader, "MSFT", side="sell", quantity=5)
    assert over["ok"] is False and over["compliance"]["passed"] is False
    assert over["compliance"]["blocked_by"] == "long_only"
    assert _snap(trader)["current_cash"] == cash1

    # close out the rest: position disappears, lot fully closed
    last = _submit(trader, "MSFT", side="sell", quantity=1)
    assert last["ok"] is True
    final = _snap(trader)
    assert _holding(final, "MSFT") is None
    lots = trader.get(f"/v1/sim/lots/{trader.id}/MSFT").json()
    assert lots["totals"]["quantity_open"] == 0
    exit2 = last["trade"]["entry_price"]
    assert abs(lots["totals"]["realised_pnl"] - ((exit_px - entry) + (exit2 - entry))) <= 0.1


@pytest.mark.uat("UAT-SIM-009")
def test_manual_close_returns_the_lot_to_cash_at_the_close_price(trader):
    buy = _submit(trader, "KO", quantity=4)
    assert buy["ok"] is True
    tid, entry = buy["trade"]["id"], buy["trade"]["entry_price"]
    cash0 = _snap(trader)["current_cash"]

    r = trader.post(f"/v1/sim/trades/{trader.id}/close", json={"trade_id": tid})
    assert r.status_code == 200, r.text
    closed = r.json()["trade"]
    assert closed["status"] == "closed" and closed["closed_at"]
    px = closed["closed_price"]
    assert abs(closed["realised_pnl"] - (px - entry) * 4) <= 0.1
    snap = _snap(trader)
    assert abs((snap["current_cash"] - cash0) - 4 * px) <= 0.05
    assert _holding(snap, "KO") is None

    again = trader.post(f"/v1/sim/trades/{trader.id}/close", json={"trade_id": tid})
    assert again.status_code == 404
    unknown = trader.post(f"/v1/sim/trades/{trader.id}/close", json={"trade_id": str(uuid.uuid4())})
    assert unknown.status_code == 404


# ---------------------------------------------------------------- mandate floor
def _assert_refused(u, before, res, blocked_by=None):
    assert res["ok"] is False, f"order was ACCEPTED: {res}"
    c = res["compliance"]
    assert c["passed"] is False and c["violations"], c
    if blocked_by:
        assert c["blocked_by"] == blocked_by, c
    else:
        assert c["blocked_by"], c
    _assert_book_unchanged(before, _snap(u))


@pytest.mark.uat("UAT-SIM-010")
def test_mandate_ticker_rules_are_enforced_not_just_warned(rules):
    # Halal: a screened-out name is refused by the deterministic check
    _patch_mandate(rules, {"compliance": {"halal": True}})
    try:
        before = _snap(rules)
        pv = _preview(rules, "JPM")
        assert pv["accepted"] is False
        assert pv["compliance"]["sharia_verdict"]["status"] == "screened_out" \
            or "AAOIFI" in " ".join(pv["compliance"]["violations"])
        _assert_refused(rules, before, _submit(rules, "JPM"), "compliance")
        # and a passing halal name still trades (the floor is not simply 'no')
        assert _preview(rules, "AAPL")["accepted"] is True
    finally:
        _patch_mandate(rules, {"compliance": {"halal": False}})

    # Blocklist
    _patch_mandate(rules, {"compliance": {"ticker_blocklist": ["TSLA"]}})
    try:
        before = _snap(rules)
        _assert_refused(rules, before, _submit(rules, "TSLA"), "blocklist")
    finally:
        _patch_mandate(rules, {"compliance": {"ticker_blocklist": []}})

    # Allowlist: everything outside it is refused
    _patch_mandate(rules, {"compliance": {"ticker_allowlist": ["MSFT"]}})
    try:
        before = _snap(rules)
        _assert_refused(rules, before, _submit(rules, "AAPL"), "allowlist")
        assert _preview(rules, "MSFT")["accepted"] is True
    finally:
        _patch_mandate(rules, {"compliance": {"ticker_allowlist": None}})


@pytest.mark.uat("UAT-SIM-011")
def test_risk_limits_refuse_oversized_and_overconcentrated_orders(rules):
    # Single-name cap: at 3% of $10k a $343 share is already over
    _patch_mandate(rules, {"single_name_cap_pct": 3.0})
    try:
        before = _snap(rules)
        res = _submit(rules, "AAPL", quantity=1)
        _assert_refused(rules, before, res, "concentration")
        assert "single-name cap" in " ".join(res["compliance"]["violations"])
    finally:
        _patch_mandate(rules, {"single_name_cap_pct": 40.0})

    # Max open positions
    first = _submit(rules, "AAPL", quantity=1)
    assert first["ok"] is True
    _patch_mandate(rules, {"max_open_positions": 1})
    try:
        before = _snap(rules)
        res = _submit(rules, "KO", quantity=1)
        _assert_refused(rules, before, res, "max_open_positions")
        # adding to an existing holding is unaffected
        assert _submit(rules, "AAPL", quantity=1)["ok"] is True
    finally:
        _patch_mandate(rules, {"max_open_positions": 50})

    # Sector concentration (AAPL is already held, so Technology is occupied)
    _patch_mandate(rules, {"sector_cap_pct": 5.0})
    try:
        before = _snap(rules)
        _assert_refused(rules, before, _submit(rules, "MSFT", quantity=1), "compliance")
    finally:
        _patch_mandate(rules, {"sector_cap_pct": 100.0})

    # More than the cash on hand
    _patch_mandate(rules, {"single_name_cap_pct": 100.0})
    try:
        before = _snap(rules)
        _assert_refused(rules, before, _submit(rules, "NVDA", quantity=500))
    finally:
        _patch_mandate(rules, {"single_name_cap_pct": 40.0})


@pytest.mark.uat("UAT-SIM-012")
def test_long_only_mandate_refuses_to_open_a_short(rules):
    comp = _patch_mandate(rules, {})["compliance"]
    assert comp["long_only"] is True
    before = _snap(rules)
    res = _submit(rules, "XOM", side="sell", quantity=1)
    _assert_refused(rules, before, res, "long_only")
    assert "long-only" in " ".join(res["compliance"]["violations"])
    assert before["shorts"] == [] and _snap(rules)["shorts"] == []


@pytest.mark.uat("UAT-SIM-013")
def test_client_cannot_loosen_the_stored_mandate_per_order(rules):
    """The floor is uncoachable: a `mandate_override` in the request body is for
    users with no stored mandate, never a way around the one they set."""
    _patch_mandate(rules, {"compliance": {"ticker_blocklist": ["TSLA"]}})
    try:
        before = _snap(rules)
        for body in ({"compliance": {"ticker_blocklist": []}},
                     {"compliance": {"ticker_blocklist": [], "long_only": False}},
                     {"single_name_cap_pct": 100.0}):
            res = _submit(rules, "TSLA", mandate_override=body)
            _assert_refused(rules, before, res, "blocklist")
            pv = _preview(rules, "TSLA", mandate_override=body)
            assert pv["accepted"] is False
    finally:
        _patch_mandate(rules, {"compliance": {"ticker_blocklist": []}})


@pytest.mark.uat("UAT-SIM-014")
def test_preview_runs_the_same_check_and_never_persists(rules):
    _patch_mandate(rules, {"compliance": {"ticker_blocklist": ["TSLA"]}})
    try:
        before = _snap(rules)
        pv = _preview(rules, "TSLA")
        res = _submit(rules, "TSLA")
        assert pv["accepted"] is False and res["ok"] is False
        assert pv["compliance"]["blocked_by"] == res["compliance"]["blocked_by"] == "blocklist"
        assert pv["compliance"]["violations"] == res["compliance"]["violations"]
        _assert_book_unchanged(before, _snap(rules))
    finally:
        _patch_mandate(rules, {"compliance": {"ticker_blocklist": []}})

    before = _snap(rules)
    pv = _preview(rules, "KO", quantity=2)
    assert pv["accepted"] is True
    assert abs(pv["notional"] - 2 * pv["fill_price"]) < 0.05
    assert pv["cash_available"] == before["cash_available"]
    _assert_book_unchanged(before, _snap(rules))


@pytest.mark.uat("UAT-SIM-015")
def test_malformed_orders_are_rejected_before_they_touch_the_book(trader):
    before = _snap(trader)
    base = {"user_id": trader.id, "ticker": "AAPL", "side": "buy", "quantity": 1}
    bad = [
        {**base, "quantity": 0},
        {**base, "quantity": -3},
        {**base, "side": "hold"},
        {**base, "order_type": "limit"},                       # no limit_price
        {**base, "order_type": "stop"},                        # no trigger_price
        {**base, "order_type": "limit", "limit_price": -1},
        {**base, "order_type": "limit", "limit_price": 100, "tif": "gtc"},
        {**base, "tif": "gtd_30"},                             # market order has no TIF
        {**base, "ticker": "ZZZZQ"},
    ]
    for body in bad:
        for path in ("/v1/sim/submit", "/v1/sim/preview"):
            r = trader.post(path, json=body)
            assert r.status_code == 422, (path, body, r.status_code, r.text)
    _assert_book_unchanged(before, _snap(trader))


@pytest.mark.uat("UAT-SIM-016")
def test_resting_limit_order_reserves_cash_and_can_be_cancelled(trader):
    before = _snap(trader)
    res = _submit(trader, "MSFT", quantity=1, order_type="limit", limit_price=100.0, tif="day")
    assert res["ok"] is True and res["resting"] is True and res["trade"] is None
    order = res["order"]
    assert order["state"] == "working", order

    snap = _snap(trader)
    assert snap["current_cash"] == before["current_cash"], "a resting order must not spend cash yet"
    assert snap["resting_order_count"] == before["resting_order_count"] + 1
    assert snap["cash_committed"] > before["cash_committed"]
    assert snap["cash_available"] < before["cash_available"]
    assert _holding(snap, "MSFT") is None

    listed = trader.get(f"/v1/sim/orders/{trader.id}").json()["orders"]
    assert any(o["id"] == order["id"] for o in listed)

    c = trader.post(f"/v1/sim/orders/{trader.id}/{order['id']}/cancel")
    assert c.status_code == 200 and c.json()["cancelled"] is True
    assert c.json()["state"] == "cancelled"
    snap = _snap(trader)
    assert snap["resting_order_count"] == before["resting_order_count"]
    assert snap["cash_committed"] == before["cash_committed"]
    assert snap["current_cash"] == before["current_cash"]

    again = trader.post(f"/v1/sim/orders/{trader.id}/{order['id']}/cancel")
    assert again.status_code == 200 and again.json()["cancelled"] is False
    assert again.json()["state"] == "cancelled"
    missing = trader.post(f"/v1/sim/orders/{trader.id}/{uuid.uuid4()}/cancel")
    assert missing.status_code == 404


@pytest.mark.uat("UAT-SIM-017")
def test_another_users_book_is_unreachable(trader, stranger, api):
    before = _snap(trader)
    uid = trader.id
    tid = trader.get(f"/v1/sim/trades/{uid}").json()["trades"][0]["id"]
    reads = [
        f"/v1/sim/portfolio/{uid}", f"/v1/sim/portfolio/{uid}/history",
        f"/v1/sim/trades/{uid}", f"/v1/sim/orders/{uid}", f"/v1/sim/lots/{uid}/AAPL",
    ]
    for p in reads:
        assert stranger.get(p).status_code == 403, p
        assert api.get(p).status_code == 401, p
    body = {"user_id": uid, "ticker": "AAPL", "side": "buy", "quantity": 1}
    for p in ("/v1/sim/submit", "/v1/sim/preview"):
        assert stranger.post(p, json=body).status_code == 403, p
        assert api.post(p, json=body).status_code == 401, p
    assert stranger.post(f"/v1/sim/portfolio/{uid}/reset").status_code == 403
    assert stranger.post(f"/v1/sim/trades/{uid}/close", json={"trade_id": tid}).status_code == 403
    assert stranger.post(f"/v1/sim/trades/{uid}/evaluate").status_code == 403
    assert stranger.post(f"/v1/sim/orders/{uid}/{uuid.uuid4()}/cancel").status_code == 403
    _assert_book_unchanged(before, _snap(trader))


@pytest.mark.uat("UAT-SIM-018")
def test_reset_is_rate_limited_to_once_a_day(stranger):
    u = stranger
    before = _snap(u)
    r = u.post(f"/v1/sim/portfolio/{u.id}/reset")
    assert r.status_code == 429
    assert r.json()["detail"] == "reset_cooldown"
    retry = int(r.headers["Retry-After"])
    assert 0 < retry <= 24 * 3600
    assert _snap(u) == before, "a refused reset must leave the book exactly as it was"


@pytest.mark.uat("UAT-SIM-019")
def test_trade_ledger_paging_history_and_evaluate(trader):
    uid = trader.id
    full = trader.get(f"/v1/sim/trades/{uid}").json()
    assert full["total"] == len(full["trades"]) >= 3
    page = trader.get(f"/v1/sim/trades/{uid}", params={"limit": 2, "offset": 1}).json()
    assert page["total"] == full["total"] and len(page["trades"]) == 2
    assert [t["id"] for t in page["trades"]] == [t["id"] for t in full["trades"][1:3]]
    for q in ({"limit": 0}, {"limit": 501}, {"offset": -1}):
        assert trader.get(f"/v1/sim/trades/{uid}", params=q).status_code == 422, q
    closed = trader.get(f"/v1/sim/trades/{uid}", params={"status_filter": "closed"}).json()
    assert closed["trades"] and all(t["status"] == "closed" for t in closed["trades"])

    h = trader.get(f"/v1/sim/portfolio/{uid}/history")
    assert h.status_code == 200 and "points" in h.json() and "twr_pct" in h.json()
    assert trader.get(f"/v1/sim/portfolio/{uid}/history", params={"limit": 0}).status_code == 422

    before = _snap(trader)
    ev = trader.post(f"/v1/sim/trades/{uid}/evaluate")
    assert ev.status_code == 200 and ev.json()["ok"] is True
    assert isinstance(ev.json()["updates"], list)
    # nothing is bracketed, so nothing may close or move cash
    assert ev.json()["updates"] == []
    assert _snap(trader)["current_cash"] == before["current_cash"]


# ---------------------------------------------------------------- options
def _first_candidate(u):
    r = u.post("/v1/sim/options/propose",
               json={"user_id": u.id, "ticker": "AAPL", "direction": "bullish"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["expiry"] and body["spot"] and body["candidates"], body
    cand = body["candidates"][0]
    legs = [{"right": l["right"], "strike": l["strike"], "quantity": l["quantity"]}
            for l in cand["legs"]]
    return cand, legs


@pytest.mark.uat("UAT-SIM-020")
def test_options_are_blocked_until_derivatives_are_allowed(stranger):
    u = stranger
    comp = _patch_mandate(u, {})["compliance"]
    assert comp["derivatives_allowed"] is False
    cand, legs = _first_candidate(u)
    assert cand["compliance"]["passed"] is False
    assert "derivatives" in " ".join(cand["compliance"]["violations"]).lower()
    before = _snap(u)

    open_body = {"user_id": u.id, "ticker": "AAPL", "strategy_name": cand["strategy_name"],
                 "expiry": cand["expiry"], "legs": legs}
    r = u.post("/v1/sim/options/open", json=open_body)
    assert r.status_code == 200
    o = r.json()
    assert o["accepted"] is False and o["compliance"]["blocked_by"] == "compliance"
    assert o["strategy_id"] is None and o["net_cost"] is None
    _assert_book_unchanged(before, _snap(u))
    assert _snap(u)["options"] == []

    # reprice is read-only and reports the drift against what the client was shown
    rp = u.post("/v1/sim/options/reprice", json={
        "user_id": u.id, "ticker": "AAPL", "strategy_name": cand["strategy_name"],
        "expiry": cand["expiry"], "spot_then": cand["spot"],
        "legs": [dict(l, premium_then=cand["legs"][i]["premium"]) for i, l in enumerate(legs)],
    })
    assert rp.status_code == 200, rp.text
    body = rp.json()
    assert body["repriced"] is True
    d = body["drift"]
    assert d["spot_then"] == cand["spot"] and d["spot_now"] > 0
    assert len(d["legs"]) == len(legs)
    assert all(abs(x["premium_now"] - x["premium_then"]) < max(1.0, 0.25 * x["premium_then"])
               for x in d["legs"]), "premium drifted implausibly within seconds"
    assert body["structure"]["compliance"]["passed"] is False
    _assert_book_unchanged(before, _snap(u))

    # Turning derivatives on does not bypass the money check: a structure that
    # costs more than the cash on hand is refused and charges nothing.
    _patch_mandate(u, {"compliance": {"derivatives_allowed": True}})
    r = u.post("/v1/sim/options/open", json=open_body)
    assert r.status_code == 200
    o = r.json()
    cost = cand["metrics"]["net_cost"]
    if cost > before["current_cash"]:
        assert o["accepted"] is False, o
    after = _snap(u)
    if not o["accepted"]:
        _assert_book_unchanged(before, after)
        assert after["options"] == []


@pytest.mark.uat("UAT-SIM-021")
def test_option_routes_validate_and_enforce_ownership(trader, stranger, api):
    base = {"user_id": trader.id, "ticker": "AAPL", "direction": "bullish"}
    assert stranger.post("/v1/sim/options/propose", json=base).status_code == 403
    assert api.post("/v1/sim/options/propose", json=base).status_code == 401
    assert trader.post("/v1/sim/options/propose", json={**base, "ticker": "ZZZZQ"}).status_code == 422
    assert trader.post("/v1/sim/options/propose", json={**base, "direction": "sideways"}).status_code == 422
    leg = {"right": "call", "strike": 100.0, "quantity": 1}
    body = {"user_id": trader.id, "ticker": "AAPL", "strategy_name": "long_call",
            "expiry": "2026-12-18", "legs": [leg]}
    assert stranger.post("/v1/sim/options/open", json=body).status_code == 403
    assert trader.post("/v1/sim/options/open", json={**body, "legs": []}).status_code == 422
    assert trader.post("/v1/sim/options/open",
                       json={**body, "legs": [{**leg, "right": "straddle"}]}).status_code == 422
    assert trader.post("/v1/sim/options/open",
                       json={**body, "legs": [{**leg, "strike": -5}]}).status_code == 422
    # a client-stated premium is never accepted as an input (it would mint cash)
    cheat = trader.post("/v1/sim/options/open",
                        json={**body, "legs": [{**leg, "premium": 0.01}]})
    assert cheat.status_code in (200, 422)
    if cheat.status_code == 200:
        assert cheat.json()["accepted"] is False
