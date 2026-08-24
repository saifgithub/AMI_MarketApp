"""CR172 §12 — what the Portfolio screen is allowed to be told about an option.

This file exists because of a gap, not a bug: the backend `Portfolio` schema
has carried `options` since §3 and `sim_engine` has populated it, but no client
read it. So a user could consent to a structure AMI had priced and then find no
trace of it on their own portfolio. The card that closes that is only as
truthful as the payload behind it, and two properties of that payload are
load-bearing.

**`days_to_expiry` is computed here, not on the device.** `expiry` is a bare
date with no timezone. A phone in UTC+8 and a phone in UTC-5 reading the same
row would disagree about the day count — on the day that disagreement matters
most, the last one. `CostedStructure.days_to_expiry` is already server-sent for
exactly this reason; an open leg has no business being weaker than the proposal
it came from.

**It is signed, and that is deliberate.** `option_strategist` clamps its own
day count with `max(0, ...)` and is right to: you cannot propose a structure off
an expired chain, so negative is unreachable there. Here it is reachable and it
means something specific — a leg still `state="open"` past its expiry is one
settlement has not processed. Clamping would render that identically to
"expires today", which is the single reading that would stop a user asking why
it is still on their book.
"""

from __future__ import annotations

import datetime
from uuid import uuid4

import pytest

from app.db.models import SimOptionLegRow
from app.db.session import get_session
from app.services.coach_engine import hydrate_coach_mandate
from app.services.sim_engine import SimEngine
from app.services.sim_options import open_legs_for_portfolio
from app.trading_math.option_strategy import StrategyLeg

EXPIRY = datetime.date(2027, 3, 19)


def _mandate():
    return hydrate_coach_mandate({
        "plan": "trader",
        "single_name_cap_pct": 100.0,
        "compliance": {
            "long_only": False,
            "halal": False,
            "derivatives_allowed": True,
        },
    })


def _leg(right, strike, qty, premium, expiry=EXPIRY):
    return StrategyLeg(
        right=right, strike=strike, quantity=qty, premium=premium,
        multiplier=100.0, expiry=expiry.isoformat(),
    )


BULL_SPREAD = (_leg("call", 100.0, 1.0, 5.0), _leg("call", 110.0, -1.0, 2.0))


@pytest.fixture()
def engine():
    return SimEngine()


@pytest.fixture()
def user_id(engine):
    uid = uuid4()
    engine.ensure_portfolio(uid)
    return uid


def _open(engine, user_id, legs=BULL_SPREAD, name="bull_call_spread",
          expiry=EXPIRY):
    r = engine.open_option_structure(
        user_id, underlying="AAPL", strategy_name=name, legs=legs,
        expiry=expiry, mandate=_mandate(),
    )
    assert r.accepted, r.compliance.violations
    return r


def _portfolio_id(user_id):
    with get_session() as s:
        row = s.query(SimOptionLegRow).filter(
            SimOptionLegRow.user_id == user_id
        ).first()
        return row.portfolio_id


def test_days_to_expiry_is_stamped_by_the_server(engine, user_id):
    _open(engine, user_id)
    expected = (EXPIRY - datetime.datetime.now(datetime.timezone.utc).date()).days
    with get_session() as s:
        legs = open_legs_for_portfolio(s, _portfolio_id(user_id))
    assert legs, "the spread should have produced legs"
    assert all(l.days_to_expiry == expected for l in legs)


def test_the_client_is_not_left_to_compute_it(engine, user_id):
    """The field is REQUIRED on the schema, so a second constructor that
    forgets it fails loudly instead of shipping a plausible zero."""
    from app.schemas.trade import OptionLeg
    assert OptionLeg.model_fields["days_to_expiry"].is_required()


def test_an_expired_but_open_leg_reports_a_NEGATIVE_count(engine, user_id):
    """Not clamped at zero.

    A leg past expiry and still open is a settlement backlog, not a same-day
    expiry. `max(0, ...)` here would make the two indistinguishable on the
    card, and the user would have no reason to ask about the one that needs
    asking about.
    """
    _open(engine, user_id)
    pid = _portfolio_id(user_id)
    past = datetime.datetime.now(datetime.timezone.utc).date() - datetime.timedelta(days=3)
    with get_session() as s:
        for row in s.query(SimOptionLegRow).filter(
            SimOptionLegRow.portfolio_id == pid
        ).all():
            row.expiry = past
        s.commit()
    with get_session() as s:
        legs = open_legs_for_portfolio(s, pid)
    assert legs
    assert all(l.days_to_expiry == -3 for l in legs), (
        [l.days_to_expiry for l in legs]
    )


def test_the_portfolio_payload_carries_the_legs_the_card_groups_by(
    engine, user_id,
):
    """The card groups by `strategy_id`, so the payload must actually carry a
    shared one per structure — otherwise a two-leg spread renders as two loose
    positions the user never agreed to."""
    _open(engine, user_id)
    p = engine.ensure_portfolio(user_id)
    assert len(p.options) == 2
    assert len({l.strategy_id for l in p.options}) == 1
    assert {l.strategy_name for l in p.options} == {"bull_call_spread"}
    # Signed contracts survive to the wire: the short leg must stay negative,
    # or the card cannot tell LONG from SHORT.
    assert sorted(l.quantity for l in p.options) == [-1.0, 1.0]
