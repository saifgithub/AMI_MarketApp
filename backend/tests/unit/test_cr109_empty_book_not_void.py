"""A day with no holdings must not VOID a run — CR109, found on live Alpha.

Two rules, each correct on its own, composed into a defect:

1. `SimEngine.aggregate_source([])` returns `mock_walk` for an empty ticker
   list. Correct for its own job — the LIVE pill must not light up when
   nothing has been priced.
2. `games_scoring_pass` VOIDs any run whose NAV series contains a `mock` day.
   Also correct — a fabricated price must never produce a real score.

Chained, they VOIDed essentially every run. **Queue-first is the PRIMARY
designed flow** (US hours are evening in the Gulf and past midnight in
Malaysia): enter, queue an order that night, fill at the next open. The day
in between holds no positions, so it was stamped `mock`, so the run was void
before it began — the player having done everything right.

The unit suite could not see it: every scoring fixture already had holdings,
so nothing ever exercised an empty book. It surfaced only on a live
end-to-end run against Alpha. That is the whole reason this file exists —
the composition of two individually-tested behaviours is itself untested
until something exercises the seam.

`cash` is the honest fourth value: NAV is cash, cash is exactly known, and no
price was involved. It is not a caveat and must not be scored as one.
"""

from __future__ import annotations

from app.services.portfolio_nav_daily import (
    _normalize_price_source,
    _price_source_for_snapshot,
)


def test_empty_book_reads_cash_not_mock() -> None:
    """The seam itself. `mock_walk` in, `cash` out, when nothing is held."""
    assert _price_source_for_snapshot("mock_walk", holding_count=0) == "cash"


def test_empty_book_is_cash_whatever_the_provider_said() -> None:
    """The holding count decides, not the provider string — an empty book was
    never priced, so no provider answer about it can be meaningful."""
    for raw in ("mock_walk", "yfinance", "yahoo", "unavailable", ""):
        assert _price_source_for_snapshot(raw, holding_count=0) == "cash"


def test_a_held_book_still_reports_its_real_provenance() -> None:
    """The fix must not become a blanket excuse: once anything is held, a
    mock-priced day is still `mock` and must still VOID. Losing that would
    trade one silent lie for a worse one."""
    assert _price_source_for_snapshot("mock_walk", holding_count=1) == "mock"
    assert _price_source_for_snapshot("yfinance", holding_count=1) == "live"
    assert _price_source_for_snapshot("unavailable", holding_count=2) == "stale"


def test_cash_is_not_in_the_void_vocabulary() -> None:
    """`games_scoring_pass` voids on `price_source == "mock"`. `cash` must not
    normalise into that bucket by any route."""
    assert _price_source_for_snapshot("mock_walk", holding_count=0) != "mock"
    # And the underlying normaliser is untouched — it still calls mock, mock.
    assert _normalize_price_source("mock_walk") == "mock"
