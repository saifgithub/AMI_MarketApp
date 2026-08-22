"""CR172 §7 / acceptance criterion 5 — the sweep, and the two defects it closes.

Three things live here and they are one piece of work:

**DEF357 — the lifecycle had no caller.** `run_option_lifecycle` was built
complete in slice 2, tested twenty-one times, and called from production zero
times. On live Alpha an option reached its expiry date and nothing happened to
it. The guard has to be a *caller-side* one: a test that calls the builder
proves the builder, which is exactly the substitution that let this ship, so
`test_the_production_sweep_reaches_the_lifecycle` asserts the entry point
reaches it rather than asserting the function works.

**DEF356 — an uncovered short call is reachable in two ways.** Selling the
shares out from under a covered call (nothing checks), and writing two covered
calls against one lot of 100 shares (each individually covered, the book short
100). The second is fixed at the open site; the first cannot be, because
`evaluate_outcomes`' bracket close enters no floor at all and correctly so.

**Criterion 5 — the backstop that makes the floor's promise true.** A short
call that has lost its cover is force-closed, market-hours gated, reported
visibly, never refused for insufficient `current_cash`.

The load-bearing test is `test_the_forced_close_does_not_move_total_value`.
Cash falls by the buy-back and rises by the released collateral, which is
exactly the option term the leg carried — so a margin close is visible in the
event and invisible in the NAV series, which is what "we closed your position"
should look like. A close that moved the total by the buy-back price would
book a loss for having been closed, silently, in the equity curve.
"""

from __future__ import annotations

import datetime
from datetime import timedelta
from uuid import uuid4

import pytest

from app.db import get_session
from app.db.models import SimOptionLegRow
from app.schemas.trade import OrderType, Side
from app.services.coach_engine import hydrate_coach_mandate
from app.services.market_data import (
    OptionChain,
    OptionQuote,
    Quote,
    set_market_data_provider,
)
from app.services.sim_engine import SimEngine
from app.services.sim_resting_orders import sweep_resting_orders
from app.trading_math.market_hours import session_close_on_or_after
from app.trading_math.option_strategy import StrategyLeg, strategy_metrics

EXPIRY = datetime.date.today() + datetime.timedelta(days=45)
SPOT = 50.0
_STRIKES = (45.0, 50.0, 55.0, 60.0)
# The 55 call's own mid on the board below: bid 2.00 / ask 2.10.
CALL_55_MID = 2.05


def _tight(bid: float) -> tuple[float, float]:
    """A 5% spread, comfortably inside `OPTION_MAX_SPREAD_PCT` (0.25).

    The first version of this board used a flat $0.40 spread, which is 5% at
    the 45 strike and **57% at the 60** — so the far strike classified
    `unusable` and every test that needed it silently exercised a different
    path. `test_the_lowest_strike_goes_first` passed under a mutation that
    reversed the sort, because the 60 leg it should have closed could not be
    priced at all. Same class as the two mutation survivals in slice 3: the
    test observed the wrong surface, and the fixture was what made it wrong.
    """
    return bid, round(bid * 1.05, 2)


def _oq(strike: float, bid: float, ask: float) -> OptionQuote:
    return OptionQuote(
        strike=strike, bid=bid, ask=ask, last=None, volume=50,
        open_interest=500, implied_vol=0.30,
    )


class _Board:
    """A liquid board around $50 plus the `^IRX` yield the enrichment reads."""

    name = "test_board"
    source = "test_board"

    def __init__(self) -> None:
        self.chain_reads: list[tuple[str, str]] = []

    def quote(self, ticker: str):
        if ticker.upper() == "^IRX":
            return Quote(price=4.2, source="yfinance", change_pct=0.0)
        return Quote(price=SPOT, source="yfinance", change_pct=0.0)

    def get_price(self, ticker: str):
        q = self.quote(ticker)
        return q.price if q is not None else None

    def earnings(self, ticker: str):
        return None

    def expiries(self, underlying: str):
        return [EXPIRY]

    def option_chain(self, underlying: str, expiry: datetime.date):
        self.chain_reads.append((underlying.upper(), expiry.isoformat()))
        if expiry != EXPIRY:
            return None
        calls = tuple(_oq(k, *_tight(max(1.0, 57 - k))) for k in _STRIKES)
        puts = tuple(_oq(k, *_tight(max(1.0, k - 43))) for k in _STRIKES)
        return OptionChain(
            underlying=underlying.upper(), expiry=expiry, calls=calls,
            puts=puts, source="yfinance",
        )


class _NoBoard(_Board):
    """Quotes the stock, serves no chain — the unpriceable case."""

    def option_chain(self, underlying: str, expiry: datetime.date):
        self.chain_reads.append((underlying.upper(), expiry.isoformat()))
        return None  # noqa: RET501 — the provider protocol returns a chain or None


@pytest.fixture()
def board():
    provider = _Board()
    set_market_data_provider(provider)
    yield provider
    set_market_data_provider(None)


@pytest.fixture()
def engine():
    return SimEngine()


def _mandate():
    return hydrate_coach_mandate({
        "plan": "trader", "single_name_cap_pct": 100.0,
        "compliance": {
            "long_only": False, "halal": False, "derivatives_allowed": True,
        },
    })


def _mid(strike: float) -> float:
    """The board's own mid for a call at `strike` — the price a leg opens at.

    Legs are opened at the board's mid deliberately, so `avg_premium` equals
    the mark the sweep will close at. That is what makes
    `test_the_forced_close_does_not_move_total_value` a statement about the
    close rather than about the gap between two prices.
    """
    bid, ask = _tight(max(1.0, 57 - strike))
    return (bid + ask) / 2.0


def _short_call(strike: float, quantity: float = -1.0) -> StrategyLeg:
    return StrategyLeg(
        right="call", strike=strike, quantity=quantity, premium=_mid(strike),
        multiplier=100.0, expiry=EXPIRY.isoformat(),
    )


def _session_now() -> datetime.datetime:
    """15:00 ET on a weekday — inside 09:30–16:00 whatever day the suite runs.
    Borrowed from `test_cr170_resting_orders.py`, same construction."""
    return session_close_on_or_after(
        datetime.datetime.now(datetime.UTC)
    ) - timedelta(hours=1)


def _covered_call_user(engine, *, shares: float = 100.0, strike: float = 55.0):
    user_id = uuid4()
    engine.ensure_portfolio(user_id)
    bought = engine.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=shares,
        order_type=OrderType.MARKET, mandate=_mandate(),
    )
    assert bought.accepted, bought.compliance.violations
    opened = engine.open_option_structure(
        user_id, underlying="AAPL", strategy_name="covered_call",
        legs=(_short_call(strike),), expiry=EXPIRY, mandate=_mandate(),
    )
    assert opened.accepted, opened.compliance.violations
    return user_id


def _legs(user_id):
    with get_session() as s:
        return s.query(SimOptionLegRow).filter(
            SimOptionLegRow.user_id == user_id
        ).all()


def _uncovered_shares(engine, user_id) -> float:
    """Recomputed from the book the way a reader would, not from the fix."""
    p = engine.ensure_portfolio(user_id)
    held = sum(h.quantity for h in p.holdings if h.ticker == "AAPL")
    metrics = strategy_metrics(
        [StrategyLeg(right=leg.right, strike=leg.strike, quantity=leg.quantity,
                     premium=leg.avg_premium, multiplier=leg.multiplier,
                     expiry=leg.expiry.isoformat())
         for leg in p.options],
        shares_held=held,
    )
    if metrics is None or not metrics.has_uncovered_short_call:
        return 0.0
    return 1.0


# ── DEF356 instance 2 — two covered calls, one lot ──────────────────────────


def test_a_second_covered_call_cannot_be_written_against_the_same_shares(
    board, engine,
):
    """Each structure is individually covered; the book would be short 100.

    `check_option_open` reasons about one structure and cannot see the other,
    so the netting happens at the call site — which is why this is asserted
    through `open_option_structure` and not through the floor.
    """
    from app.agents.safety_floor import NAKED_CALL_REFUSAL

    user_id = _covered_call_user(engine, strike=55.0)
    second = engine.open_option_structure(
        user_id, underlying="AAPL", strategy_name="covered_call",
        legs=(_short_call(60.0),), expiry=EXPIRY, mandate=_mandate(),
    )

    assert second.accepted is False
    assert NAKED_CALL_REFUSAL in second.compliance.violations
    assert len([leg for leg in _legs(user_id) if leg.state == "open"]) == 1


def test_a_second_covered_call_is_allowed_once_the_shares_are_there(board, engine):
    """The companion — otherwise the test above passes on a rule that refuses
    every second structure regardless of cover."""
    user_id = _covered_call_user(engine, shares=200.0, strike=55.0)
    second = engine.open_option_structure(
        user_id, underlying="AAPL", strategy_name="covered_call",
        legs=(_short_call(60.0),), expiry=EXPIRY, mandate=_mandate(),
    )
    assert second.accepted is True, second.compliance.violations
    assert len([leg for leg in _legs(user_id) if leg.state == "open"]) == 2


def test_the_netting_is_per_underlying_not_across_the_book(board, engine):
    """100 AAPL shares do not cover a short MSFT call, and 100 MSFT shares do
    not stop an AAPL covered call being written."""
    user_id = _covered_call_user(engine, shares=100.0, strike=55.0)
    engine.submit(
        user_id=user_id, ticker="MSFT", side=Side.BUY, quantity=100.0,
        order_type=OrderType.MARKET, mandate=_mandate(),
    )
    msft = engine.open_option_structure(
        user_id, underlying="MSFT", strategy_name="covered_call",
        legs=(_short_call(55.0),), expiry=EXPIRY, mandate=_mandate(),
    )
    assert msft.accepted is True, msft.compliance.violations


# ── DEF356 instance 1 + criterion 5 — the cover is sold away ────────────────


def test_selling_the_cover_leaves_an_uncovered_short_call_for_the_sweep(
    board, engine,
):
    """The defect itself, reproduced, so the fix below has something to fix.

    The sale is NOT refused — deliberately. There is no user-initiated close
    path for an option structure, so refusing would trap the user in the
    position until expiry with no action available to them.
    """
    user_id = _covered_call_user(engine)
    sold = engine.submit(
        user_id=user_id, ticker="AAPL", side=Side.SELL, quantity=100.0,
        order_type=OrderType.MARKET, mandate=_mandate(),
    )
    assert sold.accepted is True
    assert _uncovered_shares(engine, user_id) == 1.0


def test_the_sweep_closes_a_short_call_that_lost_its_cover(board, engine):
    user_id = _covered_call_user(engine)
    engine.submit(
        user_id=user_id, ticker="AAPL", side=Side.SELL, quantity=100.0,
        order_type=OrderType.MARKET, mandate=_mandate(),
    )

    stats = sweep_resting_orders(
        user_id=user_id, now=_session_now(), engine=engine,
    )

    assert stats["options_margined"] == 1
    legs = _legs(user_id)
    assert len(legs) == 1
    assert legs[0].state == "closed"
    assert legs[0].close_reason == "margin"
    assert float(legs[0].close_price) == CALL_55_MID
    assert _uncovered_shares(engine, user_id) == 0.0


def test_a_covered_call_is_left_alone(board, engine):
    """The companion assertion — a sweep that closes everything would pass the
    test above while destroying every covered call in the product."""
    user_id = _covered_call_user(engine)

    stats = sweep_resting_orders(
        user_id=user_id, now=_session_now(), engine=engine,
    )

    assert stats["options_margined"] == 0
    assert _legs(user_id)[0].state == "open"


def test_the_forced_close_does_not_move_total_value(board, engine):
    """The identity. Cash falls by the buy-back and rises by the released
    collateral — which is exactly the option term the leg carried — so the
    close is visible in the event and invisible in the equity curve.

    A close that moved the total by the buy-back price would book a loss for
    having been closed, silently, in `portfolio_nav_daily` and the TWR chain.

    **The identity is "continuous at the leg's own carrying mark", not
    "continuous full stop", and today those are the same thing only by
    accident.** With §11's option-marks feed unbuilt, `option_leg_value` holds
    a leg at the premium it opened at, so a buy-back at any other price moves
    the total by the difference — correctly, the way selling a share above its
    `avg_cost` does. This test opens at the board's own mid so the two
    coincide and the close itself is what is measured. When §11 wires marks,
    the carrying value becomes the market mark and this holds for any price;
    until then, a margin close at a moved market DOES move the total, and that
    is a real P&L event rather than a bug.
    """
    user_id = _covered_call_user(engine)
    engine.submit(
        user_id=user_id, ticker="AAPL", side=Side.SELL, quantity=100.0,
        order_type=OrderType.MARKET, mandate=_mandate(),
    )
    before_p, _marks, before, _dd, _src = engine.portfolio_marks_snapshot(user_id)
    cash_before = before_p.current_cash

    sweep_resting_orders(user_id=user_id, now=_session_now(), engine=engine)

    after_p, _marks2, after, _dd2, _src2 = engine.portfolio_marks_snapshot(user_id)
    assert after == pytest.approx(before, abs=0.01), (
        f"the forced close moved total_value from {before} to {after}; a "
        "margin close settles at the leg's own mark and must be continuous"
    )
    # Continuity here is a real cancellation, not two zeros: the leg carried a
    # −$220 option term before and cash actually fell by $220 to retire it.
    assert before_p.options and not after_p.options
    assert after_p.current_cash == pytest.approx(
        cash_before - CALL_55_MID * 100.0, abs=0.01,
    )
    # The premise, stated rather than assumed: the leg was carried at exactly
    # the mark it was retired at, so the cancellation above is the close's own
    # arithmetic and not a coincidence of two prices that happen to agree.
    assert float(before_p.options[0].avg_premium) == pytest.approx(CALL_55_MID)


def test_the_close_is_charged_even_with_no_cash_to_charge(board, engine):
    """Criterion 5's third clause, and the one most likely to be 'helpfully'
    softened: **never refused for insufficient `current_cash`.**

    Cash is spent down to nothing before the sweep, so the buy-back has
    nothing to draw on. Refusing would leave the unbounded position open,
    which is the single outcome D3 exists to prevent — so the close happens
    and the cash goes where it goes.
    """
    user_id = _covered_call_user(engine)
    engine.submit(
        user_id=user_id, ticker="AAPL", side=Side.SELL, quantity=100.0,
        order_type=OrderType.MARKET, mandate=_mandate(),
    )
    with get_session() as s:
        p_row = engine._load_portfolio_row(s, user_id)
        p_row.current_cash = 0.0

    stats = sweep_resting_orders(
        user_id=user_id, now=_session_now(), engine=engine,
    )

    assert stats["options_margined"] == 1
    assert _legs(user_id)[0].close_reason == "margin"
    assert engine.ensure_portfolio(user_id).current_cash < 0.0, (
        "the buy-back must actually be charged, not waived to keep cash "
        "non-negative — a waived charge is a position closed for free"
    )


def test_a_leg_that_cannot_be_priced_is_left_open_and_reported(engine):
    """DEF305's rule, one instrument along: never force-close a position the
    user did not ask to close at a price nobody could check."""
    provider = _NoBoard()
    set_market_data_provider(provider)
    try:
        user_id = uuid4()
        engine.ensure_portfolio(user_id)
        engine.submit(
            user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=100.0,
            order_type=OrderType.MARKET, mandate=_mandate(),
        )
        with get_session() as s:
            p_row = engine._load_portfolio_row(s, user_id)
            s.add(SimOptionLegRow(
                id=uuid4(), user_id=user_id, portfolio_id=p_row.id,
                occ_symbol="AAPL  991231C00055000", underlying="AAPL",
                right="call", strike=55.0, expiry=EXPIRY,
                quantity=-1.0, avg_premium=2.2, multiplier=100.0,
                collateral_posted=0.0, strategy_id=uuid4(),
                strategy_name="covered_call", state="open",
            ))
        engine.submit(
            user_id=user_id, ticker="AAPL", side=Side.SELL, quantity=100.0,
            order_type=OrderType.MARKET, mandate=_mandate(),
        )
        cash_before = engine.ensure_portfolio(user_id).current_cash

        events = engine.force_close_uncovered_calls(user_id)

        assert len(events) == 1
        assert events[0].action == "not_evaluated"
        assert events[0].compliance_not_evaluated, (
            "an uncovered call left open must say WHY, not read as safe"
        )
        assert _legs(user_id)[0].state == "open"
        assert engine.ensure_portfolio(user_id).current_cash == cash_before
    finally:
        set_market_data_provider(None)


def test_the_event_says_what_happened_and_why(board, engine):
    """§7: every automatic close is reported, never silent. The user did not
    ask for this, so the message has to carry the reason, not just the fact."""
    user_id = _covered_call_user(engine)
    engine.submit(
        user_id=user_id, ticker="AAPL", side=Side.SELL, quantity=100.0,
        order_type=OrderType.MARKET, mandate=_mandate(),
    )

    events = engine.force_close_uncovered_calls(user_id)

    assert len(events) == 1
    message = events[0].message
    assert events[0].action == "margin_closed"
    assert "AAPL" in message
    assert "no ceiling" in message
    assert "cash" in message, "the never-refused-for-cash rule is user-facing"
    assert "AMI" in message, "user-facing copy names AMI, never 'the AI'"


def test_the_lowest_strike_goes_first(board, engine):
    """Two short calls, cover for one. Containment is the purpose, so the most
    liable — and most likely to be assigned — is the one that goes."""
    user_id = _covered_call_user(engine, shares=200.0, strike=50.0)
    second = engine.open_option_structure(
        user_id, underlying="AAPL", strategy_name="covered_call",
        legs=(_short_call(60.0),), expiry=EXPIRY, mandate=_mandate(),
    )
    assert second.accepted
    engine.submit(
        user_id=user_id, ticker="AAPL", side=Side.SELL, quantity=100.0,
        order_type=OrderType.MARKET, mandate=_mandate(),
    )

    engine.force_close_uncovered_calls(user_id)

    by_strike = {float(leg.strike): leg.state for leg in _legs(user_id)}
    assert by_strike == {50.0: "closed", 60.0: "open"}


def test_the_close_stops_as_soon_as_the_book_is_covered_again(board, engine):
    """Not "close every short call" — close until covered. Over-closing is the
    account taking more from the user than the rule requires."""
    user_id = _covered_call_user(engine, shares=200.0, strike=50.0)
    engine.open_option_structure(
        user_id, underlying="AAPL", strategy_name="covered_call",
        legs=(_short_call(60.0),), expiry=EXPIRY, mandate=_mandate(),
    )
    engine.submit(
        user_id=user_id, ticker="AAPL", side=Side.SELL, quantity=100.0,
        order_type=OrderType.MARKET, mandate=_mandate(),
    )

    events = engine.force_close_uncovered_calls(user_id)

    assert len(events) == 1
    assert sum(1 for leg in _legs(user_id) if leg.state == "open") == 1


# ── the hours gate ─────────────────────────────────────────────────────────


def test_the_margin_close_does_not_fire_outside_the_session(board, engine):
    """§7's table: hours-gated, because a forced close against a stale
    overnight print is CR109 §5.1's time machine pointed at the user."""
    user_id = _covered_call_user(engine)
    engine.submit(
        user_id=user_id, ticker="AAPL", side=Side.SELL, quantity=100.0,
        order_type=OrderType.MARKET, mandate=_mandate(),
    )
    # A Sunday, so no session anywhere in the day.
    sunday = datetime.datetime(2026, 8, 23, 18, 0, tzinfo=datetime.UTC)

    stats = sweep_resting_orders(user_id=user_id, now=sunday, engine=engine)

    assert stats["options_margined"] == 0
    assert _legs(user_id)[0].state == "open"


def test_the_kill_switch_covers_the_margin_close_too(board, engine, monkeypatch):
    """DEF305 gates every pass that closes a position off a price nobody
    checked. This is one of them, so it goes inside the same switch — and the
    suppression log names it, because a switch that silently disables a third
    thing is how the second one was found late."""
    import app.services.sim_resting_orders as sro

    user_id = _covered_call_user(engine)
    engine.submit(
        user_id=user_id, ticker="AAPL", side=Side.SELL, quantity=100.0,
        order_type=OrderType.MARKET, mandate=_mandate(),
    )
    monkeypatch.setattr(sro, "bracket_closing_enabled", lambda: False)

    stats = sweep_resting_orders(
        user_id=user_id, now=_session_now(), engine=engine,
    )

    assert stats["brackets_suppressed"] == 1
    assert stats["options_margined"] == 0
    assert _legs(user_id)[0].state == "open"


# ── DEF357 — the caller-side guard ─────────────────────────────────────────


def test_the_production_sweep_reaches_the_lifecycle(board, engine, monkeypatch):
    """DEF357's guard, and it has to be shaped exactly like this.

    Twenty-one tests called `run_option_lifecycle` directly and every one
    passed while the product never called it once. So this asserts the
    PRODUCTION entry point reaches it — `sweep_resting_orders`, the same
    function `main.py`'s tick and `/v1/sim/.../evaluate` both drive — rather
    than asserting the lifecycle works, which is a different claim that was
    already true and already useless.
    """
    seen: list = []
    original = SimEngine.run_option_lifecycle

    def spy(self, user_id, **kwargs):
        seen.append((user_id, kwargs))
        return original(self, user_id, **kwargs)

    monkeypatch.setattr(SimEngine, "run_option_lifecycle", spy)
    user_id = _covered_call_user(engine)

    sweep_resting_orders(user_id=user_id, now=_session_now(), engine=engine)

    assert [uid for uid, _ in seen] == [user_id], (
        "sweep_resting_orders did not reach run_option_lifecycle — DEF357 "
        "is back and expiry, exercise and assignment are dead again"
    )
    assert seen[0][1].get("mandate") is not None, (
        "without a mandate the exercise floor cannot re-enter, and every "
        "created stock position is reported unchecked"
    )


def test_the_lifecycle_runs_with_the_market_shut(board, engine, monkeypatch):
    """§7's table: NOT hours-gated. An option expired at 16:00 ET on Friday
    did not stop having expired because we noticed on Saturday."""
    seen: list = []
    original = SimEngine.run_option_lifecycle

    def spy(self, user_id, **kwargs):
        seen.append(user_id)
        return original(self, user_id, **kwargs)

    monkeypatch.setattr(SimEngine, "run_option_lifecycle", spy)
    user_id = _covered_call_user(engine)
    sunday = datetime.datetime(2026, 8, 23, 18, 0, tzinfo=datetime.UTC)

    sweep_resting_orders(user_id=user_id, now=sunday, engine=engine)

    assert seen == [user_id]


def test_a_book_with_no_option_legs_does_not_reach_the_lifecycle(board, engine):
    """The sweep is on the hot path of every app open. A user who has never
    touched an option must not pay for a pass that has nothing to do."""
    seen: list = []
    original = SimEngine.run_option_lifecycle
    user_id = uuid4()
    engine.ensure_portfolio(user_id)

    try:
        SimEngine.run_option_lifecycle = lambda self, uid, **kw: (
            seen.append(uid) or original(self, uid, **kw)
        )
        sweep_resting_orders(user_id=None, now=_session_now(), engine=engine)
    finally:
        SimEngine.run_option_lifecycle = original

    assert seen == []
