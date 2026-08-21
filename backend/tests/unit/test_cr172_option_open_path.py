"""CR172 §10 step 4 — opening a structure, and what must not move when it does.

The load-bearing test in this file is `test_total_value_is_continuous_*`.
CR171's module docstring states the rule for shorts and it is identical here:
opening a position at its own mid must not change `total_value`, because that
number is read by `total_drawdown_pct`, `portfolio_nav_daily`, the TWR chain
and every risk limit. A structure that costs $500 and adds nothing to the
portfolio's value is a $500 loss booked for having traded — silently, in the
NAV series, on every open.

The rest divide into two groups:

  * **the floor is entered, not re-implemented** — a naked call is refused
    here because `check_option_open` refuses it, with the floor's own
    sentence; a long-only mandate stops a sell-to-open the same way.
  * **a refusal never half-writes** — an unaffordable structure leaves no
    leg row, no trade row and no cash movement. A partial position is worse
    than a rejected one: the legs exist, the close path cannot find them, and
    the collateral is stranded.
"""

from __future__ import annotations

import datetime
from uuid import uuid4

import pytest

from app.agents.safety_floor import NAKED_CALL_REFUSAL
from app.db.models import SimOptionLegRow, SimOptionTradeRow
from app.db.session import get_session
from app.services import sim_options
from app.services.coach_engine import hydrate_coach_mandate
from app.services.sim_engine import SimEngine
from app.trading_math.option_strategy import StrategyLeg, strategy_metrics

EXPIRY = datetime.date(2027, 3, 19)


def _mandate(
    *, long_only: bool = False, halal: bool = False, derivatives_allowed: bool = True,
):
    """Derivatives ON by default — §9's gate has its own tests; these ask about
    what happens once it is open. A shut gate would make them pass for the
    wrong reason."""
    return hydrate_coach_mandate({
        "plan": "trader",
        "single_name_cap_pct": 100.0,
        "compliance": {
            "long_only": long_only,
            "halal": halal,
            "derivatives_allowed": derivatives_allowed,
        },
    })


def _leg(right, strike, qty, premium):
    return StrategyLeg(
        right=right, strike=strike, quantity=qty, premium=premium,
        multiplier=100.0, expiry=EXPIRY.isoformat(),
    )


LONG_CALL = (_leg("call", 100.0, 1.0, 5.0),)
BULL_SPREAD = (_leg("call", 100.0, 1.0, 5.0), _leg("call", 110.0, -1.0, 2.0))
CASH_SECURED_PUT = (_leg("put", 90.0, -1.0, 4.5),)
NAKED_CALL = (_leg("call", 100.0, -1.0, 5.0),)
# A CREDIT vertical, and the only structure here that posts collateral across
# more than one leg — the debit spread's long call covers its short, so its
# collateral is 0 and it cannot exercise the attribution at all.
BULL_PUT_SPREAD = (_leg("put", 90.0, 1.0, 1.5), _leg("put", 95.0, -1.0, 3.0))


@pytest.fixture()
def engine():
    return SimEngine()


@pytest.fixture()
def user_id(engine):
    uid = uuid4()
    engine.ensure_portfolio(uid)
    return uid


def _open(engine, user_id, legs, name, mandate=None):
    return engine.open_option_structure(
        user_id,
        underlying="AAPL",
        strategy_name=name,
        legs=legs,
        expiry=EXPIRY,
        mandate=mandate or _mandate(),
    )


def _rows(user_id):
    with get_session() as s:
        legs = s.query(SimOptionLegRow).filter(
            SimOptionLegRow.user_id == user_id
        ).all()
        trades = s.query(SimOptionTradeRow).filter(
            SimOptionTradeRow.user_id == user_id
        ).all()
        return len(legs), len(trades)


# ── the identity ────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("legs", "name"),
    [
        (LONG_CALL, "long_call"),
        (BULL_SPREAD, "bull_call_spread"),
        (CASH_SECURED_PUT, "cash_secured_put"),
    ],
)
def test_total_value_is_continuous_across_the_open(engine, user_id, legs, name):
    """Opening at the structure's own mid must not move the total."""
    before = engine.ensure_portfolio(user_id).total_value()
    result = _open(engine, user_id, legs, name)
    assert result.accepted, result.compliance.violations
    after = engine.ensure_portfolio(user_id).total_value()
    assert round(after, 2) == round(before, 2)


def test_cash_falls_by_the_debit_plus_the_collateral(engine, user_id):
    before = engine.ensure_portfolio(user_id).current_cash
    _open(engine, user_id, CASH_SECURED_PUT, "cash_secured_put")
    metrics = strategy_metrics(CASH_SECURED_PUT)
    expected = sim_options.cash_required_for(
        metrics.net_cost, metrics.collateral_required,
    )
    after = engine.ensure_portfolio(user_id).current_cash
    assert round(before - after, 2) == expected
    assert expected > 0, "a cash-secured put ties up cash even though it pays"


def test_a_credit_structure_still_costs_cash_but_less_than_its_collateral():
    metrics = strategy_metrics(CASH_SECURED_PUT)
    needed = sim_options.cash_required_for(
        metrics.net_cost, metrics.collateral_required,
    )
    assert needed == round(metrics.collateral_required + metrics.net_cost, 2)
    assert needed < metrics.collateral_required, "the premium received is real"


# ── the position that lands ─────────────────────────────────────────────────

def test_the_legs_land_with_their_signs_and_units_intact(engine, user_id):
    _open(engine, user_id, BULL_SPREAD, "bull_call_spread")
    portfolio = engine.ensure_portfolio(user_id)
    assert len(portfolio.options) == 2
    by_strike = {o.strike: o for o in portfolio.options}
    assert by_strike[100.0].quantity == 1.0
    assert by_strike[110.0].quantity == -1.0
    assert by_strike[100.0].avg_premium == 5.0, "per SHARE, not per contract"
    assert all(o.strategy_name == "bull_call_spread" for o in portfolio.options)
    assert len({o.strategy_id for o in portfolio.options}) == 1


def test_every_leg_carries_an_occ_symbol(engine, user_id):
    from app.services.option_instruments import parse_occ_symbol

    _open(engine, user_id, BULL_SPREAD, "bull_call_spread")
    for leg in engine.ensure_portfolio(user_id).options:
        parsed = parse_occ_symbol(leg.occ_symbol)
        assert parsed is not None
        assert parsed.underlying == "AAPL" and parsed.expiry == EXPIRY


def test_the_structure_row_records_what_the_user_consented_to(engine, user_id):
    verdict = uuid4()
    engine.open_option_structure(
        user_id, underlying="AAPL", strategy_name="long_call", legs=LONG_CALL,
        expiry=EXPIRY, mandate=_mandate(), verdict_ref=verdict,
    )
    with get_session() as s:
        row = s.query(SimOptionTradeRow).filter(
            SimOptionTradeRow.user_id == user_id
        ).one()
        assert row.verdict_ref == verdict
        assert float(row.net_cost_at_open) == strategy_metrics(LONG_CALL).net_cost
        assert row.status == "open"


def test_no_sim_trades_row_is_written(engine, user_id):
    """The phantom-share detector subtracts Σ SELL quantity over trade rows."""
    from app.db.models import SimTradeRow

    _open(engine, user_id, BULL_SPREAD, "bull_call_spread")
    with get_session() as s:
        assert s.query(SimTradeRow).filter(
            SimTradeRow.user_id == user_id
        ).count() == 0


def test_no_holding_row_is_written(engine, user_id):
    """§3's separate table is what keeps `SimHoldingRow.quantity` non-negative."""
    _open(engine, user_id, CASH_SECURED_PUT, "cash_secured_put")
    assert engine.ensure_portfolio(user_id).holdings == []


# ── collateral attribution ──────────────────────────────────────────────────

def test_leg_collateral_sums_to_the_structure_collateral(engine, user_id):
    _open(engine, user_id, CASH_SECURED_PUT, "cash_secured_put")
    with get_session() as s:
        legs = s.query(SimOptionLegRow).filter(
            SimOptionLegRow.user_id == user_id
        ).all()
        trade = s.query(SimOptionTradeRow).filter(
            SimOptionTradeRow.user_id == user_id
        ).one()
        assert round(sum(float(row.collateral_posted) for row in legs), 2) == round(
            float(trade.collateral_posted), 2,
        )


def test_a_long_leg_posts_no_collateral(engine, user_id):
    """On a credit vertical the SHORT leg carries all of it, not half of it.

    An even split would leave $175 on the long put and release it at expiry
    from a leg that pre-funded nothing, while the assigned short leg releases
    $175 against a $9,500 obligation.
    """
    _open(engine, user_id, BULL_PUT_SPREAD, "bull_put_spread")
    with get_session() as s:
        legs = {
            float(r.strike): float(r.collateral_posted)
            for r in s.query(SimOptionLegRow).filter(
                SimOptionLegRow.user_id == user_id
            ).all()
        }
    assert legs[90.0] == 0.0, "the long leg pre-funds nothing"
    assert legs[95.0] == 350.0, "the short leg carries the whole posting"


def test_allocation_never_loses_a_cent_to_rounding():
    legs = (
        _leg("put", 90.0, -1.0, 4.5),
        _leg("put", 85.0, -2.0, 3.0),
        _leg("put", 80.0, 3.0, 1.5),
    )
    for collateral in (0.01, 33.33, 100.0, 9_999.99):
        parts = sim_options.allocate_collateral(legs, collateral)
        assert round(sum(parts), 2) == round(collateral, 2)


# ── the floor, entered not re-implemented ───────────────────────────────────

def test_a_naked_call_is_refused_with_the_floors_own_sentence(engine, user_id):
    result = _open(engine, user_id, NAKED_CALL, "naked_call")
    assert result.accepted is False
    assert NAKED_CALL_REFUSAL in result.compliance.violations
    assert _rows(user_id) == (0, 0)


def test_long_only_refuses_the_sell_to_open(engine, user_id):
    result = _open(
        engine, user_id, CASH_SECURED_PUT, "cash_secured_put",
        mandate=_mandate(long_only=True),
    )
    assert result.accepted is False
    assert any("long-only" in v for v in result.compliance.violations)
    assert _rows(user_id) == (0, 0)


def test_a_refused_open_moves_no_cash(engine, user_id):
    before = engine.ensure_portfolio(user_id).current_cash
    _open(engine, user_id, NAKED_CALL, "naked_call")
    assert engine.ensure_portfolio(user_id).current_cash == before


def test_the_halal_advisory_travels_on_an_accepted_open(engine, user_id):
    result = _open(
        engine, user_id, CASH_SECURED_PUT, "cash_secured_put",
        mandate=_mandate(halal=True),
    )
    assert result.accepted is True
    assert any("gharar" in a for a in result.compliance.advisories)


# ── affordability ───────────────────────────────────────────────────────────

def test_an_unaffordable_structure_is_refused_and_writes_nothing(engine, user_id):
    expensive = (_leg("put", 500.0, -100.0, 4.5),)   # $5m of collateral
    before = engine.ensure_portfolio(user_id).current_cash
    result = _open(engine, user_id, expensive, "cash_secured_put")
    assert result.accepted is False
    assert any("holds" in v for v in result.compliance.violations)
    assert _rows(user_id) == (0, 0)
    assert engine.ensure_portfolio(user_id).current_cash == before


def test_an_uncostable_structure_is_refused(engine, user_id):
    mixed_expiry = (
        _leg("call", 100.0, 1.0, 5.0),
        StrategyLeg(
            right="call", strike=110.0, quantity=-1.0, premium=2.0,
            multiplier=100.0, expiry="2027-06-18",
        ),
    )
    result = _open(engine, user_id, mixed_expiry, "bull_call_spread")
    assert result.accepted is False
    assert _rows(user_id) == (0, 0)


# ── lane separation ─────────────────────────────────────────────────────────

def test_a_game_portfolio_never_carries_option_legs(engine):
    """§11 wants `games_scoring_pass` provably untouched by options.

    The separation is asserted where it is enforced — in the READER. A leg row
    is written directly against the game portfolio here, which no production
    path does today, precisely so the test still fails if one ever starts:
    proving "the game portfolio has no legs because nothing writes them" proves
    nothing about the day something does.
    """
    uid = uuid4()
    run = uuid4()
    training = engine.ensure_portfolio(uid)
    game = engine.ensure_portfolio(uid, kind="game", run_id=run)
    _open(engine, uid, LONG_CALL, "long_call")
    with get_session() as s:
        s.add(SimOptionLegRow(
            id=uuid4(), user_id=uid, portfolio_id=game.id,
            occ_symbol="AAPL  270319C00100000", underlying="AAPL", right="call",
            strike=100.0, expiry=EXPIRY, quantity=1.0, avg_premium=5.0,
            multiplier=100.0, collateral_posted=0.0, strategy_id=uuid4(),
            strategy_name="long_call", state="open",
        ))
        s.flush()
    assert engine.ensure_portfolio(uid, kind="game", run_id=run).options == []
    assert len(engine.ensure_portfolio(uid).options) == 1
    assert training.id != game.id
