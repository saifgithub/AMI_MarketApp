"""CR205 — per-`occ_symbol` option lots, and the basis transfer on exercise.

**One of this CR's two premises turned out to be already satisfied, and that
is recorded here rather than quietly dropped.** The row said an exercised
call's shares *"appear with a cost basis that ignores the premium paid to
acquire them"*. They do not: `option_lifecycle.settlement_effect` computes
`basis_price = strike + sign x avg_premium` and `sim_engine` writes the equity
row at exactly that. `test_cr172_option_lifecycle` already pinned it on the
HOLDING (`avg_cost == 104.0`); what was never pinned is the same fact on the
**lot**, which is what a user actually reads on the holding-detail screen and
what CR205's acceptance asks for. That test is here.

The real gap was the other premise: `cost_basis_lots` had zero `occ_symbol`
awareness, so an option structure contributed nothing to lot history at all.

**Why option lots are not FIFO.** FIFO matches a sell against earlier buys of
a fungible thing. Option legs in this schema are not accumulated into a
running position: each leg row IS one position, opened once and closed once,
carrying its own `state` / `realised_pnl`. Running FIFO over them would invent
a queue the ledger does not have, and it would disagree with the leg's own
recorded `realised_pnl` the moment two legs on one `occ_symbol` overlapped.
"""

from __future__ import annotations

import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.cost_basis_lots import (
    compute_option_lots,
    option_lots_by_symbol,
)

_NOW = datetime.datetime(2026, 8, 1, tzinfo=datetime.timezone.utc)
_EXP = datetime.date(2026, 12, 18)


def _leg(occ="AAPL261218C00195000", qty=1.0, premium=9.10, state="open",
         realised=None, mult=100.0, opened=_NOW, right="call", strike=195.0,
         close_reason=None):
    return SimpleNamespace(
        occ_symbol=occ, underlying="AAPL", right=right, strike=strike,
        expiry=_EXP, quantity=qty, avg_premium=premium, multiplier=mult,
        opened_at=opened, state=state, realised_pnl=realised,
        close_reason=close_reason,
    )


# ── Units: an option lot is not an equity lot ────────────────────────────


def test_the_cost_basis_is_premium_times_multiplier_times_contracts():
    """$9.10 per share x 100 x 1 contract = $910. Reporting 9.10 as the lot's
    cost would understate it by 100x."""
    lot = compute_option_lots([_leg()])[0]
    assert lot.premium_per_share == 9.10
    assert lot.cost_basis_total == 910.0


def test_a_short_leg_keeps_its_sign_in_both_quantity_and_basis():
    """A credit received is negative dollars paid. Dropping the sign would
    make a written call indistinguishable from a bought one."""
    lot = compute_option_lots([_leg(qty=-2.0, premium=3.0)])[0]
    assert lot.quantity == -2.0
    assert lot.cost_basis_total == -600.0


def test_summing_a_structures_lots_gives_its_net_debit():
    """The same figure `option_strategy` prices — one rule, not two. A bull
    call spread: long 195 at 9.10, short 205 at 4.10, net debit $500."""
    lots = compute_option_lots([
        _leg(occ="A", qty=1.0, premium=9.10),
        _leg(occ="B", qty=-1.0, premium=4.10),
    ])
    assert round(sum(lot.cost_basis_total for lot in lots), 2) == 500.0


def test_a_non_standard_multiplier_is_honoured():
    lot = compute_option_lots([_leg(premium=2.0, mult=10.0)])[0]
    assert lot.cost_basis_total == 20.0


# ── Open vs closed ───────────────────────────────────────────────────────


def test_an_open_leg_is_open_and_a_settled_one_is_not():
    open_lot = compute_option_lots([_leg(state="open")])[0]
    closed_lot = compute_option_lots([_leg(state="closed", realised=120.0)])[0]

    assert open_lot.is_open and open_lot.quantity_open == 1.0
    assert open_lot.quantity_closed == 0.0
    assert not closed_lot.is_open and closed_lot.quantity_closed == 1.0
    assert closed_lot.realised_pnl == 120.0


def test_a_closed_leg_carries_why_it_closed():
    lot = compute_option_lots([
        _leg(state="closed", realised=0.0, close_reason="expired"),
    ])[0]
    assert lot.close_reason == "expired"


def test_lots_are_ordered_oldest_first():
    later = _NOW + datetime.timedelta(days=3)
    lots = compute_option_lots([_leg(occ="LATER", opened=later), _leg(occ="EARLY")])
    assert [lot.occ_symbol for lot in lots] == ["EARLY", "LATER"]


def test_a_malformed_leg_is_dropped_loudly_not_crashed_on():
    bad = _leg()
    bad.quantity = "not-a-number"
    lots = compute_option_lots([bad, _leg(occ="GOOD")])
    assert [lot.occ_symbol for lot in lots] == ["GOOD"]


# ── The per-symbol view ──────────────────────────────────────────────────


def test_two_legs_on_one_contract_are_two_lots_on_one_key():
    """Opened, closed, reopened — exactly the history the holding screen
    needs, and the reason this is keyed rather than flattened."""
    later = _NOW + datetime.timedelta(days=5)
    grouped = option_lots_by_symbol([
        _leg(occ="SAME", state="closed", realised=50.0),
        _leg(occ="SAME", state="open", opened=later),
        _leg(occ="OTHER"),
    ])
    assert set(grouped) == {"SAME", "OTHER"}
    assert len(grouped["SAME"]) == 2
    assert [lot.is_open for lot in grouped["SAME"]] == [False, True]


def test_no_legs_is_an_empty_map_not_an_error():
    assert option_lots_by_symbol([]) == {}


# ── The basis transfer, end to end ───────────────────────────────────────


def test_an_exercised_calls_equity_lot_carries_the_premium():
    """CR205's acceptance criterion 3, and the premise that was already
    satisfied. Exercising a long 100-strike call bought for $4 delivers 100
    shares whose basis is $104, NOT $100 — the $4 left cash at open, and
    charging it again at settlement would bill the same money twice.

    Asserted on the LOT (what the holding-detail screen renders), where it
    had never been pinned, rather than only on the holding aggregate.
    """
    from app.services.cost_basis_lots import compute_lots_fifo
    from app.trading_math.option import option_intrinsic_value

    # The rule under test, stated directly: basis = strike + premium paid.
    from app.services.option_lifecycle import SettlementDecision, settlement_effect

    effect = settlement_effect(
        SettlementDecision(action="exercise", in_the_money_by=30.0, settlement_value=30.0, pin_risk=False),
        right="call", strike=100.0, quantity=1.0, multiplier=100.0,
        avg_premium=4.0, collateral_posted=0.0, shares_available=0.0,
        cash_available=20_000.0,
    )
    assert effect.mode == "shares"
    assert effect.shares_delta == 100.0
    assert effect.basis_price == pytest.approx(104.0)

    # And the lot built from a trade row written at that basis agrees.
    row = SimpleNamespace(
        id=str(uuid4()), side="buy", quantity=100.0,
        entry_price=effect.basis_price, opened_at=_NOW, status="open",
        realised_pnl=None, closed_price=None,
    )
    lot = compute_lots_fifo([row])[0]
    assert lot.entry_price == pytest.approx(104.0)
    assert option_intrinsic_value("call", 100.0, 130.0) == pytest.approx(30.0)


def test_an_assigned_short_puts_equity_lot_is_reduced_by_the_premium():
    """The mirror. Writing a 100-strike put for $3 and being assigned means
    paying $100 for shares that effectively cost $97, because the premium was
    received at open."""
    from app.services.option_lifecycle import SettlementDecision, settlement_effect

    effect = settlement_effect(
        SettlementDecision(action="assign", in_the_money_by=10.0, settlement_value=10.0, pin_risk=False),
        right="put", strike=100.0, quantity=-1.0, multiplier=100.0,
        avg_premium=3.0, collateral_posted=10_000.0, shares_available=0.0,
        cash_available=0.0,
    )
    assert effect.shares_delta == 100.0
    assert effect.basis_price == pytest.approx(97.0)


def test_the_transfer_conserves_total_basis():
    """CR205's acceptance criterion 4. What the user paid in total does not
    change because the contract settled: $400 of premium plus $10,000 of
    strike is $10,400 of stock, and the option lot closes to zero."""
    from app.services.option_lifecycle import SettlementDecision, settlement_effect

    premium_paid = 4.0 * 100.0 * 1.0          # $400 left cash at open
    effect = settlement_effect(
        SettlementDecision(action="exercise", in_the_money_by=30.0, settlement_value=30.0, pin_risk=False),
        right="call", strike=100.0, quantity=1.0, multiplier=100.0,
        avg_premium=4.0, collateral_posted=0.0, shares_available=0.0,
        cash_available=20_000.0,
    )
    strike_paid = 100.0 * effect.shares_delta  # $10,000 leaves cash at settlement
    equity_basis = effect.basis_price * effect.shares_delta

    assert equity_basis == pytest.approx(premium_paid + strike_paid)

    # And the option lot itself is now closed, carrying no residual basis.
    lot = compute_option_lots([
        _leg(qty=1.0, premium=4.0, state="closed", realised=0.0,
             close_reason="exercised"),
    ])[0]
    assert lot.quantity_open == 0.0
