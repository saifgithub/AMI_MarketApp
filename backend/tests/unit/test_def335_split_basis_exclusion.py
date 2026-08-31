"""DEF335 — a ticker that split after the as-of date must leave the universe.

Bars are downloaded with `auto_adjust=True`, so a bar stored for date X carries
every split between X and the download. The share count `edgar_pit` pairs it
with is the dei cover-page figure **as filed on X** — pre-split. So
`market_cap = adj_close × shares` is wrong by the product of those splits, and
with it `price_to_sales`, `fcf_yield`, `ev_to_ebitda`, `dividend_yield`,
`buyback_yield` and `pe`. For BKNG (25:1) at a 2025 as-of date the sheet prices
a $5,000 stock at ~$200 and computes a market cap 25× too small.

**This exclusion was recorded as "applied now" and was never implemented.**
Measured 2026-08-27 against Alpha: all 150 `backtest_universe_membership` rows
carried a NULL `exclusion_reason`, and `audit_ticker` derived its reason from
exactly three conditions — `insufficient_candles`, `listed_after_asof`,
`delisted_in_window` — none of which is a split. BKNG therefore sat eligible
across the whole window, which is how a **141.5% FCF yield** reached a published
verdict in `runs_r70-paired-1.jsonl`, where the PM rationalised it as *"a
valuation artifact of the depressed price"* rather than refusing it. A defect
row asserting a mitigation in the past tense, with nothing behind it, is the
same shape as DEF379's registry claiming a guard that did not exist.

The rule this file pins:

* a split in the window excludes the ticker, **whatever its candle coverage** —
  complete contiguous bars say nothing about the two bases agreeing;
* the cutoff is the **last** split, not the first, because a bar is adjusted for
  every split after it (HON split twice: 2025-10-30 and 2026-06-29);
* a provider failure returns no splits, which reads as clean — stated in the
  code and asserted here, because it is the one direction this can be wrong.
"""

from __future__ import annotations

import importlib.util
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import BacktestUniverseMembershipRow, PriceHistoryDailyRow

_SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts" / "backfill_price_history.py"
)

WINDOW_START = date(2025, 2, 28)
WINDOW_END = date(2026, 8, 1)


@pytest.fixture(scope="module")
def bf():
    spec = importlib.util.spec_from_file_location("_bf_def335", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _store_full_coverage(ticker: str) -> None:
    """Bars spanning the whole window, so no coverage rule can fire and only
    the split rule can explain an exclusion."""
    with get_session() as s:
        # Past WINDOW_END deliberately: the audit's `delisted_in_window` rule
        # fires when the last bar precedes the window end, and WINDOW_END lands
        # on a weekend. Without this the coverage rule pre-empts the split rule
        # and these tests would pass for the wrong reason.
        d = WINDOW_START
        while d <= WINDOW_END + timedelta(days=7):
            if d.weekday() < 5:
                s.add(PriceHistoryDailyRow(
                    ticker=ticker, date=d, close=100.0, adj_close=100.0,
                    source="yfinance",
                ))
            d += timedelta(days=1)


def _reason_for(bf, ticker: str, splits) -> tuple[str | None, date | None]:
    with get_session() as s:
        # `end` (the bar-selection bound) is deliberately later than
        # `window_end` (the coverage bound): the audit selects bars <= end and
        # then asks whether the last one reaches window_end, so passing the same
        # date for both guarantees `delisted_in_window` and would mask the rule
        # under test.
        reason = bf.audit_ticker(
            s, "def335-universe", ticker,
            WINDOW_START, WINDOW_END + timedelta(days=7),
            WINDOW_START, WINDOW_END,
            split_dates=splits,
        )
    with get_session() as s:
        row = s.execute(
            select(BacktestUniverseMembershipRow).where(
                BacktestUniverseMembershipRow.universe_id == "def335-universe",
                BacktestUniverseMembershipRow.ticker == ticker,
            )
        ).scalar_one()
        return reason, row.eligible_from


def test_the_audit_still_has_the_coverage_rules_this_one_sits_beside(bf):
    """Vacuity: if `audit_ticker` stopped classifying entirely, every assertion
    below about a split reason would still need the other reasons to exist to
    prove the split rule is doing distinct work."""
    src = _SCRIPT.read_text(encoding="utf-8")
    for reason in ("insufficient_candles", "listed_after_asof", "delisted_in_window"):
        assert reason in src, f"{reason} vanished — the audit changed shape"
    assert "split_after_as_of" in src


def test_a_split_in_the_window_excludes_a_fully_covered_ticker(bf):
    """The heart of it: complete bars, and still unusable."""
    _store_full_coverage("DEF335A")
    reason, eligible_from = _reason_for(bf, "DEF335A", [date(2026, 4, 6)])
    assert reason == "split_after_as_of", (
        "a ticker with full candle coverage that split mid-window was cleared — "
        "coverage says nothing about the price and share bases agreeing"
    )
    assert eligible_from == date(2026, 4, 6)


def test_the_cutoff_is_the_last_split_not_the_first(bf):
    """HON's real case. A bar is adjusted for EVERY split after it, so the
    mismatch survives the first one."""
    _store_full_coverage("DEF335B")
    reason, eligible_from = _reason_for(
        bf, "DEF335B", [date(2025, 10, 30), date(2026, 6, 29)]
    )
    assert reason == "split_after_as_of"
    assert eligible_from == date(2026, 6, 29), (
        "eligible_from was set to the first split; a bar between the two is "
        "still adjusted for the second and still mismatched"
    )


def test_a_ticker_with_no_split_is_left_clean(bf):
    """Non-vacuity. A rule that excluded everything would satisfy every
    assertion above and empty the backtest universe."""
    _store_full_coverage("DEF335C")
    reason, _ = _reason_for(bf, "DEF335C", [])
    assert reason is None, f"a split-free, fully-covered ticker was excluded as {reason!r}"


def test_splits_outside_the_window_do_not_exclude(bf, monkeypatch):
    """`splits_in_window` filters by the window; a split before it has already
    been applied to both bases and cancels.

    Asserted against the function's OUTPUT, not its docstring. This used to
    read `splits_in_window.__doc__` for the phrase "hand-listed" — which is a
    test of prose: it passes on any implementation that keeps the sentence and
    fails on any refactor that moves it, in neither case having looked at what
    the function returns.
    """
    monkeypatch.setattr(
        bf, "fetch_splits",
        lambda ticker: [
            (WINDOW_START - timedelta(days=30), 2.0),   # before the window
            (date(2026, 4, 6), 25.0),                   # inside it
            (WINDOW_END + timedelta(days=30), 3.0),     # after it
        ],
    )
    assert bf.splits_in_window("DEF335D", WINDOW_START, WINDOW_END) == [date(2026, 4, 6)]

    _store_full_coverage("DEF335D")
    reason, _ = _reason_for(bf, "DEF335D", [])
    assert reason is None


def test_a_split_beats_the_coverage_rules_rather_than_being_masked_by_them(bf):
    """Ordering matters: a thin-but-split ticker must report the split, because
    that is the reason a reader has to act on — refilling candles would not make
    it usable."""
    with get_session() as s:
        s.add(PriceHistoryDailyRow(
            ticker="DEF335E", date=WINDOW_START, close=100.0,
            adj_close=100.0, source="yfinance",
        ))
    reason, _ = _reason_for(bf, "DEF335E", [date(2026, 4, 6)])
    assert reason == "split_after_as_of", (
        f"reported {reason!r} — a reader told 'insufficient_candles' would "
        "backfill more bars and still have a wrong market cap"
    )
