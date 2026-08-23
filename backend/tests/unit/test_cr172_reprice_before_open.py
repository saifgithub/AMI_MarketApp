"""CR172 — `POST /v1/sim/options/reprice`, the step between the yes and the fill.

Saiful's ruling on the consent flow (2026-08-23): *the verdict carries the full
structure the Room priced, and on Accept the app re-prices live and shows what
moved before opening.* This file guards the server half of that.

**What is actually at stake.** `/open` already re-prices — it has to, it is the
surface that moves cash — but it re-prices and fills in one motion, so without
this route the user never sees the number that charged them until after it
charged them. That is DEF305's shape (a position moved off a price nobody
checked) transplanted onto the opening side, and it bites harder on options
than on shares: a 45-day option's premium can move a double-digit percentage
while the underlying barely twitches, so a fill at the proposal's figure is a
materially different trade than the one displayed.

**The tests that would catch a real regression, and what each is really asking:**

* `test_the_premium_shown_is_never_the_one_the_client_sent` — the whole fence.
  `/reprice` accepts `premium_then` so the SERVER can compute the drift rather
  than the client subtracting two numbers, and a route that echoed that figure
  back as the current price would turn a display field into a price feed.
* `test_reprice_and_open_agree_on_the_same_chain` — the two routes share
  `_price_legs` and this proves it holds rather than asserting it in a comment.
  If they diverged, the figure the user consented to and the figure that charged
  would differ with nothing to attribute the gap to.
* `test_an_unknown_baseline_reports_no_change_rather_than_zero` — DEF059's shape
  on the drift line. A zero delta and an unknown delta render identically to a
  reader, and only one of them means the price held.
* `test_a_leg_that_cannot_be_transacted_refuses_the_whole_structure` — a
  structure priced without one of its legs has a net cost that is simply wrong,
  so a partial answer must not be cheaper to produce than a refusal.
* `test_reprice_writes_nothing` — it is a question, not a transaction.
"""

from __future__ import annotations

import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.options import router as options_router
from app.services.auth_service import AuthService
from app.services.market_data import (
    OptionChain,
    OptionQuote,
    Quote,
    set_market_data_provider,
)

EXPIRY = datetime.date.today() + datetime.timedelta(days=45)
SPOT = 100.0
_PERMITS = {"plan": "trader", "compliance": {"derivatives_allowed": True}}


def _quote(strike, bid, ask, iv=0.30):
    return OptionQuote(
        strike=strike, bid=bid, ask=ask, last=None, volume=50,
        open_interest=500, implied_vol=iv,
    )


class _ChainProvider:
    """A liquid board around $100 whose premiums can be shifted mid-test.

    `bump` moves every premium by a fixed amount, which is how a "the market
    moved while the user was reading" case is produced without waiting for one.
    """

    source = "test_chain"

    def __init__(self):
        self.bump = 0.0
        self.dead_strike: float | None = None

    def quote(self, ticker: str):
        if ticker.upper() == "^IRX":
            return Quote(price=4.2, source="yfinance", change_pct=0.0)
        return Quote(price=SPOT, source="yfinance", change_pct=0.0)

    def earnings(self, ticker: str):
        return None

    def expiries(self, underlying: str):
        return [EXPIRY]

    def option_chain(self, underlying: str, expiry: datetime.date):
        if expiry != EXPIRY:
            return None

        def side(intrinsic):
            out = []
            for k in (90.0, 95.0, 100.0, 105.0, 110.0):
                if self.dead_strike is not None and k == self.dead_strike:
                    # bid/ask crossed to zero: quoted, but not transactable.
                    out.append(_quote(k, 0.0, 0.0))
                    continue
                base = max(0.5, intrinsic(k)) + 4.0 + self.bump
                out.append(_quote(k, round(base, 2), round(base + 0.4, 2)))
            return tuple(out)

        return OptionChain(
            underlying=underlying.upper(), expiry=expiry,
            calls=side(lambda k: 105 - k),
            puts=side(lambda k: k - 95),
            source="yfinance",
        )


@pytest.fixture
def provider():
    p = _ChainProvider()
    set_market_data_provider(p)
    yield p
    set_market_data_provider(None)


@pytest.fixture
def client(provider) -> TestClient:
    app = FastAPI()
    app.include_router(options_router)
    return TestClient(app, raise_server_exceptions=True)


def _user():
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, {"Authorization": f"Bearer {token}"}


def _reprice(client, headers, user_id, legs, **over):
    body = {
        "user_id": str(user_id), "ticker": "AAPL",
        "strategy_name": "long_call", "expiry": EXPIRY.isoformat(),
        "legs": legs, "mandate": _PERMITS,
    }
    body.update(over)
    return client.post("/v1/sim/options/reprice", json=body, headers=headers)


_LONG_CALL = [{"right": "call", "strike": 105.0, "quantity": 1.0}]


def _derivatives_mandate():
    """A hydrated `Mandate` permitting derivatives.

    `Mandate.model_validate(_PERMITS)` does NOT work — the model has ten
    required fields and the route builds it through `resolve_mandate`. The
    hydrator is the same one the Room's own tests use, so the floor sees the
    shape it sees in production.
    """
    from app.services.coach_engine import hydrate_coach_mandate

    return hydrate_coach_mandate({
        "plan": "trader",
        "risk_score": 3,
        "compliance": {"derivatives_allowed": True},
    })


def test_reprice_returns_the_structure_costed_now(client):
    user_id, headers = _user()
    r = _reprice(client, headers, user_id, _LONG_CALL)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["repriced"] is True
    s = body["structure"]
    assert s["strategy_name"] == "long_call"
    assert s["legs"][0]["premium"] > 0
    assert s["metrics"]["net_cost"] > 0
    # The stamps that make a later drift comparison possible at all.
    assert s["spot"] == pytest.approx(SPOT)
    assert s["priced_at"] is not None
    # And the stamp carries an OFFSET. `app.core.time.now_utc` returns naive
    # UTC by design, and a naive string is read by Dart's `DateTime.tryParse`
    # as DEVICE-LOCAL: on a UTC+8 phone the age of the price would be wrong by
    # eight hours, in the direction that makes a stale price look fresh. The
    # `CostedStructure.priced_at` validator is what stops that, and this is the
    # assertion that notices if it is removed.
    parsed = datetime.datetime.fromisoformat(s["priced_at"])
    assert parsed.tzinfo is not None, s["priced_at"]


def test_the_premium_shown_is_never_the_one_the_client_sent(client):
    """`premium_then` is a display field, not a price feed.

    A route that echoed it would let a client set the number it is about to be
    charged against — and, more quietly, would make the drift always read zero,
    which is the reassuring answer.
    """
    user_id, headers = _user()
    lied = [{**_LONG_CALL[0], "premium_then": 0.01}]
    r = _reprice(client, headers, user_id, lied)
    body = r.json()
    assert body["structure"]["legs"][0]["premium"] > 1.0
    # The lie survives only where it belongs: as the baseline of the drift.
    leg = body["drift"]["legs"][0]
    assert leg["premium_then"] == 0.01
    assert leg["premium_now"] > 1.0
    assert leg["change"] == pytest.approx(leg["premium_now"] - 0.01, abs=1e-6)


def test_a_move_in_the_chain_shows_up_as_drift(client, provider):
    user_id, headers = _user()
    first = _reprice(client, headers, user_id, _LONG_CALL).json()
    shown = first["structure"]["legs"][0]["premium"]

    provider.bump = 1.25  # the market moved while the user was reading

    second = _reprice(
        client, headers, user_id,
        [{**_LONG_CALL[0], "premium_then": shown}],
        spot_then=SPOT,
    ).json()
    drift = second["drift"]
    assert drift["net_cost_then"] == pytest.approx(shown * 100.0, abs=0.01)
    assert drift["net_cost_change"] == pytest.approx(125.0, abs=1.0)
    assert drift["net_cost_change_pct"] is not None
    assert drift["max_loss_then"] is not None
    assert drift["max_loss_now"] is not None


def test_an_unknown_baseline_reports_no_change_rather_than_zero(client):
    """DEF059 on the drift line.

    No `premium_then` means nobody knows what the user was shown. `0.0` would
    render as *"nothing moved"* — a confident claim about a comparison that was
    never made — so every derived field stays null and the client suppresses the
    panel rather than drawing a row of reassuring zeroes.
    """
    user_id, headers = _user()
    body = _reprice(client, headers, user_id, _LONG_CALL).json()
    drift = body["drift"]
    assert drift["net_cost_then"] is None
    assert drift["net_cost_change"] is None
    assert drift["net_cost_change_pct"] is None
    assert drift["max_loss_then"] is None
    assert drift["spot_then"] is None
    assert drift["spot_change"] is None
    assert drift["aged_seconds"] is None
    # The one thing that IS known is still stated.
    assert drift["net_cost_now"] > 0
    assert drift["spot_now"] == pytest.approx(SPOT)


def test_the_age_of_the_price_is_reported_when_the_client_knows_it(client):
    user_id, headers = _user()
    then = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        minutes=4
    )
    body = _reprice(
        client, headers, user_id, _LONG_CALL,
        priced_at_then=then.isoformat(),
    ).json()
    assert body["drift"]["aged_seconds"] == pytest.approx(240.0, abs=10.0)


def test_a_leg_that_cannot_be_transacted_refuses_the_whole_structure(
    client, provider,
):
    user_id, headers = _user()
    provider.dead_strike = 105.0
    body = _reprice(client, headers, user_id, _LONG_CALL).json()
    assert body["repriced"] is False
    assert body["structure"] is None
    assert body["compliance"]["passed"] is False
    # A refusal always says something (CR040): an error state is never an empty
    # state, and a blank panel teaches the user that refusals are noise.
    assert body["compliance"]["not_evaluated"]


def test_reprice_and_open_agree_on_the_same_chain(client):
    """The two routes share one pricer, and this is the proof.

    If they ever diverged, the figure the user consented to and the figure that
    charged would differ, with nothing in either response to attribute the gap
    to.
    """
    user_id, headers = _user()
    repriced = _reprice(client, headers, user_id, _LONG_CALL).json()
    opened = client.post(
        "/v1/sim/options/open",
        json={
            "user_id": str(user_id), "ticker": "AAPL",
            "strategy_name": "long_call", "expiry": EXPIRY.isoformat(),
            "legs": _LONG_CALL, "mandate": _PERMITS,
        },
        headers=headers,
    ).json()
    assert opened["accepted"] is True
    assert opened["legs"][0]["premium"] == pytest.approx(
        repriced["structure"]["legs"][0]["premium"]
    )
    assert opened["net_cost"] == pytest.approx(
        repriced["structure"]["metrics"]["net_cost"]
    )


def test_reprice_writes_nothing(client):
    """It is a question. A question that opened a position would be the worst
    possible version of this feature."""
    from app.db import get_session
    from app.db.models import SimOptionLegRow

    user_id, headers = _user()
    _reprice(client, headers, user_id, _LONG_CALL)
    with get_session() as s:
        assert s.query(SimOptionLegRow).count() == 0


def test_reprice_is_owner_only(client):
    user_id, _ = _user()
    _, other_headers = _user()
    r = _reprice(client, other_headers, user_id, _LONG_CALL)
    assert r.status_code == 403


def test_a_naive_stamp_is_forced_onto_the_wire_as_utc():
    """The validator that stops a stale price from looking fresh on a phone.

    This is NOT hypothetical and NOT covered by the route tests above: those
    stamp with `datetime.now(timezone.utc)` and are aware already. The **Room
    verdict** path is the exposed one — `room_runner` stamps
    `ctx.option_priced_at` with `app.core.time.now_utc`, which returns *naive*
    UTC by deliberate design, so the structure attached to a verdict arrives
    here without an offset.

    Serialised naive, `priced_at` reads `2026-08-23T02:14:07`. Dart's
    `DateTime.tryParse` treats a string with no offset as **device-local** and
    the client then calls `.toUtc()`: on a UTC+8 phone the price the user is
    looking at would be reported eight hours younger than it is — the direction
    that makes a stale price look fresh, which is the one direction that
    matters.

    Fixing it at the field rather than at the stampers is the point. Two
    producers stamp this today and a third will; a convention every one of them
    must remember is one that one of them will not.
    """
    from app.schemas.options import CostedStructure, MetricsOut, ComplianceOut
    from app.core.time import now_utc

    naive = now_utc()
    assert naive.tzinfo is None, "premise: now_utc is naive by design"

    s = CostedStructure(
        strategy_name="long_call", contracts=1, expiry=EXPIRY.isoformat(),
        days_to_expiry=45, underlying="AAPL", legs=[],
        metrics=MetricsOut(
            net_cost=100.0, max_loss=100.0, max_gain=None,
            unbounded_loss=False, unbounded_gain=True, break_evens=[],
            collateral_required=None, has_uncovered_short_call=False,
            shares_locked=0.0, covered_by_shares=False,
        ),
        compliance=ComplianceOut(passed=True),
        priced_at=naive,
    )
    assert s.priced_at.tzinfo is not None
    assert "+00:00" in s.model_dump_json() or "Z" in s.model_dump_json()
    # And the instant is preserved, not shifted: a validator that "fixed" the
    # offset by moving the clock would be worse than the bug it replaces.
    assert s.priced_at.replace(tzinfo=None) == naive


def test_cost_existing_structure_ignores_the_premium_it_was_handed(provider):
    """The fence inside the costing function, driven past the route.

    `/reprice` prices its legs through `_price_legs` before this function ever
    sees them, so a route-level test cannot reach this branch — a mutation that
    made `cost_existing_structure` trust its caller passed all nine of the
    tests above. That is the shape DEF190 names: asserting on the layer that
    happens to be in front of the fence rather than on the fence.

    So this drives the function directly with a leg carrying an absurd premium
    and asserts the chain's mid won.
    """
    from app.services.option_chain import get_enriched_chain
    from app.services.option_strategist import cost_existing_structure
    from app.trading_math.option_strategy import StrategyLeg

    chain = get_enriched_chain("AAPL", EXPIRY)
    assert chain is not None

    lied = StrategyLeg(
        right="call", strike=105.0, quantity=1.0,
        premium=0.01,  # a long call for a cent; the chain says several dollars
        multiplier=100.0, expiry=EXPIRY.isoformat(),
    )
    candidate = cost_existing_structure(
        chain,
        underlying="AAPL",
        strategy_name="long_call",
        legs=[lied],
        mandate=_derivatives_mandate(),
        days_to_expiry=45,
    )
    assert candidate is not None
    assert candidate.legs[0].premium > 1.0, "the caller's premium was honoured"
    assert candidate.metrics.net_cost > 100.0


def test_cost_existing_structure_refuses_a_leg_the_chain_cannot_price(provider):
    """A strike that is not on the board yields no structure at all.

    Not a structure missing a leg, and not one costed off the legs that did
    price: either would report a net cost that is simply wrong, and a wrong
    total is worse than a refusal because it is actionable.
    """
    from app.services.option_chain import get_enriched_chain
    from app.services.option_strategist import cost_existing_structure
    from app.trading_math.option_strategy import StrategyLeg

    chain = get_enriched_chain("AAPL", EXPIRY)
    off_board = StrategyLeg(
        right="call", strike=137.5, quantity=1.0, premium=2.0,
        multiplier=100.0, expiry=EXPIRY.isoformat(),
    )
    assert cost_existing_structure(
        chain, underlying="AAPL", strategy_name="long_call",
        legs=[off_board], mandate=_derivatives_mandate(),
        days_to_expiry=45,
    ) is None


def test_one_verdict_opens_one_structure(client):
    """The second tap on a verdict that already has a position open.

    Not hypothetical, and the reason it is a SERVER check: the equity card
    suppresses its Buy button by looking for a trade carrying this
    `verdict_ref`, but option structures live in their own tables and no route
    lists them, so the board cannot run that check. A user who opens a
    structure, leaves the Room and comes back sees the consent CTA again.

    Scoped to open structures on purpose — a closed one is a finished trade and
    re-entering it is the user's call, not this guard's.
    """
    import uuid

    user_id, headers = _user()
    verdict = str(uuid.uuid4())
    body = {
        "user_id": str(user_id), "ticker": "AAPL",
        "strategy_name": "long_call", "expiry": EXPIRY.isoformat(),
        "legs": _LONG_CALL, "mandate": _PERMITS, "verdict_ref": verdict,
    }
    first = client.post("/v1/sim/options/open", json=body, headers=headers).json()
    assert first["accepted"] is True

    second = client.post("/v1/sim/options/open", json=body, headers=headers).json()
    assert second["accepted"] is False
    assert second["compliance"]["violations"], second
    # And it says nothing was charged — the fact the user needs first.
    assert "nothing was charged" in second["compliance"]["violations"][0].lower()


def test_a_verdictless_open_is_not_deduplicated(client):
    """No `verdict_ref` means nothing to deduplicate against.

    A user opening the same structure twice from the proposal surface is doing
    something legitimate — sizing up. The guard above keys on the verdict, so
    it must not fire here; a guard that blocks a normal action is one the user
    learns to work around.
    """
    user_id, headers = _user()
    body = {
        "user_id": str(user_id), "ticker": "AAPL",
        "strategy_name": "long_call", "expiry": EXPIRY.isoformat(),
        "legs": _LONG_CALL, "mandate": _PERMITS,
    }
    assert client.post(
        "/v1/sim/options/open", json=body, headers=headers,
    ).json()["accepted"] is True
    assert client.post(
        "/v1/sim/options/open", json=body, headers=headers,
    ).json()["accepted"] is True
