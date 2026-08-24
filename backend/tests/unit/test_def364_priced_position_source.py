"""DEF364 — a NAV day must not claim "no price" when a price moved it.

`_price_source_for_snapshot` overrides the price source to `cash` on a book
with no positions, and it is right to: an empty book's NAV *is* cash, exactly
known, and labelling it `mock` once VOIDed nearly every queue-first game run.

The bug was the guard condition, not the override. It counted `holdings` alone,
and `_marked_tickers` has included `p.shorts` since CR171 while CR172 §11 adds
options. A book with no holdings and one open short therefore had a NAV that
moved with a real price — `Portfolio.total_value`'s short term reads
`marks.get(s.ticker, s.entry_price)` — and reported no price at all.
`games_scoring_pass` voids a run on `price_source == "mock"` and nothing else,
so such a run was **scored on a fabricated price** instead of voided.

The fence is `_priced_position_count`, and the reason it is derived from
`_marked_tickers` rather than hand-listing the position types is this defect:
`holdings` was the complete list when the line was written, and stayed the
written list through two more position types arriving.
"""

from __future__ import annotations

import datetime
from uuid import uuid4

from app.schemas.trade import Holding, OptionLeg, Portfolio, ShortLeg
from app.services.portfolio_nav_daily import (
    _price_source_for_snapshot,
    _priced_position_count,
)

NOW = datetime.datetime(2026, 8, 24, tzinfo=datetime.timezone.utc)


def _portfolio(*, holdings=(), shorts=(), options=()) -> Portfolio:
    return Portfolio(
        id=uuid4(), user_id=uuid4(), current_cash=10_000.0,
        holdings=list(holdings), shorts=list(shorts), options=list(options),
        created_at=NOW,
    )


def _holding() -> Holding:
    return Holding(ticker="AAPL", quantity=10.0, avg_cost=190.0, opened_at=NOW)


def _short() -> ShortLeg:
    return ShortLeg(
        id=uuid4(),
        ticker="TSLA", quantity=10.0, entry_price=250.0, cash_posted=1250.0,
        opened_at=NOW,
    )


def _option() -> OptionLeg:
    return OptionLeg(
        id=uuid4(), occ_symbol="AAPL261007C00195000", underlying="AAPL",
        right="call", strike=195.0, expiry=datetime.date(2026, 10, 7),
        quantity=1.0, avg_premium=9.1, multiplier=100.0,
        collateral_posted=0.0, strategy_id=uuid4(), strategy_name="long_call",
        opened_at=NOW, days_to_expiry=44,
    )


# ── the defect ──────────────────────────────────────────────────────────────

def test_a_short_only_book_reports_the_price_that_moved_it():
    """THE defect. Before the fix this returned `cash`, and a mock-priced
    short-only game run was scored rather than voided."""
    p = _portfolio(shorts=[_short()])
    assert _priced_position_count(p) == 1
    assert _price_source_for_snapshot(
        "mock_walk", priced_position_count=_priced_position_count(p),
    ) == "mock"


def test_an_option_only_book_reports_the_price_that_moved_it():
    """The same hole CR172 §11 would have fallen into: a book whose only
    position is a structure is mark-dependent too."""
    p = _portfolio(options=[_option()])
    assert _priced_position_count(p) == 1
    assert _price_source_for_snapshot(
        "mock_walk", priced_position_count=_priced_position_count(p),
    ) == "mock"


def test_a_genuinely_empty_book_still_reads_cash():
    """The override that was correct stays correct — this is the queue-first
    day whose NAV is exactly known, and calling it `mock` VOIDs a run the
    player did nothing wrong in."""
    p = _portfolio()
    assert _priced_position_count(p) == 0
    assert _price_source_for_snapshot(
        "mock_walk", priced_position_count=_priced_position_count(p),
    ) == "cash"


def test_every_position_type_counts_and_they_sum():
    p = _portfolio(holdings=[_holding()], shorts=[_short()], options=[_option()])
    assert _priced_position_count(p) == 3


def test_the_counter_tracks_marked_tickers_rather_than_a_hand_list():
    """The fence, stated as a test.

    If a future position type is added to `_marked_tickers` — the set
    `portfolio_marks_snapshot` actually fetches quotes for — the counter must
    see it without anyone remembering to edit this module. Options are the one
    marked set that lives outside `_marked_tickers` (they key on `occ_symbol`,
    not a ticker), which is why they are added explicitly and why that is the
    only explicit term allowed here.
    """
    from app.services.sim_engine import _marked_tickers

    p = _portfolio(holdings=[_holding()], shorts=[_short()], options=[_option()])
    assert _priced_position_count(p) == len(_marked_tickers(p)) + len(p.options)


# ── the normalisation it feeds, unchanged ───────────────────────────────────

def test_a_real_source_on_a_real_position_reads_live():
    p = _portfolio(holdings=[_holding()])
    assert _price_source_for_snapshot(
        "yfinance", priced_position_count=_priced_position_count(p),
    ) == "live"


def test_an_unavailable_source_reads_stale_not_mock():
    """CR172 §11 leans on this: an option that could not be marked degrades to
    `unavailable`, which must read `stale` — some price served, just not one
    this round confirmed — leaving `mock` to keep meaning fabricated."""
    p = _portfolio(options=[_option()])
    assert _price_source_for_snapshot(
        "unavailable", priced_position_count=_priced_position_count(p),
    ) == "stale"
