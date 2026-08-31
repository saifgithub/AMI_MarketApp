"""DEF335 — the share count must be restated onto the price store's basis.

**What this file exists to stop, and why the previous answer was wrong.**

`fetch_pit_fundamentals` computes `market_cap = adj_close × shares`, where the
price is a stored bar and `shares` is the dei cover-page count **as filed**. The
stored bars are split-adjusted through the day they were downloaded; the filed
count predates every split since. The product is therefore in neither unit, and
for BKNG (25:1) at a 2025 as-of date it is 25× too small — which is how a 141.5%
FCF yield reached a published verdict in `runs_r70-paired-1.jsonl` with the PM
rationalising it as *"a valuation artifact of the depressed price"*.

DEF335 prescribed a different fix, twice, in its own row: re-backfill
`price_history_daily` with `auto_adjust=False` so `close` would carry an
as-traded quote. **Measured 2026-08-31 against yfinance 1.3.0, that flag does
not do that.** The OHLC series is split-adjusted in BOTH modes; `auto_adjust`
withholds only the DIVIDEND adjustment. Unadjusted close across each split:

    BKNG  2026-04-06  25:1   167.77 -> 176.19   ratio 0.952   (25 if unadjusted)
    NFLX  2025-11-17  10:1   111.22 -> 110.29   ratio 1.008   (10 if unadjusted)
    NOW   2025-12-18   5:1   156.48 -> 153.38   ratio 1.020   ( 5 if unadjusted)

Executing that fix would have rewritten 119,311 live rows across 201 tickers,
moved `close` by the ~0.7% dividend factor, and left the error exactly in place
while reporting success. So the price basis cannot move and the share basis
moves to meet it.

The three things that make the restatement correct rather than merely present,
each pinned below because each has a failure mode that produces a plausible
wrong number rather than an error:

1. the anchor is the share FACT's `period_end`, not `as_of` — a split between
   the filing and `as_of` already makes the filed count stale at `as_of`;
2. the cutoff is the bars' own download stamp, not today — a split after the
   last backfill is not in the stored prices, and applying it anyway
   over-corrects by the whole factor (25×, not 1%);
3. the correction lands once, on `shares`, so every field downstream reads one
   basis and the sheet still divides into itself (DEF302).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.db import get_session
from app.db.models import EdgarFactRow, PriceHistoryDailyRow, TickerSplitRow
from app.services.edgar_pit import fetch_pit_fundamentals
from app.services.ticker_splits import (
    get_asof_bars_basis_date,
    get_splits,
    split_factor,
    upsert_splits,
)

_TICKER = "DEF335S"
_AS_OF = date(2025, 6, 6)
_SHARES_STATED_AT = date(2025, 3, 31)
_DOWNLOADED = datetime(2026, 8, 19, tzinfo=timezone.utc)
_DOWNLOAD_DAY = _DOWNLOADED.date()

_M = 1_000_000.0
_PRICE_AT_AS_OF = 200.0
_SHARES_AS_FILED = 33.0 * _M   # BKNG-shaped: a pre-25:1 count
_SPLIT_DAY = date(2026, 4, 6)
_SPLIT_RATIO = 25.0


def _seed_price_bars(ticker: str = _TICKER, *, fetched_at: datetime = _DOWNLOADED) -> None:
    """260 sessions ending on the as-of date, closing at `_PRICE_AT_AS_OF`.

    Flat, deliberately: this file is about the share basis, and a moving series
    would let a wrong figure hide inside a plausible range.
    """
    d, made = _AS_OF, []
    while len(made) < 260:
        if d.weekday() < 5:
            made.append(d)
        d = date.fromordinal(d.toordinal() - 1)
    with get_session() as s:
        for bar_date in reversed(made):
            s.add(PriceHistoryDailyRow(
                ticker=ticker, date=bar_date,
                close=_PRICE_AT_AS_OF, adj_close=_PRICE_AT_AS_OF,
                open=_PRICE_AT_AS_OF, high=_PRICE_AT_AS_OF, low=_PRICE_AT_AS_OF,
                volume=1_000_000, source="yfinance_backfill", fetched_at=fetched_at,
            ))


def _seed_facts() -> None:
    """The minimum that makes a market cap and the ratios built on it."""
    quarter_ends = [
        date(2023, 6, 30), date(2023, 9, 30), date(2023, 12, 31),
        date(2024, 3, 31), date(2024, 6, 30), date(2024, 9, 30),
        date(2024, 12, 31), date(2025, 3, 31),
    ]
    with get_session() as s:
        for i, end in enumerate(quarter_ends):
            start = date(2023, 4, 1) if i == 0 else quarter_ends[i - 1] + timedelta(days=1)
            for tag, per_q in (
                ("Revenues", 1_000.0 * _M),
                ("NetIncomeLoss", 100.0 * _M),
            ):
                s.add(EdgarFactRow(
                    cik=1, ticker=_TICKER, taxonomy="us-gaap", tag=tag, unit="USD",
                    value=per_q, period_start=start, period_end=end,
                    filed=end + timedelta(days=40), accession_no=f"{tag}-{end}",
                    ingested_at=_DOWNLOADED,
                ))
        s.add(EdgarFactRow(
            cik=1, ticker=_TICKER, taxonomy="dei", unit="shares",
            tag="EntityCommonStockSharesOutstanding", value=_SHARES_AS_FILED,
            period_start=None, period_end=_SHARES_STATED_AT, filed=date(2025, 5, 10),
            accession_no="dei-1", ingested_at=_DOWNLOADED,
        ))


def _store_split(ex_date: date, ratio: float, ticker: str = _TICKER) -> None:
    with get_session() as s:
        s.add(TickerSplitRow(
            ticker=ticker, ex_date=ex_date, ratio=ratio,
            source="yfinance_backfill", fetched_at=_DOWNLOADED,
        ))


@pytest.fixture
def filer() -> None:
    _seed_price_bars()
    _seed_facts()


# ── split_factor: the two bounds, each of which can silently mis-price ───────


def test_a_split_after_the_filing_and_before_the_download_is_applied() -> None:
    _store_split(_SPLIT_DAY, _SPLIT_RATIO)
    assert split_factor(_TICKER, after=_SHARES_STATED_AT, until=_DOWNLOAD_DAY) == 25.0


def test_a_split_after_the_download_is_NOT_applied() -> None:
    """The over-correction case, and the expensive one.

    Bars are adjusted only up to the moment they were downloaded. Anchoring the
    upper bound on `date.today()` instead would apply a split the stored prices
    have never seen and inflate the share count 25×, in the same direction and
    the same magnitude as the bug being fixed.
    """
    _store_split(_DOWNLOAD_DAY + timedelta(days=1), _SPLIT_RATIO)
    assert split_factor(_TICKER, after=_SHARES_STATED_AT, until=_DOWNLOAD_DAY) == 1.0


def test_a_split_on_the_download_day_is_applied() -> None:
    """The upper bound is inclusive: a split on the day of the download is in
    what was downloaded."""
    _store_split(_DOWNLOAD_DAY, _SPLIT_RATIO)
    assert split_factor(_TICKER, after=_SHARES_STATED_AT, until=_DOWNLOAD_DAY) == 25.0


def test_a_split_between_the_filing_and_the_as_of_date_is_applied(filer) -> None:
    """The anchor is the FACT's date, not `as_of`.

    A split on 2025-05-01 sits after the 2025-03-31 cover-page count and before
    the 2025-06-06 as-of date, so the filed count is already stale by the time
    the sheet is drawn. Anchoring on `as_of` would skip it and leave the sheet
    25× wrong while every other test in this file still passed.
    """
    _store_split(date(2025, 5, 1), _SPLIT_RATIO)
    assert split_factor(_TICKER, after=_SHARES_STATED_AT, until=_DOWNLOAD_DAY) == 25.0
    sheet = fetch_pit_fundamentals(_TICKER, _AS_OF)
    assert sheet is not None
    assert sheet["market_cap"] == pytest.approx(165_000, rel=1e-6)


def test_a_split_before_the_filing_is_NOT_applied() -> None:
    """Under the filing date both bases already agree — the count was stated
    after the split, so applying it again would double-count."""
    _store_split(_SHARES_STATED_AT - timedelta(days=1), _SPLIT_RATIO)
    assert split_factor(_TICKER, after=_SHARES_STATED_AT, until=_DOWNLOAD_DAY) == 1.0


def test_a_split_on_the_filing_date_is_NOT_applied() -> None:
    """The lower bound is exclusive: a count stated as of the ex-date is taken
    to already reflect it. That is the direction that cannot double-apply."""
    _store_split(_SHARES_STATED_AT, _SPLIT_RATIO)
    assert split_factor(_TICKER, after=_SHARES_STATED_AT, until=_DOWNLOAD_DAY) == 1.0


def test_two_splits_in_the_window_compound() -> None:
    """HON split twice (2025-10-30 and 2026-06-29). A bar is adjusted for every
    split after it, so the factor is the product, not the latest."""
    _store_split(date(2025, 10, 30), 2.0)
    _store_split(date(2026, 6, 29), 3.0)
    assert split_factor(_TICKER, after=_SHARES_STATED_AT, until=_DOWNLOAD_DAY) == 6.0


def test_a_reverse_split_shrinks_the_count() -> None:
    """LCID went 1:10. A rule that only ever multiplies up would leave this one
    ten times too large and read as fixed."""
    _store_split(date(2025, 9, 2), 0.1)
    assert split_factor(_TICKER, after=_SHARES_STATED_AT, until=_DOWNLOAD_DAY) == pytest.approx(0.1)


def test_no_stored_splits_is_exactly_todays_behaviour() -> None:
    """Non-vacuity, and the deployment property: until the backfill records
    anything, this cannot move a single number."""
    assert split_factor(_TICKER, after=_SHARES_STATED_AT, until=_DOWNLOAD_DAY) == 1.0


# ── the basis date comes from the bars, not the clock ────────────────────────


def test_the_basis_date_is_the_bars_download_stamp() -> None:
    _seed_price_bars()
    assert get_asof_bars_basis_date(_TICKER, _AS_OF) == _DOWNLOAD_DAY


def test_a_ticker_with_no_stored_bars_has_no_basis_date() -> None:
    """None, not today. A guessed basis date is a guessed split factor."""
    assert get_asof_bars_basis_date("NOSUCHTICKER", _AS_OF) is None


def test_mock_bars_do_not_set_the_basis_date() -> None:
    """Same exclusion `get_asof_daily_rows` applies: a fabricated bar must not
    decide the basis a real one is priced on."""
    with get_session() as s:
        s.add(PriceHistoryDailyRow(
            ticker="DEF335M", date=_AS_OF, close=1.0, adj_close=1.0,
            source="mock_walk", fetched_at=_DOWNLOADED,
        ))
    assert get_asof_bars_basis_date("DEF335M", _AS_OF) is None


# ── the defect itself, end to end on a fact sheet ────────────────────────────


def test_the_market_cap_is_no_longer_wrong_by_the_split_factor(filer) -> None:
    """The BKNG case. 33M filed shares against a $200 split-adjusted bar gives
    $6.6bn; the company is worth $165bn."""
    _store_split(_SPLIT_DAY, _SPLIT_RATIO)
    sheet = fetch_pit_fundamentals(_TICKER, _AS_OF)
    assert sheet is not None
    assert sheet["market_cap"] == pytest.approx(165_000, rel=1e-6), (
        "market cap is still on the filed share basis while the price is on the "
        "adjusted one — the mismatch this defect is"
    )
    assert sheet["shares_outstanding"] == pytest.approx(825, rel=1e-6)


def test_without_the_split_the_same_filer_is_untouched(filer) -> None:
    """Non-vacuity. A restatement that fired on every ticker would satisfy the
    test above and corrupt the other 142 names."""
    sheet = fetch_pit_fundamentals(_TICKER, _AS_OF)
    assert sheet is not None
    assert sheet["market_cap"] == pytest.approx(6_600, rel=1e-6)
    assert sheet["shares_outstanding"] == pytest.approx(33, rel=1e-6)


def test_a_split_after_the_download_does_not_reach_the_sheet(filer) -> None:
    """The over-correction guard, at the surface a reader actually sees."""
    _store_split(_DOWNLOAD_DAY + timedelta(days=1), _SPLIT_RATIO)
    sheet = fetch_pit_fundamentals(_TICKER, _AS_OF)
    assert sheet is not None
    assert sheet["market_cap"] == pytest.approx(6_600, rel=1e-6)


def test_the_sheet_still_divides_into_itself(filer) -> None:
    """DEF302's rule, which is what forces the correction to land ONCE on
    `shares` rather than per-field: a sheet carrying a restated market cap
    beside an unrestated EPS would print two numbers that do not divide into
    each other, and would pass a test that only looked at market cap.
    """
    _store_split(_SPLIT_DAY, _SPLIT_RATIO)
    sheet = fetch_pit_fundamentals(_TICKER, _AS_OF)
    assert sheet is not None

    implied_cap = sheet["base_price"] * sheet["shares_outstanding"]
    assert implied_cap == pytest.approx(sheet["market_cap"], rel=1e-3), (
        f"base_price × shares_outstanding = {implied_cap} but market_cap = "
        f"{sheet['market_cap']} — two bases on one sheet"
    )
    # `pe` divides by an unrounded EPS while `trailing_eps` is printed to 2dp,
    # so on a ~$0.48 EPS the two differ by ~1% from rounding alone. The
    # tolerance is set just outside that and nowhere near the 25× it exists to
    # catch — a basis mismatch misses by 2500%, not by 2%.
    assert float(sheet["pe"]) == pytest.approx(
        sheet["base_price"] / sheet["trailing_eps"], rel=2e-2,
    )
    assert float(sheet["price_to_sales"]) == pytest.approx(
        sheet["market_cap"] / sheet["revenue_ttm"], rel=1e-2,
    )


def test_the_restatement_is_declared_in_the_shares_basis(filer, monkeypatch) -> None:
    """A silently-corrected number is the same reading problem as a silently
    wrong one: the log has to say the basis moved, and by how much.

    Recorded off a stand-in logger rather than `capsys`/`caplog`. Both of those
    read a stream whose configuration other tests in the suite can change: this
    assertion passed on its own and failed inside the full run, which is the
    shape where a green test means "the capture was empty".
    """
    from app.services import edgar_pit as mod

    seen: list[dict] = []

    class _Recorder:
        def info(self, event, **kw):
            seen.append({"event": event, **kw})

        def warn(self, event, **kw):
            seen.append({"event": event, **kw})

    monkeypatch.setattr(mod, "logger", _Recorder())

    _store_split(_SPLIT_DAY, _SPLIT_RATIO)
    fetch_pit_fundamentals(_TICKER, _AS_OF)

    resolved = [e for e in seen if e["event"] == "pit_fundamentals_resolved"]
    assert resolved, f"no resolved log at all; got {[e['event'] for e in seen]}"
    assert resolved[-1]["shares_basis"] == "dei_cover_page+split_adj_25", (
        "the resolved-fundamentals log does not record that the share basis was "
        f"restated; got {resolved[-1]['shares_basis']!r}"
    )


# ── the write path ───────────────────────────────────────────────────────────


def test_upsert_is_idempotent_and_corrects_a_revised_ratio() -> None:
    with get_session() as s:
        first = upsert_splits(s, _TICKER, [(_SPLIT_DAY, 25.0)], source="yfinance_backfill")
    with get_session() as s:
        second = upsert_splits(s, _TICKER, [(_SPLIT_DAY, 20.0)], source="yfinance_backfill")
    assert (first["inserted"], second["inserted"], second["updated"]) == (1, 0, 1)
    assert get_splits(_TICKER) == [(_SPLIT_DAY, 20.0)]


def test_a_no_op_ratio_and_a_bad_print_are_refused() -> None:
    """1.0 is not a split, and a ratio of 1e9 is a bad print. Either stored
    would put a row in a table whose only meaning is 'the basis changed here'.
    """
    with get_session() as s:
        stats = upsert_splits(
            s, _TICKER,
            [(_SPLIT_DAY, 1.0), (date(2025, 1, 2), 1e9), (date(2025, 1, 3), 0.0)],
            source="yfinance_backfill",
        )
    assert stats["rejected"] == 3
    assert get_splits(_TICKER) == []


def test_a_duplicate_ex_date_inside_one_call_converges_to_an_update() -> None:
    """The P15 path, triggered deterministically.

    `upsert_splits` reads the existing rows once and then inserts, so a second
    pair for the same ex-date is absent from that snapshot and takes the INSERT
    branch into the unique constraint — the same collision two concurrent
    backfills produce, without needing two processes to reproduce it. The loser
    must converge to an update, and the surrounding rows must survive: an
    unhandled `IntegrityError` poisons the session and loses every other
    ticker's splits to one collision.
    """
    with get_session() as s:
        stats = upsert_splits(
            s, _TICKER,
            [(_SPLIT_DAY, 25.0), (_SPLIT_DAY, 20.0), (date(2025, 10, 30), 2.0)],
            source="yfinance_backfill",
        )
    assert (stats["inserted"], stats["updated"]) == (2, 1)
    assert get_splits(_TICKER) == [(date(2025, 10, 30), 2.0), (_SPLIT_DAY, 20.0)]
