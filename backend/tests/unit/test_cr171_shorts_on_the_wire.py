"""CR171 — the short book, as a CLIENT receives it.

`test_cr171_short_selling.py` proves the engine's arithmetic. This file proves
the client can *see* it, which is a separate fact and the one that was missing:
`dd8a4f3f` shipped shorts that `total_value` counts, `portfolio_nav_daily`
records and the margin sweep can force-close — with **no field on
`PortfolioSnapshot` carrying any of it**. A position that moves the user's NAV
and appears nowhere on their screen is CR040's failure in its purest form, and
§7's *"the close is reported, never silent"* was, until this slice, true only of
the container's logs.

Everything here drives the real route. A test that called `_short_out` directly
would assert the serializer's arithmetic while saying nothing about whether that
serializer is reached — the DEF190 shape this lineage has now shipped twice.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.db import get_session
from app.db.models import SimShortPositionRow
from app.schemas.trade import OrderType, Side
from app.services.coach_engine import hydrate_coach_mandate
from app.services.market_data import Quote
from app.services.sim_engine import SimEngine


class _Pinned:
    name = "pinned"

    def __init__(self, prices: dict[str, float]):
        self.prices = {k.upper(): v for k, v in prices.items()}

    def set(self, ticker: str, price: float) -> None:
        self.prices[ticker.upper()] = price

    def quote(self, ticker: str) -> Quote | None:
        return Quote(price=self.prices.get(ticker.upper(), 100.0), source="yfinance")

    def history(self, *a, **k):  # pragma: no cover
        return []

    def news(self, *a, **k):  # pragma: no cover
        return []

    def earnings(self, *a, **k):  # pragma: no cover
        return None


@pytest.fixture(autouse=True)
def _no_borrow_socket(monkeypatch):
    monkeypatch.setattr(
        "app.services.short_borrow_rate._fetch_info", lambda ticker: {},
    )


def _mandate(**over):
    base = {
        "plan": "trader",
        "single_name_cap_pct": 100.0,
        "max_open_risk_pct": 100.0,
        "max_trades_per_day": 100,
        "max_trades_per_week": 500,
        "compliance": {"long_only": False, "halal": False},
    }
    base.update(over)
    return hydrate_coach_mandate(base)


def _api(provider):
    """A live sim router bound to a pinned provider, a real user, their token.

    The engine override is what makes this a *route* test rather than a
    fixture test: without it the route builds its own engine against the real
    market-data stack and the marks stop being ours.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.sim import router as sim_router
    from app.services.auth_service import AuthService
    from app.services.sim_engine import get_sim_engine

    sim = SimEngine(provider=provider)
    app = FastAPI()
    app.include_router(sim_router)
    app.dependency_overrides[get_sim_engine] = lambda: sim
    user, token, _ = AuthService().ensure_anonymous(device_user_id=None)
    client = TestClient(app, raise_server_exceptions=False)
    return client, sim, user, token


def _portfolio(client, user, token) -> dict:
    r = client.get(
        f"/v1/sim/portfolio/{user.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _open_short(sim, user_id, *, ticker="AAPL", qty=10.0, **kw):
    return sim.submit(
        user_id=user_id, ticker=ticker, side=Side.SELL, quantity=qty,
        mandate=_mandate(), order_type=OrderType.MARKET, **kw,
    )


# ── The open leg ──────────────────────────────────────────────────────────


def test_an_open_short_is_on_the_portfolio_a_client_reads():
    provider = _Pinned({"AAPL": 100.0})
    client, sim, user, token = _api(provider)
    sim.ensure_portfolio(user.id)
    result = _open_short(sim, user.id, qty=10)
    assert result.short_action == "short_open", result.compliance.violations

    body = _portfolio(client, user, token)
    assert len(body["shorts"]) == 1, body["shorts"]
    leg = body["shorts"][0]
    assert leg["ticker"] == "AAPL"
    assert leg["quantity"] == pytest.approx(10.0)
    assert leg["entry_price"] == pytest.approx(100.0)
    # Holdings are untouched: the whole point of the separate table (§3).
    assert body["holdings"] == []


def test_the_leg_value_is_the_cash_that_left_plus_the_move_not_quantity_times_mark():
    """§2. `quantity × mark` is the obvious thing to render and it is backwards:
    it GROWS as the position moves against the user. At a mark 10% above entry
    the user is down $100 on 10 shares, and a market-value reading would show
    $1,100 — bigger, and green."""
    provider = _Pinned({"AAPL": 100.0})
    client, sim, user, token = _api(provider)
    sim.ensure_portfolio(user.id)
    _open_short(sim, user.id, qty=10)

    provider.set("AAPL", 110.0)
    leg = _portfolio(client, user, token)["shorts"][0]

    # cash_posted = 0.5 x notional = 500; the move costs 10 x 10 = 100.
    assert leg["cash_posted"] == pytest.approx(500.0)
    assert leg["leg_value"] == pytest.approx(400.0)
    assert leg["unrealised_pnl"] == pytest.approx(-100.0)
    assert leg["leg_value"] != pytest.approx(10 * 110.0)


def test_the_margin_ratio_travels_with_the_threshold_it_is_judged_against():
    """The client must not carry its own 1.30. A second copy of a threshold is
    a second thing to drift (DEF098), and the drift shows up as a position the
    app calls safe on the sweep that closes it."""
    provider = _Pinned({"AAPL": 100.0})
    client, sim, user, token = _api(provider)
    sim.ensure_portfolio(user.id)
    _open_short(sim, user.id, qty=10)

    at_entry = _portfolio(client, user, token)["shorts"][0]
    assert at_entry["maintenance_margin"] == pytest.approx(1.30)
    # collateral 1500, entry leg 1000, cost to close 1000 → 1.50 at entry.
    assert at_entry["margin_ratio"] == pytest.approx(1.50, abs=1e-3)

    provider.set("AAPL", 105.0)
    stressed = _portfolio(client, user, token)["shorts"][0]
    assert stressed["margin_ratio"] < at_entry["margin_ratio"]
    assert stressed["margin_ratio"] > stressed["maintenance_margin"], (
        "105 is comfortably above maintenance — the breach lands near 108.7. "
        "If this flips, the constants moved and the client's warning band "
        "moved with them"
    )


def test_the_borrow_the_position_has_actually_cost_is_readable():
    """§4 charges daily and the charge is invisible in `unrealised_pnl` — it
    comes out of cash. A short whose borrow is never surfaced looks like it
    cost nothing to hold, which is the single most important thing shorting
    teaches."""
    provider = _Pinned({"AAPL": 100.0})
    client, sim, user, token = _api(provider)
    sim.ensure_portfolio(user.id)
    _open_short(sim, user.id, qty=10)

    charged = sim.accrue_short_borrow(user.id, on_date="2026-08-14")
    assert charged > 0

    leg = _portfolio(client, user, token)["shorts"][0]
    assert leg["borrow_accrued_total"] == pytest.approx(charged)
    assert leg["borrow_rate_pct"] > 0
    # Provenance rides along — §4 stores which layer answered precisely so
    # "why 3%?" is answerable, and it is only answerable if it is sent.
    assert leg["borrow_rate_source"] in {"alpaca", "short_interest", "default"}


# ── The close that the user did not ask for ───────────────────────────────


def test_a_margin_closed_short_is_reported_not_merely_logged():
    """§7. Before this field the ONLY record a user could reach was their cash
    balance moving. `logger.warning('sim_short_margin_closed')` informs the
    operator, not the person it happened to."""
    provider = _Pinned({"AAPL": 100.0})
    client, sim, user, token = _api(provider)
    sim.ensure_portfolio(user.id)
    _open_short(sim, user.id, qty=10)

    provider.set("AAPL", 145.0)
    assert sim.force_close_breached_shorts(user.id) == ["AAPL"]

    body = _portfolio(client, user, token)
    assert body["shorts"] == [], "the position is gone from the open book"
    assert len(body["closed_shorts"]) == 1, body["closed_shorts"]
    closed = body["closed_shorts"][0]
    assert closed["close_reason"] == "margin", (
        "the reason is the whole payload — 'closed' alone reads as a bug"
    )
    assert closed["close_price"] == pytest.approx(145.0)
    assert closed["realised_pnl"] == pytest.approx(-450.0)


def test_a_user_closed_cover_is_reported_with_its_own_reason():
    """Same list, different reason. The client distinguishes 'you did this'
    from 'the account did this to you' off `close_reason`, so the two must not
    arrive indistinguishable."""
    provider = _Pinned({"AAPL": 100.0})
    client, sim, user, token = _api(provider)
    sim.ensure_portfolio(user.id)
    _open_short(sim, user.id, qty=10)

    assert sim.cover_short(user_id=user.id, ticker="AAPL") is not None

    closed = _portfolio(client, user, token)["closed_shorts"]
    assert len(closed) == 1
    assert closed[0]["close_reason"] == "user"


def test_the_close_report_is_a_window_not_a_trade_history():
    """It rides on a polled snapshot, so it must stay a small constant. A close
    from three weeks ago belongs in the trade history, not here — and a list
    that grows without bound turns every portfolio poll into a slow one."""
    provider = _Pinned({"AAPL": 100.0})
    client, sim, user, token = _api(provider)
    sim.ensure_portfolio(user.id)
    _open_short(sim, user.id, qty=10)
    sim.cover_short(user_id=user.id, ticker="AAPL")

    assert len(_portfolio(client, user, token)["closed_shorts"]) == 1

    with get_session() as s:
        row = s.query(SimShortPositionRow).filter(
            SimShortPositionRow.user_id == user.id,
        ).one()
        row.closed_at = datetime.now(timezone.utc) - timedelta(days=30)
        s.add(row)

    assert _portfolio(client, user, token)["closed_shorts"] == []


# ── Getting out: a buy against a standing short ───────────────────────────


def test_a_buy_against_a_standing_short_covers_it_rather_than_going_long():
    """Without this the ONLY exits from a training short were the margin call
    and a bracket — `SimEngine.cover_short` existed and no client could reach
    it. That is DEF259's shape ("a position could be opened and never closed")
    on the one position type whose loss is unbounded."""
    provider = _Pinned({"AAPL": 100.0})
    client, sim, user, token = _api(provider)
    sim.ensure_portfolio(user.id)
    _open_short(sim, user.id, qty=10)

    provider.set("AAPL", 90.0)
    result = sim.submit(
        user_id=user.id, ticker="AAPL", side=Side.BUY, quantity=10,
        mandate=_mandate(), order_type=OrderType.MARKET,
    )
    assert result.accepted, result.compliance.violations
    assert result.short_action == "short_cover"
    assert result.short_realised_pnl == pytest.approx(100.0)

    body = _portfolio(client, user, token)
    assert body["shorts"] == []
    assert body["holdings"] == [], (
        "a cover must not leave the user holding a LONG in the same name — "
        "both legs at once is double exposure to the gross rule and a state "
        "def110_backfill was never written to read"
    )
    assert body["closed_shorts"][0]["close_reason"] == "user"


def test_a_partial_cover_is_refused_naming_the_quantity_that_would_work():
    """The mirror of §1's sell-never-crosses-zero. A partial cover blends two
    exit prices into one realised figure — the same attribution problem, from
    the other end."""
    client, sim, user, token = _api(_Pinned({"AAPL": 100.0}))
    sim.ensure_portfolio(user.id)
    _open_short(sim, user.id, qty=10)

    result = sim.submit(
        user_id=user.id, ticker="AAPL", side=Side.BUY, quantity=4,
        mandate=_mandate(), order_type=OrderType.MARKET,
    )
    assert not result.accepted
    sentence = " ".join(result.compliance.violations)
    assert "10" in sentence and "4" in sentence, sentence
    assert len(_portfolio(client, user, token)["shorts"]) == 1


def test_an_ordinary_buy_in_an_unshorted_name_is_completely_unaffected():
    """The cover branch must be invisible to every buy that is not one. This is
    the pin against it quietly capturing the ordinary path."""
    client, sim, user, token = _api(_Pinned({"AAPL": 100.0, "MSFT": 50.0}))
    sim.ensure_portfolio(user.id)
    _open_short(sim, user.id, ticker="AAPL", qty=10)

    result = sim.submit(
        user_id=user.id, ticker="MSFT", side=Side.BUY, quantity=3,
        mandate=_mandate(), order_type=OrderType.MARKET,
    )
    assert result.accepted, result.compliance.violations
    assert result.short_action is None
    assert result.trade is not None

    body = _portfolio(client, user, token)
    assert [h["ticker"] for h in body["holdings"]] == ["MSFT"]
    assert len(body["shorts"]) == 1


# ── The common case, and the shape a client can always rely on ────────────


def test_a_portfolio_that_has_never_shorted_serves_both_lists_empty():
    """Not absent, not null. A client that has to distinguish "missing key" from
    "no shorts" will get it wrong on one of the two backends it must tolerate
    during a staged rollout."""
    client, sim, user, token = _api(_Pinned({"AAPL": 100.0}))
    sim.ensure_portfolio(user.id)

    body = _portfolio(client, user, token)
    assert body["shorts"] == []
    assert body["closed_shorts"] == []


def test_the_snapshot_survives_a_mark_the_ratio_cannot_be_computed_against():
    """`margin_ratio` is `inf` when the cost to close is not positive, and
    `inf` is not JSON — a bare serialization would 500 the whole portfolio
    over one bad quote, taking down holdings, cash and the resting book with
    it. Null, and the client renders no ratio rather than a fabricated one.
    """
    provider = _Pinned({"AAPL": 100.0})
    client, sim, user, token = _api(provider)
    sim.ensure_portfolio(user.id)
    _open_short(sim, user.id, qty=10)

    provider.set("AAPL", 0.0)
    body = _portfolio(client, user, token)
    leg = body["shorts"][0]
    assert leg["margin_ratio"] is None or leg["margin_ratio"] > 0, leg
