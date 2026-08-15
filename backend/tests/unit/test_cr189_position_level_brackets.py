"""CR189 — one position, one average, one bracket.

Saiful, deciding the CR188 slice 3 tile: *"When the user has bought shares at
different times, the holding tile should show the weighted average buying
prices. And the stop loss and take profit should also be recalculated based on
weighted average."*

A bracket is stored per **trade row**; a position is per **ticker**. Buy the same
name twice and there are two stops with room on the tile for one. This cannot be
solved in the widget: a tile showing a blended $97 while the sweep still fires
$95 and $99 is lying about a risk control — the user reads one number and a
different one liquidates them. So the sweep evaluates the position's level.

The rule, over live lots only, weighted by shares still open (`Lot.quantity_open`,
CR029-MATH — so a sold-out lot weighs nothing, which is DEF318 as arithmetic
rather than a second gate):

    10 @ $100 stop $95  +  10 @ $110 stop $99   ->  $97.00
    10 @ $100 stop $95  +  10 @ $110 no stop    ->  $95.00
    10 @ $100 no stop   +  10 @ $110 no stop    ->  None

**A lot with no stop is excluded from the average, not counted as zero.** That
one choice is the entire special-case handling. Zeroing drags the stop to $47.50,
which protects nothing; dropping it removes a control the user set by hand.
Excluding carries existing protection across the whole position — the only one of
the three a user would recognise as their own intent.

## What this costs, recorded where it will be read

**Two lots with different exits no longer scale out.** 1 share targeting $110
beside 2 targeting $900 blends to $636.67, which is neither. Partial exits at a
named price are a resting SELL order (CR170) — the mechanism actually built for
it, and one that renders on the position's own tile. See
`test_def110_outcome_liquidates.py::test_two_lots_exit_on_the_positions_blended_level_not_their_own`,
which is the live `abc5e232` case re-asserted rather than deleted.

Measured before shipping: **no training position on Alpha has more than one open
lot**, so no live user's bracket moved. The three multi-lot positions are
game-lane, carry no brackets, and `evaluate_outcomes` is training-scoped anyway.
"""

from __future__ import annotations

from uuid import uuid4

from app.db import get_session
from app.db.models import SimTradeRow
from app.schemas.trade import OrderType, Side
from app.services.coach_engine import hydrate_coach_mandate
from app.services.market_data import Quote
from app.services.sim_engine import SimEngine
from app.trading_math.order_pricing import LotBracket, blended_bracket


class _Pinned:
    def __init__(self, price: float):
        self.price = price

    def quote(self, ticker: str) -> Quote | None:
        return Quote(price=self.price, source="yfinance")

    def history(self, *a, **k):  # pragma: no cover
        return []

    def news(self, *a, **k):  # pragma: no cover
        return []

    def earnings(self, *a, **k):  # pragma: no cover
        return None


def _mandate():
    return hydrate_coach_mandate(
        {"plan": "trader", "single_name_cap_pct": 100.0, "max_open_risk_pct": 100.0}
    )


def _buy(sim, user_id, ticker, qty, **kw):
    r = sim.submit(user_id=user_id, ticker=ticker, side=Side.BUY, quantity=qty,
                   mandate=_mandate(), order_type=OrderType.MARKET, **kw)
    assert r.accepted and r.trade is not None, r.compliance.violations
    return r.trade


def _row(trade_id) -> SimTradeRow:
    with get_session() as s:
        return s.get(SimTradeRow, trade_id)


# ── The rule, as pure arithmetic ───────────────────────────────────────────


def test_two_bracketed_lots_blend_by_open_quantity():
    stop, target = blended_bracket([
        LotBracket(quantity_open=10, stop=95.0, target=120.0),
        LotBracket(quantity_open=10, stop=99.0, target=130.0),
    ])
    assert (stop, target) == (97.0, 125.0)


def test_the_weighting_is_by_shares_not_by_lot_count():
    """30 shares at $99 must pull harder than 10 at $95."""
    stop, _ = blended_bracket([
        LotBracket(quantity_open=10, stop=95.0, target=None),
        LotBracket(quantity_open=30, stop=99.0, target=None),
    ])
    assert stop == 98.0  # (95×10 + 99×30) / 40


def test_a_lot_without_a_stop_is_excluded_not_zeroed():
    """The case with no obviously-right answer. Zeroing gives $47.50, which
    protects nothing; this carries the user's own $95 across all 20 shares."""
    stop, _ = blended_bracket([
        LotBracket(quantity_open=10, stop=95.0, target=None),
        LotBracket(quantity_open=10, stop=None, target=None),
    ])
    assert stop == 95.0


def test_stop_and_target_are_averaged_over_their_own_contributors():
    """One lot set only a stop, the other only a target. Both survive, each over
    the shares that actually named it — a shared denominator would halve both."""
    stop, target = blended_bracket([
        LotBracket(quantity_open=10, stop=95.0, target=None),
        LotBracket(quantity_open=10, stop=None, target=130.0),
    ])
    assert (stop, target) == (95.0, 130.0)


def test_a_sold_out_lot_weighs_nothing():
    """DEF318 restated as arithmetic. The dead lot's $95 must not pull the live
    lot's $99 down — that is the defect where a re-entered position was stopped
    out at a price the user never named."""
    stop, _ = blended_bracket([
        LotBracket(quantity_open=0.0, stop=95.0, target=None),
        LotBracket(quantity_open=10, stop=99.0, target=None),
    ])
    assert stop == 99.0


def test_an_unprotected_position_has_no_bracket():
    assert blended_bracket([
        LotBracket(quantity_open=10, stop=None, target=None),
    ]) == (None, None)


def test_no_lots_at_all_is_not_a_crash():
    assert blended_bracket([]) == (None, None)


# ── The rule, through the sweep ────────────────────────────────────────────


def test_the_sweep_fires_on_the_blended_stop():
    """Acceptance 4, on the price that separates the two models.

    $96 sits above lot 1's own $95 and below lot 2's $99, so under per-row
    brackets exactly one lot would close and the other would survive. The
    position's stop is $97, so the whole position exits — one level, one exit.
    """
    prov = _Pinned(100.0)
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    a = _buy(sim, user_id, "NVDA", 10, stop=95.0)
    b = _buy(sim, user_id, "NVDA", 10, stop=99.0)

    prov.price = 96.0
    updates = sim.evaluate_outcomes(user_id)

    assert sorted(u.new_status for u in updates) == ["lost", "lost"]
    assert _row(a.id).status == "lost"
    assert _row(b.id).status == "lost"
    p = sim.ensure_portfolio(user_id)
    assert not any(h.ticker == "NVDA" for h in p.holdings)


def test_the_sweep_holds_above_the_blended_stop():
    """Non-vacuity for the test above, and the half a user feels: $96 fires but
    $98 must not, even though lot 2's own $99 stop is through."""
    prov = _Pinned(100.0)
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    _buy(sim, user_id, "NVDA", 10, stop=95.0)
    _buy(sim, user_id, "NVDA", 10, stop=99.0)

    prov.price = 98.0
    assert sim.evaluate_outcomes(user_id) == []
    assert sim.ensure_portfolio(user_id).holdings[0].quantity == 20


def test_a_single_lot_position_behaves_exactly_as_before():
    """**Acceptance 7 — the non-vacuity guard, and the reason it is here.**

    Every other test in this file passes on an implementation that quietly
    disables brackets for anyone holding one lot, which is nearly every user.
    That is this project's most-repeated defect (P21 — a check present in the
    source and inert at runtime), it has already happened twice in this exact
    area (DEF312 on both sides of the wire), and the code being changed is what
    liquidates real positions overnight. The blend of one is itself.
    """
    prov = _Pinned(100.0)
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    solo = _buy(sim, user_id, "NVDA", 10, stop=95.0, target=110.0)

    prov.price = 94.0
    updates = sim.evaluate_outcomes(user_id)

    assert [u.new_status for u in updates] == ["lost"]
    assert _row(solo.id).realised_pnl == -60.0  # (94 − 100) × 10
    assert not any(h.ticker == "NVDA" for h in sim.ensure_portfolio(user_id).holdings)


def test_one_tickers_blend_does_not_reach_another():
    """Lots are per ticker. A cheap stop on one name must not drag another's."""
    prov = _Pinned(100.0)
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    nvda = _buy(sim, user_id, "NVDA", 10, stop=95.0)
    msft = _buy(sim, user_id, "MSFT", 10, stop=50.0)

    prov.price = 94.0
    updates = sim.evaluate_outcomes(user_id)

    assert [u.trade_id for u in updates] == [nvda.id]
    assert _row(msft.id).status == "open"


# ── Acceptance 6 — the blend that would liquidate on arrival ───────────────


def test_a_buy_whose_blend_lands_wrong_side_is_refused():
    """The order's OWN bracket is fine and the POSITION's is not — and the only
    way that happens is worth stating, because it is also when it matters most.

    A blend can only sit at or above the mark if an existing lot's stop already
    is, which means the position is **already stop-eligible and waiting for the
    sweep**. That window is real rather than theoretical: brackets fire only
    during market hours (DEF305's gating), so a price that gaps through a stop
    overnight sits un-swept until the open.

    Buy 10 NVDA at $110 with a stop at $99 — valid. Price gaps to $98 before the
    session opens; the sweep has not run. Buy 10 more at $98 with a stop at $97,
    also valid against its own entry. The position's stop is now $98.00, exactly
    the market: at the open the sweep liquidates all 20, and the post-stop-out
    cooldown then hard-blocks the user's next buy. Refused rather than warned —
    nobody can act on a warning about arithmetic they did not do.
    """
    prov = _Pinned(110.0)
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    _buy(sim, user_id, "NVDA", 10, stop=99.0)

    prov.price = 98.0  # gapped through the stop, sweep not yet run
    r = sim.submit(
        user_id=user_id, ticker="NVDA", side=Side.BUY, quantity=10,
        mandate=_mandate(), order_type=OrderType.MARKET, stop=97.0,
    )

    assert not r.accepted
    reason = r.compliance.violations[0]
    assert "20 NVDA" in reason           # names the whole position, not the order
    assert "$98.00" in reason            # names the level it would land on
    assert "next sweep" in reason
    assert sim.ensure_portfolio(user_id).holdings[0].quantity == 10


def test_a_buy_that_merely_moves_the_stop_is_accepted():
    """Non-vacuity. A blend that moves the stop but stays below the market is
    ordinary and must go through — this is the case the ticket DISCLOSES rather
    than refuses, and a refusal here would block routine adding-to-a-winner."""
    prov = _Pinned(100.0)
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    _buy(sim, user_id, "NVDA", 10, stop=95.0)

    r = sim.submit(
        user_id=user_id, ticker="NVDA", side=Side.BUY, quantity=10,
        mandate=_mandate(), order_type=OrderType.MARKET, stop=99.0,
    )

    assert r.accepted, r.compliance.violations
    assert sim.position_bracket(user_id, "NVDA")[0] == 97.0


def test_a_first_buy_is_never_blend_refused():
    """Nothing held means the blend is the order's own bracket, already checked
    by `bracket_is_wrong_side` above. The CR189 gate must not double-refuse it
    or fire on an empty position."""
    prov = _Pinned(100.0)
    sim = SimEngine(provider=prov)
    user_id = uuid4()

    r = sim.submit(
        user_id=user_id, ticker="NVDA", side=Side.BUY, quantity=10,
        mandate=_mandate(), order_type=OrderType.MARKET, stop=95.0,
    )
    assert r.accepted, r.compliance.violations


def test_position_bracket_prices_an_order_that_does_not_exist_yet():
    """What the ticket's disclosure is built on: the bracket the position WOULD
    have. One derivation feeding the sweep, the refusal and the sentence."""
    prov = _Pinned(100.0)
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    _buy(sim, user_id, "NVDA", 10, stop=95.0)

    before = sim.position_bracket(user_id, "NVDA")
    after = sim.position_bracket(
        user_id, "NVDA",
        extra=LotBracket(quantity_open=10, stop=99.0, target=None),
    )

    assert before[0] == 95.0
    assert after[0] == 97.0   # "raises your stop on all 20 NVDA from $95 to $97"
