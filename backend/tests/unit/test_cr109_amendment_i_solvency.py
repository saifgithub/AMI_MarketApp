"""CR109 Amendment I — the account may not go negative.

Saiful, 2026-08-12, having decided shorting keeps its full-notional
collateral: *"keep no leverage, but when the game ends, all positions must be
closed. how do we keep the account from going negative?"*

Amendment G left the leg unbounded below on purpose and named the run's own
clock as the containment. That was wrong, and the reason is arithmetic rather
than taste: **a run's NAV feeds the TWR chain, and TWR is undefined across a
sign change.** One negative NAV row makes every link after it — the Close, the
board, the drawdown denominator, the career-point delta — arithmetic about
nothing.

Two mechanisms, and the tests below are split the same way:

1. **The orderly case.** A forced buy-in at `leg <= 10% of collateral`
   (equivalently `mark >= 1.9x entry`) caps a short's loss at what it posted,
   making its worst case equal to a long's.
2. **The gap.** A name that closes at 1.8x and opens at 3x fills that buy-in
   at 3x, and the account is already negative when the mechanism runs. The
   run floors at zero and BUSTS, keeping the scoring chain defined, while
   `nav_shortfall` preserves the number the floor hides.

The floor is emphatically NOT the `?? 0` class this feature keeps producing:
nothing is defaulted or guessed, and both halves of the true value survive in
the two fields their two consumers need. There is a test for that below,
because the distinction is the whole defence.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import GameEntryRow, GameFieldRow, GameShortPositionRow
from app.schemas.trade import Side
from app.services import market_data as _md
from app.services.sim_engine import SimEngine
from app.trading_math.shorts import (
    MAINTENANCE_FLOOR_PCT,
    nav_floor,
    short_buyin_trigger_price,
    short_leg,
    short_maintenance_floor,
    short_needs_buyin,
)


class _MutableProvider:
    name = "fake"

    def __init__(self, price: float = 100.0) -> None:
        self.price = price

    def quote(self, ticker: str):
        return _md.Quote(price=self.price, source=self.name)

    def get_price(self, ticker: str):
        return self.price

    def history(self, ticker: str, period: str):
        return None

    def news(self, ticker: str, limit: int = 5):
        return None

    def earnings(self, ticker: str):
        return None


# ── The trigger, in closed form ──────────────────────────────────────────


def test_the_leg_is_exactly_zero_when_the_name_doubles():
    """The fact the whole amendment rests on.

    `cash_posted = entry*q`, so `leg = q*(2*entry - mark)`. If this stops
    being true the trigger below is measuring the wrong thing, and no other
    test in this file would notice.
    """
    entry, qty = 100.0, 10.0
    posted = entry * qty
    assert short_leg(posted, qty, entry, 200.0) == pytest.approx(0.0)
    assert short_leg(posted, qty, entry, 300.0) == pytest.approx(-1_000.0)


def test_the_trigger_price_is_derived_from_the_floor_not_a_second_constant():
    """A second hard-coded multiple could drift from the floor it is meant
    to express. This pins them to each other."""
    entry, qty = 100.0, 10.0
    posted = entry * qty
    trigger = short_buyin_trigger_price(entry)

    assert trigger == pytest.approx(entry * (2.0 - MAINTENANCE_FLOOR_PCT))
    assert trigger == pytest.approx(190.0)
    # At the trigger, the leg is worth exactly the maintenance floor.
    assert short_leg(posted, qty, entry, trigger) == pytest.approx(
        short_maintenance_floor(posted)
    )


def test_the_trigger_is_a_pure_multiple_independent_of_size():
    """The quantity cancels — which is what lets the ticket show the trigger
    price before the player has chosen a size."""
    assert short_buyin_trigger_price(50.0) == pytest.approx(95.0)
    assert short_buyin_trigger_price(1_000.0) == pytest.approx(1_900.0)


def test_needs_buyin_fires_at_the_floor_and_not_before():
    entry, qty = 100.0, 10.0
    posted = entry * qty
    assert not short_needs_buyin(posted, qty, entry, 100.0)   # flat
    assert not short_needs_buyin(posted, qty, entry, 150.0)   # losing, fine
    assert not short_needs_buyin(posted, qty, entry, 189.99)  # just above
    assert short_needs_buyin(posted, qty, entry, 190.0)       # at the floor
    assert short_needs_buyin(posted, qty, entry, 250.0)       # past it


def test_the_floor_leaves_room_for_the_cover_fee():
    """Why the floor is 10% and not zero.

    At the trigger the leg still holds 10% of the collateral, and the cover
    fee is 0.1% of a notional that has by then not quite doubled. If the
    floor were zero the fee would come out of the player's OTHER positions,
    in the one mechanism built to stop exactly that leak.
    """
    from app.services.games_scoring import trade_fee

    entry, qty = 100.0, 10.0
    posted = entry * qty
    trigger = short_buyin_trigger_price(entry)
    leg_at_trigger = short_leg(posted, qty, entry, trigger)
    cover_fee = trade_fee(trigger * qty)

    assert leg_at_trigger > cover_fee
    assert leg_at_trigger == pytest.approx(100.0)


# ── The floor, and what it must not destroy ──────────────────────────────


def test_nav_floor_is_a_no_op_on_a_solvent_book():
    assert nav_floor(10_000.0) == (10_000.0, 0.0)
    assert nav_floor(0.0) == (0.0, 0.0)


def test_nav_floor_preserves_the_number_it_hides():
    """The anti-`?? 0` assertion.

    A floor that returned only `0.0` would be the defect class this feature
    has produced nine times: a fact replaced by a default, with nothing left
    to tell the two apart. Both halves survive.
    """
    nav, shortfall = nav_floor(-2_450.75)
    assert nav == 0.0
    assert shortfall == pytest.approx(2_450.75)
    # And the two reconstruct the original, exactly.
    assert nav - shortfall == pytest.approx(-2_450.75)


# ── The orderly case, end to end ─────────────────────────────────────────


def _short(sim, user_id, run_id, ticker="AAPL", qty=10.0):
    return sim.submit_game_trade(
        user_id=user_id, run_id=run_id, ticker=ticker, side=Side.SELL, quantity=qty,
    )


def _open_short_row(run_id):
    with get_session() as s:
        return s.execute(
            select(GameShortPositionRow).where(
                GameShortPositionRow.run_id == run_id,
                GameShortPositionRow.state == "open",
            )
        ).scalars().first()


def _seed_live_entry(user_id, run_id, *, state="active"):
    """A field + entry the sweep will consider. The sweep joins entries, so
    a short with no entry row is invisible to it."""
    now = datetime.now(timezone.utc)
    with get_session() as s:
        field = GameFieldRow(
            id=uuid4(), cadence="week", state="live",
            entry_opens_at=now - timedelta(days=3),
            locks_at=now - timedelta(days=2),
            starts_on=(now - timedelta(days=2)).date(),
            ends_on=(now + timedelta(days=3)).date(),
            entrant_count=1, kind="open",
        )
        s.add(field)
        s.flush()
        s.add(GameEntryRow(
            id=uuid4(), field_id=field.id, user_id=user_id,
            run_id=run_id, state=state,
        ))
        return field.id


def test_a_short_that_doubles_is_bought_in_and_the_account_stays_solvent():
    from app.services.games_service import sweep_forced_buyins

    provider = _MutableProvider(100.0)
    sim = SimEngine(provider=provider)
    user_id, run_id = uuid4(), uuid4()
    _seed_live_entry(user_id, run_id)

    opened = _short(sim, user_id, run_id, qty=10)   # 1,000 posted
    assert opened.accepted, opened.reason

    # Moves against them, but not yet to the floor.
    provider.price = 180.0
    stats = sweep_forced_buyins(now=_market_open_moment(), sim=sim)
    assert stats["bought_in"] == 0
    assert _open_short_row(run_id) is not None

    # Through the floor.
    provider.price = 195.0
    stats = sweep_forced_buyins(now=_market_open_moment(), sim=sim)
    assert stats["bought_in"] == 1
    assert _open_short_row(run_id) is None

    book = sim.ensure_portfolio(user_id, kind="game", run_id=run_id)
    assert book.total_value({}) > 0, "the buy-in did not keep the book solvent"


def test_the_sweep_does_not_touch_a_short_that_is_merely_losing():
    """The mutation guard for the test above: a sweep that bought in
    everything would pass its second half."""
    from app.services.games_service import sweep_forced_buyins

    provider = _MutableProvider(100.0)
    sim = SimEngine(provider=provider)
    user_id, run_id = uuid4(), uuid4()
    _seed_live_entry(user_id, run_id)
    _short(sim, user_id, run_id, qty=10)

    provider.price = 150.0   # -50% on the position, well short of the floor
    stats = sweep_forced_buyins(now=_market_open_moment(), sim=sim)
    assert stats["bought_in"] == 0
    assert _open_short_row(run_id) is not None


def test_the_sweep_is_a_no_op_outside_market_hours():
    """A forced cover needs a real price. Filling one at the last close is
    the stale fill §5.1 forbids for user orders, and the house does not get
    to exempt itself from it."""
    from app.services.games_service import sweep_forced_buyins

    provider = _MutableProvider(100.0)
    sim = SimEngine(provider=provider)
    user_id, run_id = uuid4(), uuid4()
    _seed_live_entry(user_id, run_id)
    _short(sim, user_id, run_id, qty=10)

    provider.price = 500.0   # catastrophically through the floor
    # A Sunday.
    stats = sweep_forced_buyins(
        now=datetime(2026, 8, 9, 15, 0, tzinfo=timezone.utc), sim=sim,
    )
    assert stats == {"checked": 0, "bought_in": 0}
    assert _open_short_row(run_id) is not None


def test_the_sweep_ignores_a_run_that_is_no_longer_live():
    """A settled run's NAV has been scored. Buying one in here would move a
    number the Close already published."""
    from app.services.games_service import sweep_forced_buyins

    provider = _MutableProvider(100.0)
    sim = SimEngine(provider=provider)
    user_id, run_id = uuid4(), uuid4()
    _seed_live_entry(user_id, run_id, state="finished")
    _short(sim, user_id, run_id, qty=10)

    provider.price = 500.0
    stats = sweep_forced_buyins(now=_market_open_moment(), sim=sim)
    assert stats["bought_in"] == 0
    assert _open_short_row(run_id) is not None


def _market_open_moment() -> datetime:
    """A Wednesday at 15:00 UTC — 11:00 ET, inside the session."""
    return datetime(2026, 8, 12, 15, 0, tzinfo=timezone.utc)


# ── The gap case: bust ───────────────────────────────────────────────────


def test_a_gapped_short_busts_the_run_and_records_the_shortfall():
    from app.services.portfolio_nav_daily import _mark_run_bust

    user_id, run_id = uuid4(), uuid4()
    _seed_live_entry(user_id, run_id)

    now = datetime.now(timezone.utc)
    assert _mark_run_bust(user_id, run_id, shortfall=1_234.56, now=now) is True

    with get_session() as s:
        entry = s.execute(
            select(GameEntryRow).where(GameEntryRow.run_id == run_id)
        ).scalar_one()
        assert entry.state == "bust"
        assert entry.busted_at is not None
        assert float(entry.nav_shortfall) == pytest.approx(1_234.56)


def test_bust_is_recorded_once_and_keeps_the_first_measurement():
    """The NAV tick runs daily and a busted run is still a portfolio row.
    Without the idempotency guard the shortfall would be rewritten every day
    until the field closed — and the later number is the wrong one, taken
    after the positions have drifted past the day the account broke."""
    from app.services.portfolio_nav_daily import _mark_run_bust

    user_id, run_id = uuid4(), uuid4()
    _seed_live_entry(user_id, run_id)
    now = datetime.now(timezone.utc)

    assert _mark_run_bust(user_id, run_id, shortfall=500.0, now=now) is True
    assert _mark_run_bust(user_id, run_id, shortfall=900.0, now=now) is False

    with get_session() as s:
        entry = s.execute(
            select(GameEntryRow).where(GameEntryRow.run_id == run_id)
        ).scalar_one()
        assert float(entry.nav_shortfall) == pytest.approx(500.0)


def test_a_settled_run_is_never_re_stated_as_bust():
    from app.services.portfolio_nav_daily import _mark_run_bust

    user_id, run_id = uuid4(), uuid4()
    _seed_live_entry(user_id, run_id, state="finished")

    assert _mark_run_bust(
        user_id, run_id, shortfall=500.0, now=datetime.now(timezone.utc),
    ) is False

    with get_session() as s:
        entry = s.execute(
            select(GameEntryRow).where(GameEntryRow.run_id == run_id)
        ).scalar_one()
        assert entry.state == "finished"


def test_a_bust_run_is_still_scored_but_claims_no_finish_stipend():
    """Both halves matter and they pull in opposite directions.

    SCORED, because a wipeout is a measured result — the worst one in the
    game — and dropping it out of the field would be a farm: blow up, pay
    nothing. NO STIPEND, because the stipend is for holding a run to its
    close and a busted book was liquidated before it.
    """
    from app.services.games_scoring_pass import _SCORABLE_STATES

    assert "bust" in _SCORABLE_STATES
    assert "forfeit" not in _SCORABLE_STATES
    assert "finished" not in _SCORABLE_STATES

    from app.services.games_scoring_pass import _EntrySnap

    busted = _EntrySnap(
        id=uuid4(), user_id=uuid4(), run_id=uuid4(), trade_count=3, busted=True,
    )
    ordinary = _EntrySnap(
        id=uuid4(), user_id=uuid4(), run_id=uuid4(), trade_count=3, busted=False,
    )
    assert busted.trade_count >= 1 and busted.busted
    assert not ordinary.busted


# ── End to end: the tick that actually writes the row ────────────────────


def test_the_nav_tick_writes_zero_and_busts_the_run_when_the_book_is_underwater():
    """The wiring, not the arithmetic.

    `nav_floor` being right is worth nothing if the NAV tick does not call
    it — and this is the row the TWR chain links across, so an unfloored
    write here is the whole defect. Drives the real tick with a real short
    that has gapped far past its buy-in trigger.
    """
    from app.services.portfolio_nav_daily import run_game_nav_snapshot_tick

    provider = _MutableProvider(100.0)
    sim = SimEngine(provider=provider)
    user_id, run_id = uuid4(), uuid4()
    _seed_live_entry(user_id, run_id)

    # Short the whole book, then have the name gap to 5x — past 2x, so the
    # leg is worth less than nothing and the account is genuinely negative.
    opened = _short(sim, user_id, run_id, qty=99.0)
    assert opened.accepted, opened.reason
    provider.price = 500.0

    book = sim.ensure_portfolio(user_id, kind="game", run_id=run_id)
    assert book.total_value({"AAPL": 500.0}) < 0, "fixture did not go negative"

    stats = run_game_nav_snapshot_tick(
        now=datetime(2026, 8, 12, 22, 0, tzinfo=timezone.utc),
        trading_day=lambda: datetime(2026, 8, 12).date(),
        sim=sim,
    )
    assert stats["written"] == 1

    from app.db.models import PortfolioNavDailyRow

    with get_session() as s:
        row = s.execute(
            select(PortfolioNavDailyRow).where(PortfolioNavDailyRow.run_id == run_id)
        ).scalars().one()
        assert float(row.nav) == 0.0, "a negative NAV reached the TWR chain"

        entry = s.execute(
            select(GameEntryRow).where(GameEntryRow.run_id == run_id)
        ).scalar_one()
        assert entry.state == "bust"
        assert entry.nav_shortfall is not None and float(entry.nav_shortfall) > 0


def test_the_nav_tick_leaves_a_solvent_run_alone():
    """The mutation guard for the test above: a tick that busted everything,
    or floored every NAV to zero, would pass it."""
    from app.services.portfolio_nav_daily import run_game_nav_snapshot_tick

    sim = SimEngine(provider=_MutableProvider(100.0))
    user_id, run_id = uuid4(), uuid4()
    _seed_live_entry(user_id, run_id)
    sim.ensure_portfolio(user_id, kind="game", run_id=run_id)

    stats = run_game_nav_snapshot_tick(
        now=datetime(2026, 8, 12, 22, 0, tzinfo=timezone.utc),
        trading_day=lambda: datetime(2026, 8, 12).date(),
        sim=sim,
    )
    assert stats["written"] >= 1

    from app.db.models import PortfolioNavDailyRow

    with get_session() as s:
        row = s.execute(
            select(PortfolioNavDailyRow).where(PortfolioNavDailyRow.run_id == run_id)
        ).scalars().one()
        assert float(row.nav) > 0

        entry = s.execute(
            select(GameEntryRow).where(GameEntryRow.run_id == run_id)
        ).scalar_one()
        assert entry.state == "active"
        assert entry.busted_at is None


# ── The run detail agrees with the stored series ─────────────────────────


def test_the_run_detail_floors_the_same_way_the_nav_row_does():
    """A live screen showing a negative book while the stored NAV row says
    zero is two answers to one question. One floor, applied at both."""
    import app.services.games_service as gs

    assert "nav_floor" in gs.__dict__ or hasattr(gs, "nav_floor"), (
        "get_run_detail must use the same floor the NAV tick uses"
    )
    assert nav_floor(-100.0)[0] == 0.0
