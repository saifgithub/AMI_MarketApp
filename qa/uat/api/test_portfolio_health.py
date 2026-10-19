"""UAT area: Portfolio health & sector analytics (CR263, cases/portfolio_health.yaml).

The tiles are FREE in every gate mode; only Finding generation (the one LLM
call) is gated. These tests prove the tiles are measured from the real book,
the gate is reported truthfully per plan, the Finding endpoint refuses before
spending anything it should not, and the one LLM-spending case is capped at a
single call (a Finding is idempotent per portfolio per day, so its replay is
free and is asserted as such).

Alpha gate config at time of writing (measured via GET /health `gate`):
mode "trial", 3 trial Findings, 2/day cap, 30-day cadence. The 402/429 gate
refusals themselves need either mode "plan" or >=4 paid Findings, so they are a
blocked catalogue case rather than a skipped test.
"""

import time

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


def _patch_mandate(u, body):
    r = u.patch(f"/v1/mandate/{u.id}", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _health(u):
    r = u.get(f"/v1/portfolio/health/{u.id}")
    assert r.status_code == 200, r.text
    return r.json()


def _alloc(u):
    r = u.get(f"/v1/portfolio/sector-allocation/{u.id}")
    assert r.status_code == 200, r.text
    return r.json()


GATE_KEYS = {"mode", "trial_active", "trial_findings_used", "trial_findings_budget",
             "trial_days_left", "daily_used", "daily_cap", "plan_has_access",
             "cadence_days", "cadence_blocked", "next_eligible_at"}


@pytest.fixture(scope="module")
def free(seed):
    """Floor Pass, empty book."""
    return _user(seed, plan="floor_pass")


@pytest.fixture(scope="module")
def rich(seed):
    """Trader holding 5 AAPL."""
    u = _user(seed, plan="trader")
    _patch_mandate(u, {"single_name_cap_pct": 40.0, "sector_cap_pct": 100.0,
                       "max_trades_per_day": 100, "max_trades_per_week": 200,
                       "post_loss_cooldown_hours": 0})
    r = u.post("/v1/sim/submit", json={"user_id": u.id, "ticker": "AAPL",
                                       "side": "buy", "quantity": 5})
    assert r.status_code == 200 and r.json()["ok"] is True, r.text
    return u


@pytest.mark.uat("UAT-HLTH-001")
def test_tiles_for_an_empty_book_are_free_and_say_so(free):
    h = _health(free)
    assert h["status"] == "no_holdings"
    assert h["metrics"]["status"] == "no_holdings"
    assert h["engine_version"] and h["as_of"]
    assert set(h["gate"]) == GATE_KEYS
    # a free-plan user reads the tiles with a 200, never a 402/429
    assert h["gate"]["plan_has_access"] is False


@pytest.mark.uat("UAT-HLTH-002")
def test_tiles_are_measured_from_the_real_book(rich):
    snap = rich.get(f"/v1/sim/portfolio/{rich.id}").json()
    h = _health(rich)
    assert h["status"] == "ok", h["status"]
    m = h["metrics"]
    assert m["holdings_count"] == 1
    held = m["holdings"][0]
    assert held["ticker"] == "AAPL" and held["included"] is True
    assert held["sector"] == "Technology"
    assert held["invested_weight_pct"] == pytest.approx(100.0, abs=0.01)
    assert m["total_value"] == pytest.approx(snap["total_value"], rel=0.01)
    invested = sum(x["value"] for x in snap["holdings"])
    assert m["invested_value"] == pytest.approx(invested, rel=0.01)
    assert m["cash_fraction"] == pytest.approx(snap["current_cash"] / snap["total_value"], abs=0.01)
    assert m["dropped_holdings"] == []

    blocks = m["blocks"]
    for name in ("portfolio_volatility", "beta", "weight_concentration", "risk_contribution"):
        assert name in blocks, name
        b = blocks[name]
        assert isinstance(b["sufficient"], bool)
        if b["sufficient"]:
            assert b["value"] is not None
        else:
            assert b["insufficient_cause"], f"{name}: insufficient with no stated cause"
    # one holding is one bet: concentration is total
    assert blocks["weight_concentration"]["value"] == pytest.approx(1.0)
    assert blocks["effective_bets"]["value"] == pytest.approx(1.0)
    assert blocks["portfolio_volatility"]["value"] > 0
    assert h["gate"]["plan_has_access"] is True  # trader is entitled


@pytest.mark.uat("UAT-HLTH-003")
def test_gate_is_reported_truthfully_per_plan(free, rich):
    g_free, g_rich = _health(free)["gate"], _health(rich)["gate"]
    assert g_free["mode"] == g_rich["mode"]
    assert g_free["plan_has_access"] is False and g_rich["plan_has_access"] is True
    assert g_free["trial_findings_budget"] >= 1 and g_free["trial_findings_used"] == 0
    assert g_free["daily_used"] == 0 and g_free["daily_cap"] >= 1
    if g_free["mode"] == "trial":
        assert g_free["trial_active"] is True  # a fresh Floor Pass user still has the trial
    assert g_free["cadence_blocked"] is False


@pytest.mark.uat("UAT-HLTH-004")
def test_sector_allocation_matches_the_book_and_reads_the_mandate_cap(free, rich):
    empty = _alloc(free)
    assert empty["allocation"] == {}
    assert empty["compliance"]["compliant"] is True
    assert empty["compliance"]["max_sector_name"] is None
    assert empty["total_value"] == pytest.approx(10000.0, abs=1.0)

    snap = rich.get(f"/v1/sim/portfolio/{rich.id}").json()
    a = _alloc(rich)
    assert set(a["allocation"]) == {"Technology", "Cash"}
    assert sum(a["allocation"].values()) == pytest.approx(1.0, abs=0.001)
    tech = snap["holdings"][0]["value"] / snap["total_value"]
    assert a["allocation"]["Technology"] == pytest.approx(tech, abs=0.005)
    assert a["allocation"]["Cash"] == pytest.approx(snap["current_cash"] / snap["total_value"], abs=0.005)
    c = a["compliance"]
    assert c["max_sector_name"] == "Technology" and c["max_sector"] == a["allocation"]["Technology"]
    assert c["compliant"] is True and c["max_allowed"] == pytest.approx(
        rich.get(f"/v1/mandate/{rich.id}").json()["resolved"]["sector_cap_pct"] / 100.0
        if rich.get(f"/v1/mandate/{rich.id}").json()["sector_cap_pct"] is None
        else rich.get(f"/v1/mandate/{rich.id}").json()["sector_cap_pct"] / 100.0)

    # the cap is read from the mandate, not hard-coded: lower it below the weight
    _patch_mandate(rich, {"sector_cap_pct": 5.0})
    try:
        c = _alloc(rich)["compliance"]
        assert c["max_allowed"] == pytest.approx(0.05)
        assert c["compliant"] is False
    finally:
        _patch_mandate(rich, {"sector_cap_pct": 100.0})


@pytest.mark.uat("UAT-HLTH-005")
def test_sector_watch_is_honest_when_it_cannot_say_anything(seed, free, rich, api):
    empty = free.get(f"/v1/sector-watch/{free.id}").json()
    assert empty["state"] == "empty" and empty["sector"] is None and empty["move_pct"] is None

    r = rich.get(f"/v1/sector-watch/{rich.id}")  # holds AAPL
    assert r.status_code == 200
    w = r.json()
    assert w["state"] in ("ok", "unavailable")
    if w["state"] == "unavailable":
        assert w["reason"] in ("no_live_quotes", "no_news", "error")
        # never a fabricated 0.0% move
        assert w["move_pct"] is None and w["leader"] is None and w["headline"] is None
    else:
        assert w["sector"] and w["leader"] and w["headline"]["title"]
        assert w["quote_source"] not in ("mock_walk", "unavailable")
        assert w["tickers_considered"] >= 1

    # another user's id is a 404, not a 403: it does not confirm the id exists
    assert free.get(f"/v1/sector-watch/{rich.id}").status_code == 404
    assert api.get(f"/v1/sector-watch/{rich.id}").status_code == 401


@pytest.mark.uat("UAT-HLTH-006")
@pytest.mark.xfail(strict=True, reason=(
    "FINDING: Sector Watch (Floor card 3) is 'unavailable' / no_news for a user whose "
    "only touched ticker is AAPL, because /v1/sim/news/* returns nothing on Alpha "
    "(see UAT-SIM-004). The card never leaves its degraded state."))
def test_sector_watch_resolves_a_headline_for_a_liquid_holding(rich):
    w = rich.get(f"/v1/sector-watch/{rich.id}").json()
    assert w["state"] == "ok", w
    assert w["sector"] == "Technology" and w["leader"] == "AAPL"
    assert w["headline"]["title"]


@pytest.mark.uat("UAT-HLTH-007")
def test_finding_refuses_before_spending_anything(free, rich, api):
    # nothing to measure -> an explicit 409 that names why (not a Finding over nothing)
    r = free.post(f"/v1/portfolio/health/{free.id}/finding")
    assert r.status_code == 409
    d = r.json()["detail"]
    assert d["code"] == "portfolio_health_unavailable" and d["reason"] == "no_holdings"

    # ownership is checked first, and unauthenticated is a 401
    assert free.post(f"/v1/portfolio/health/{rich.id}/finding").status_code == 403
    assert api.post(f"/v1/portfolio/health/{rich.id}/finding").status_code == 401
    assert free.get(f"/v1/portfolio/health/{rich.id}").status_code == 403
    assert api.get(f"/v1/portfolio/health/{rich.id}").status_code == 401
    assert free.get(f"/v1/portfolio/sector-allocation/{rich.id}").status_code == 403

    # the endpoint is rate limited per user (5/min) before it can reach the LLM
    codes = [free.post(f"/v1/portfolio/health/{free.id}/finding").status_code for _ in range(8)]
    assert 429 in codes, codes
    assert set(codes) <= {409, 429}, codes


@pytest.mark.uat("UAT-HLTH-008")
def test_day_trader_outcomes_never_judge_a_user_with_no_history(free, rich):
    r = free.get(f"/v1/portfolio/day-trader-outcomes/{free.id}")
    assert r.status_code == 200 and r.json()["status"] == "not_in_cohort"
    assert free.get(f"/v1/portfolio/day-trader-outcomes/{rich.id}").status_code == 403

    preset = free.get(f"/v1/mandate/{free.id}").json()["day_trader_preset"]["overrides"]
    _patch_mandate(free, preset)
    after = free.get(f"/v1/portfolio/day-trader-outcomes/{free.id}").json()
    assert after["status"] == "too_early", after
    assert not any(k for k in after if k not in ("status", "message")), \
        "a too-early response must carry no numeric comparison"


@pytest.mark.uat("UAT-HLTH-009")
@pytest.mark.llm
def test_finding_generates_once_then_replays_free(rich):
    """The ONLY LLM-spending call in this area: one Finding. The replay must be
    the stored entry (created false, same id) and must not consume budget."""
    before = _health(rich)["gate"]
    r = rich.post(f"/v1/portfolio/health/{rich.id}/finding", timeout=560)
    assert r.status_code == 200, r.text
    f = r.json()
    assert f["created"] is True and f["journal_entry_id"] and f["as_of"]
    assert isinstance(f["sections"], dict) and f["sections"], "a Finding with no sections"
    assert all(isinstance(v, (str, list, dict)) and v for v in f["sections"].values())
    assert f["gate"]["daily_used"] == before["daily_used"] + 1
    assert f["gate"]["trial_findings_used"] == before["trial_findings_used"] + 1

    again = rich.post(f"/v1/portfolio/health/{rich.id}/finding", timeout=60)
    assert again.status_code == 200
    a = again.json()
    assert a["created"] is False
    assert a["journal_entry_id"] == f["journal_entry_id"]
    assert a["sections"] == f["sections"]
    assert a["gate"]["daily_used"] == f["gate"]["daily_used"], "a replay spent budget"

    entries = rich.get(f"/v1/journal/{rich.id}")
    if entries.status_code == 200:
        text = entries.text
        assert f["journal_entry_id"] in text
