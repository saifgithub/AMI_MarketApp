"""Point-in-time fundamentals from stored EDGAR facts (CR164).

Resolves the same fundamentals dict `fetch_live_fundamentals` emits, but as
of a historical date, using only XBRL facts whose `filed` date is on or
before it — the filed date, not the period end, is what makes this
leakage-correct: a Q4 number filed in February did not exist in January.

Layering: `_FactView` + the resolvers are PURE (unit-testable on hand-built
fixtures, no DB); `load_facts` is the one DB touch; `fetch_pit_fundamentals`
composes them with the price store and the shared formatting helpers from
`fundamentals.py` / `trading_math.valuation`, so PIT figures render
byte-identically to live ones.

Staleness guards: a "latest" quarter older than ~200 days or a balance-sheet
point older than ~400 days at the as-of date is refused (absent, logged) —
a delisted or late-filing company must read as data-dark, not as frozen
year-old fundamentals with live provenance.

What is structurally NOT reconstructable here and therefore never emitted:
forward P/E, PEG, analyst target/rating (consensus estimates), next-earnings
(a forward calendar). Sector/industry are also omitted in v1 — there is no
PIT classification source wired. All of these flow to the CR104 UNAVAILABLE
rendering at the profile layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Sequence

from sqlalchemy import select

from app.core.logging import logger
from app.db import get_session
from app.db.models import EdgarFactRow
from app.services import edgar_tags
from app.services.asof_context import assert_dates_within

# A duration fact spanning roughly a quarter / a fiscal year.
_QUARTER_SPAN = (70, 100)
_ANNUAL_SPAN = (330, 380)

# Staleness bounds (days) — see module docstring.
MAX_QUARTER_AGE_DAYS = 200
MAX_INSTANT_AGE_DAYS = 400


@dataclass(frozen=True)
class _FactView:
    """One stored fact, decoupled from the ORM row so resolvers stay pure."""

    tag: str
    value: float
    period_start: date | None
    period_end: date
    filed: date


def load_facts(ticker: str, tags: Sequence[str], as_of: date) -> list[_FactView]:
    """All stored facts for `ticker` under `tags` with `filed <= as_of`.

    The filed-date cutoff is applied in SQL AND re-asserted after the query
    (guard (a)) — the whole PIT property rides on this one WHERE clause.
    """
    stmt = (
        select(EdgarFactRow)
        .where(EdgarFactRow.ticker == ticker.upper().strip())
        .where(EdgarFactRow.tag.in_(list(tags)))
        .where(EdgarFactRow.filed <= as_of)
    )
    with get_session() as session:
        rows = session.execute(stmt).scalars().all()
    assert_dates_within([r.filed for r in rows], as_of, origin="edgar_pit.load_facts")
    return [
        _FactView(
            tag=r.tag,
            value=float(r.value),
            period_start=r.period_start,
            period_end=r.period_end,
            filed=r.filed,
        )
        for r in rows
    ]


# ── Pure resolvers ──────────────────────────────────────────────────────────


def resolve_instant_dated(
    facts: Sequence[_FactView], tags: Sequence[str], as_of: date,
    *, max_age_days: int = MAX_INSTANT_AGE_DAYS,
) -> tuple[float, date] | None:
    """`(value, period_end)` for the latest balance-sheet point of the FIRST
    tag that resolves.

    Within a tag: newest `period_end` wins, ties broken by newest `filed` —
    so a 10-K/A amendment naturally supersedes the original without any
    amendment-specific handling.

    The date half exists for DEF335: a share count has to be restated onto the
    price store's split basis, and the anchor for that is the date the count
    was STATED, not the as-of date — a split between the filing and `as_of`
    already makes the filed count stale at `as_of`.
    """
    for tag in tags:
        candidates = [f for f in facts if f.tag == tag]
        if not candidates:
            continue
        best = max(candidates, key=lambda f: (f.period_end, f.filed))
        if (as_of - best.period_end).days > max_age_days:
            return None
        return best.value, best.period_end
    return None


def resolve_instant(
    facts: Sequence[_FactView], tags: Sequence[str], as_of: date,
    *, max_age_days: int = MAX_INSTANT_AGE_DAYS,
) -> float | None:
    """The value half of `resolve_instant_dated` — every caller that does not
    need the basis anchor."""
    hit = resolve_instant_dated(facts, tags, as_of, max_age_days=max_age_days)
    return hit[0] if hit is not None else None


def quarterly_series(
    facts: Sequence[_FactView], tags: Sequence[str],
) -> list[tuple[date, date, float]]:
    """Discrete quarters for the first tag that has any, ascending by period_end.

    **Most filers do not report discrete quarters.** They report CUMULATIVE
    year-to-date durations sharing one fiscal-year start: P&G's `Revenues`
    arrives as (2025-07-01 → 09-30) 91d, (→ 12-31) 183d, (→ 03-31) 273d,
    (→ 06-30) 364d. Measured on the CR164 pilot corpus, keeping only
    quarter-length spans found exactly ONE quarter per fiscal year, so every
    TTM failed and P/E, P/S, FCF yield, EV/EBITDA and dividend yield resolved
    at 0% across 25 tickers.

    So: bucket the facts by `period_start`, sort each bucket by `period_end`,
    and difference consecutive entries — the first entry of a bucket is
    already discrete, each later one becomes (previous end + 1 day → its own
    end) with value `v_n − v_{n-1}`. That subsumes the old FY − (Q1+Q2+Q3)
    Q4 derivation and also handles filers who genuinely report discrete
    quarters (each lands in its own single-entry bucket).

    Only quarter-length results survive: a gap in the YTD chain produces a
    half-year-long difference, which is dropped rather than passed off as a
    quarter. Per (period_start, period_end) the latest-filed value wins, so a
    10-K/A restatement supersedes the original before any differencing.
    """
    tag = next((t for t in tags if any(f.tag == t for f in facts)), None)
    if tag is None:
        return []

    by_period: dict[tuple[date, date], _FactView] = {}
    for f in facts:
        if f.tag != tag or f.period_start is None:
            continue
        key = (f.period_start, f.period_end)
        if key not in by_period or f.filed > by_period[key].filed:
            by_period[key] = f

    buckets: dict[date, list[_FactView]] = {}
    for f in by_period.values():
        buckets.setdefault(f.period_start, []).append(f)

    quarters: dict[tuple[date, date], float] = {}
    for start, group in buckets.items():
        group.sort(key=lambda f: f.period_end)
        prev_end, prev_value = None, 0.0
        for f in group:
            q_start = start if prev_end is None else prev_end + timedelta(days=1)
            q_value = f.value - prev_value
            span = (f.period_end - q_start).days
            if _QUARTER_SPAN[0] <= span <= _QUARTER_SPAN[1]:
                quarters[(q_start, f.period_end)] = q_value
            prev_end, prev_value = f.period_end, f.value

    # The other real shape: three DISCRETE quarters (each with its own start,
    # so each sits in its own bucket and differencing has nothing to chain)
    # plus a fiscal-year total. Q4 = FY − (Q1+Q2+Q3). Skipped automatically
    # when differencing already produced the tail quarter, since `inside`
    # then holds four.
    for f in by_period.values():
        fy_span = (f.period_end - f.period_start).days
        if not (_ANNUAL_SPAN[0] <= fy_span <= _ANNUAL_SPAN[1]):
            continue
        inside = {
            (s, e): v for (s, e), v in quarters.items()
            if s >= f.period_start - timedelta(days=10)
            and e <= f.period_end + timedelta(days=10)
        }
        if len(inside) != 3:
            continue
        covered_ends = sorted(e for (_, e) in inside)
        if any(abs((e - f.period_end).days) <= 10 for e in covered_ends):
            continue  # the gap is mid-year, a rarer shape than v1 handles
        quarters[(max(covered_ends) + timedelta(days=1), f.period_end)] = (
            f.value - sum(inside.values())
        )

    return sorted(
        [(s, e, v) for (s, e), v in quarters.items()], key=lambda item: item[1]
    )


def ttm(
    series: list[tuple[date, date, float]], as_of: date,
    *, max_age_days: int = MAX_QUARTER_AGE_DAYS,
) -> float | None:
    """Sum of the last four quarters ending on or before `as_of`.

    None (loud at the caller) when fewer than four resolve, when the newest
    is stale, or when the four together span far more than a year — a hole
    in the middle would otherwise sum three quarters of one year with one of
    another and call it trailing-twelve-months.
    """
    eligible = [item for item in series if item[1] <= as_of]
    if len(eligible) < 4:
        return None
    last4 = eligible[-4:]
    if (as_of - last4[-1][1]).days > max_age_days:
        return None
    if (last4[-1][1] - last4[0][0]).days > 430:
        return None
    return sum(v for _, _, v in last4)


def yoy_quarter_pair(
    series: list[tuple[date, date, float]], as_of: date,
    *, max_age_days: int = MAX_QUARTER_AGE_DAYS,
) -> tuple[tuple[date, date, float], tuple[date, date, float]] | None:
    """The latest resolvable quarter and the same quarter a year earlier.

    One definition of "the same quarter a year earlier" for every YoY figure
    on the sheet — growth and each margin trend — so two fields can never
    disagree about which pair of quarters they compared.
    """
    eligible = [item for item in series if item[1] <= as_of]
    if not eligible:
        return None
    latest = eligible[-1]
    if (as_of - latest[1]).days > max_age_days:
        return None
    prior = [item for item in eligible if abs((latest[1] - item[1]).days - 365) <= 20]
    if not prior:
        return None
    return latest, prior[-1]


def yoy_quarter_growth(
    series: list[tuple[date, date, float]], as_of: date,
    *, max_age_days: int = MAX_QUARTER_AGE_DAYS,
) -> float | None:
    """Latest quarter vs the same quarter a year earlier, as a decimal ratio
    (0.05 = +5%) — the same definition yfinance's `revenueGrowth` carries, so
    the rendered field means the same thing on both paths."""
    pair = yoy_quarter_pair(series, as_of, max_age_days=max_age_days)
    if pair is None:
        return None
    latest, prior = pair
    base = prior[2]
    if base <= 0:
        return None
    return latest[2] / base - 1.0


def margin_trend_bps(
    numerator: list[tuple[date, date, float]],
    denominator: list[tuple[date, date, float]],
    as_of: date,
) -> tuple[int, str] | None:
    """Change in a quarterly margin, year over year, in basis points — plus
    the basis string naming the two quarters compared.

    The denominator quarter is matched on an EXACT `period_end`. A near-miss
    is refused rather than paired: dividing one quarter's income by a
    slightly different quarter's revenue produces a margin that belongs to
    neither, and it would look entirely plausible on the sheet.
    """
    pair = yoy_quarter_pair(numerator, as_of)
    if pair is None:
        return None
    latest, prior = pair
    by_end = {end: value for _, end, value in denominator}
    d_latest, d_prior = by_end.get(latest[1]), by_end.get(prior[1])
    if not d_latest or not d_prior or d_latest <= 0 or d_prior <= 0:
        return None
    bps = round(((latest[2] / d_latest) - (prior[2] / d_prior)) * 10_000)
    return bps, f"{latest[1].isoformat()} vs {prior[1].isoformat()}"


def instant_sum(
    facts: Sequence[_FactView],
    anchor_tags: Sequence[str],
    optional_tags: Sequence[str],
    as_of: date,
) -> float | None:
    """Anchor concept + whichever optional components resolve. None when the
    anchor itself is absent — "debt" must never resolve to just a short-term
    stub (see `edgar_tags`)."""
    anchor = resolve_instant(facts, anchor_tags, as_of)
    if anchor is None:
        return None
    total = anchor
    for tag in optional_tags:
        extra = resolve_instant(facts, (tag,), as_of)
        if extra is not None:
            total += extra
    return total


# ── Composition ─────────────────────────────────────────────────────────────


def fetch_pit_fundamentals(ticker: str, as_of: date) -> dict[str, Any] | None:
    """The `fetch_live_fundamentals` dict shape, as of `as_of`, from EDGAR
    facts + the price store. None when the ticker has no usable price row —
    the same "unknown ticker, caller falls through" contract as the live path.
    """
    from app.services.price_history import get_asof_daily_rows
    from app.services.ticker_splits import get_asof_bars_basis_date, split_factor
    from app.trading_math.valuation import (
        fcf_yield_pct,
        net_cash_millions,
        ratio_to_pct,
    )

    price_rows = get_asof_daily_rows(ticker, as_of, max_rows=252)
    if not price_rows:
        logger.warn("pit_fundamentals_no_price", ticker=ticker, as_of=as_of.isoformat())
        return None
    price = price_rows[-1][5]  # adj_close on the last bar <= as_of

    all_tags = tuple(edgar_tags.INGEST_TAGS_US_GAAP | edgar_tags.INGEST_TAGS_DEI)
    facts = load_facts(ticker, all_tags, as_of)

    out: dict[str, Any] = {
        "base_price": round(price, 2),
        # Same derived defaults as the live path; overwritten by the real
        # 252-bar range below (which always exists here — price_rows is
        # non-empty), kept for shape parity with `fetch_live_fundamentals`.
        "support": round(price * 0.9, 2),
        "breakout": round(price * 1.03, 2),
        "low": round(min(r[5] for r in price_rows), 2),
        "high": round(max(r[5] for r in price_rows), 2),
        # A trailing range measured from stored bars (up to 252 of them). Only
        # a full year of bars earns the "52-week" label the renderer applies.
        "week52_range_live": len(price_rows) >= 240,
    }

    ni_series = quarterly_series(facts, edgar_tags.NET_INCOME)
    rev_series = quarterly_series(facts, edgar_tags.REVENUE)
    ttm_ni = ttm(ni_series, as_of)
    ttm_rev = ttm(rev_series, as_of)

    # Share count for the market-cap basis. The dei cover-page fact is
    # preferred (a point-in-time count), but it does not resolve for every
    # filer at every as-of date — 3 of 27 pilot pairs, and each miss zeroes
    # FIVE downstream fields at once (P/E, P/S, FCF yield, EV/EBITDA,
    # dividend yield). The us-gaap weighted-average diluted count is the
    # honest fallback: a period average rather than a point count, so it is
    # tried second, never blended.
    dei = resolve_instant_dated(facts, edgar_tags.SHARES_OUTSTANDING_DEI, as_of)
    shares_basis = "dei_cover_page"
    shares: float | None = None
    shares_stated_at: date | None = None
    if dei is not None:
        shares, shares_stated_at = dei
    if not shares or shares <= 0:
        diluted = quarterly_series(facts, edgar_tags.DILUTED_SHARES)
        eligible = [(e, v) for _, e, v in diluted if e <= as_of]
        if eligible:
            shares_stated_at, shares = eligible[-1]
            shares_basis = "weighted_average_diluted"

    # DEF335 — restate the filed count onto the PRICE's basis before anything
    # is multiplied by it.
    #
    # `price` above is `adj_close`, and the store's bars are split-adjusted
    # through the day they were downloaded; the count resolved just now is the
    # figure as STATED on its filing, which predates every split since. The two
    # are different units, and `price * shares` silently produced a number in
    # neither — off by the product of the intervening splits. For BKNG (25:1)
    # at a 2025 as-of date that is a market cap 25x too small, and with it
    # `price_to_sales`, `fcf_yield`, `ev_to_ebitda`, `dividend_yield`,
    # `buyback_yield` and `pe`. It is how a 141.5% FCF yield reached a
    # published verdict in `runs_r70-paired-1.jsonl` with the PM explaining it
    # away as "a valuation artifact of the depressed price".
    #
    # The correction is applied ONCE, here, rather than per-field: every
    # consumer below (`market_cap`, `shares_outstanding`, `trailing_eps`,
    # `revenue_per_share`, `pe`) then reads one basis, so the sheet stays
    # self-reconciling — `base_price * shares_outstanding` equals `market_cap`
    # and `base_price / trailing_eps` equals `pe`, which is the DEF302
    # contradiction class.
    #
    # An empty `ticker_splits` table yields 1.0, i.e. exactly today's numbers:
    # this cannot change a ticker that has not split, and cannot fire at all
    # until the backfill has recorded some splits.
    split_adj = 1.0
    if shares and shares > 0 and shares_stated_at is not None:
        basis_date = get_asof_bars_basis_date(ticker, as_of)
        if basis_date is not None:
            split_adj = split_factor(ticker, after=shares_stated_at, until=basis_date)
            if split_adj != 1.0:
                shares = shares * split_adj
                shares_basis = f"{shares_basis}+split_adj_{split_adj:g}"

    market_cap = price * shares if shares and shares > 0 else None

    if market_cap is not None:
        out["market_cap"] = round(market_cap / 1_000_000)
    if shares and shares > 0:
        out["shares_outstanding"] = round(shares / 1_000_000)

    # EPS and revenue-per-share are derived from the SAME numerator and
    # denominator that `pe` and `price_to_sales` use, rather than from a
    # reported per-share tag. That keeps the sheet self-reconciling —
    # `base_price / trailing_eps` equals the printed `pe`, and
    # `market_cap / revenue_ttm` equals `price_to_sales`. A separately-based
    # reported EPS would put two figures on one sheet that do not divide into
    # each other, which is the class of contradiction DEF302 exists to close.
    if ttm_ni is not None and shares and shares > 0:
        out["trailing_eps"] = round(ttm_ni / shares, 2)
    if ttm_rev is not None and shares and shares > 0:
        out["revenue_per_share"] = round(ttm_rev / shares, 2)
    if ttm_rev is not None:
        out["revenue_ttm"] = round(ttm_rev / 1_000_000)

    if ttm_ni is not None and ttm_ni > 0 and shares and shares > 0:
        eps = ttm_ni / shares
        if eps > 0:
            out["pe"] = f"{price / eps:.1f}"

    growth = yoy_quarter_growth(rev_series, as_of)
    if growth is not None:
        out["rev_growth"] = ratio_to_pct(growth)

    if ttm_ni is not None and ttm_rev is not None and ttm_rev > 0:
        out["profit_margin"] = ratio_to_pct(ttm_ni / ttm_rev)

    cash = instant_sum(facts, edgar_tags.CASH_ANCHOR, edgar_tags.CASH_OPTIONAL_ADD, as_of)
    debt = instant_sum(facts, edgar_tags.DEBT_ANCHOR, edgar_tags.DEBT_OPTIONAL_ADD, as_of)
    if cash is not None:
        out["total_cash"] = round(cash / 1_000_000)
    if debt is not None:
        out["total_debt"] = round(debt / 1_000_000)
    if cash is not None and debt is not None:
        out["net_cash"] = net_cash_millions(cash, debt)

    if market_cap is not None and ttm_rev is not None and ttm_rev > 0:
        out["price_to_sales"] = f"{market_cap / ttm_rev:.1f}"

    ttm_ocf = ttm(quarterly_series(facts, edgar_tags.OPERATING_CASH_FLOW), as_of)
    ttm_capex = ttm(quarterly_series(facts, edgar_tags.CAPEX), as_of)
    if ttm_ocf is not None and ttm_capex is not None:
        fcf = ttm_ocf - ttm_capex
        out["free_cash_flow"] = round(fcf / 1_000_000)
        fcf_yield = fcf_yield_pct(fcf, market_cap)
        if fcf_yield is not None:
            out["fcf_yield"] = fcf_yield

    ttm_op = ttm(quarterly_series(facts, edgar_tags.OPERATING_INCOME), as_of)
    ttm_da = ttm(quarterly_series(facts, edgar_tags.DEPRECIATION_AMORTIZATION), as_of)
    if (
        market_cap is not None
        and cash is not None
        and debt is not None
        and ttm_op is not None
        and ttm_da is not None
    ):
        ebitda = ttm_op + ttm_da
        if ebitda > 0:
            out["ev_to_ebitda"] = f"{(market_cap + debt - cash) / ebitda:.1f}"

    if ttm_op is not None and ttm_rev is not None and ttm_rev > 0:
        out["operating_margin"] = ratio_to_pct(ttm_op / ttm_rev)

    # Gross profit, either reported directly or reconstructed as
    # revenue − cost of revenue. Financials and some REITs report neither,
    # which is a real absence: they have no cost of goods to speak of.
    gross_series = quarterly_series(facts, edgar_tags.GROSS_PROFIT)
    if not gross_series and rev_series:
        cogs_by_end = {
            end: value
            for _, end, value in quarterly_series(facts, edgar_tags.COST_OF_REVENUE)
        }
        gross_series = [
            (start, end, value - cogs_by_end[end])
            for start, end, value in rev_series
            if end in cogs_by_end
        ]
    ttm_gross = ttm(gross_series, as_of) if gross_series else None
    if ttm_gross is not None and ttm_rev is not None and ttm_rev > 0:
        out["gross_margin"] = ratio_to_pct(ttm_gross / ttm_rev)

    # Margin TRENDS, quarter over the same quarter a year earlier, in bps.
    for key, numerator in (
        ("net_margin_trend_bps", ni_series),
        ("operating_margin_trend_bps", quarterly_series(facts, edgar_tags.OPERATING_INCOME)),
        ("gross_margin_trend_bps", gross_series),
    ):
        if not numerator or not rev_series:
            continue
        trend = margin_trend_bps(numerator, rev_series, as_of)
        if trend is not None:
            out[key], basis = trend
            out.setdefault("margin_trend_basis", basis)

    equity = resolve_instant(facts, edgar_tags.EQUITY, as_of)
    assets = resolve_instant(facts, edgar_tags.ASSETS, as_of)
    if ttm_ni is not None and equity and equity > 0:
        out["return_on_equity"] = ratio_to_pct(ttm_ni / equity)
    if ttm_ni is not None and assets and assets > 0:
        out["return_on_assets"] = ratio_to_pct(ttm_ni / assets)
    if debt is not None and equity and equity > 0:
        # Already a ratio. The live path divides yfinance's figure by 100
        # because that provider reports a percent; that is a provider quirk,
        # not the definition, so nothing is scaled here.
        out["debt_to_equity"] = round(debt / equity, 2)

    # Current and quick ratios exist only on a CLASSIFIED balance sheet.
    # Banks and insurers do not present one, so these stay absent for them
    # rather than resolving to something that would read as a solvency fact.
    current_assets = resolve_instant(facts, edgar_tags.CURRENT_ASSETS, as_of)
    current_liabilities = resolve_instant(facts, edgar_tags.CURRENT_LIABILITIES, as_of)
    if current_assets is not None and current_liabilities and current_liabilities > 0:
        out["current_ratio"] = round(current_assets / current_liabilities, 2)
        inventory = resolve_instant(facts, edgar_tags.INVENTORY, as_of)
        if inventory is not None:
            # Absent inventory is not zero inventory — a filer that reports no
            # inventory line and one that reports 0.0 are different claims.
            out["quick_ratio"] = round(
                (current_assets - inventory) / current_liabilities, 2
            )

    ttm_buybacks = ttm(quarterly_series(facts, edgar_tags.BUYBACKS), as_of)
    if ttm_buybacks is not None and ttm_buybacks > 0:
        out["buyback_ttm"] = round(ttm_buybacks / 1_000_000)
        if market_cap:
            out["buyback_yield"] = round(ttm_buybacks / market_cap * 100, 1)

    ttm_divs = ttm(quarterly_series(facts, edgar_tags.DIVIDENDS_PAID_COMMON), as_of)
    if ttm_divs is not None and ttm_divs > 0 and ttm_ni and ttm_ni > 0:
        out["payout_ratio"] = ratio_to_pct(ttm_divs / ttm_ni)
    if ttm_divs is not None and ttm_divs > 0 and market_cap:
        # PaymentsOfDividends* is a cash OUTFLOW (positive in the statement);
        # yield = payments / market cap, rendered percent like the live field.
        out["dividend_yield"] = ratio_to_pct(ttm_divs / market_cap, decimals=2)

    # CR218 — total capital returned, and what share of free cash flow it took.
    # Added on THIS path first, because the as-of sheet is the one the backtest
    # renders and the one the observation came from: a Fundamentals Analyst
    # given "Buybacks $5,910M" and "Dividend yield 1.4%" has to convert the
    # yield back to dollars against market cap and divide by FCF to reach the
    # capital-allocation read its own role brief asks for. Here both operands
    # are already resolved exactly from EDGAR, so the conversion is neither
    # approximate nor the model's job.
    if ttm_divs is not None and ttm_divs > 0:
        out["dividends_paid_ttm"] = round(ttm_divs / 1_000_000)
    components = [
        v for v in (out.get("buyback_ttm"), out.get("dividends_paid_ttm"))
        if v is not None
    ]
    if components:
        total = sum(components)
        out["capital_return_ttm"] = total
        fcf_m = out.get("free_cash_flow")
        # Positive FCF only. A company returning capital while burning cash is
        # funding it from the balance sheet or new debt, and a percentage of a
        # small or negative denominator asserts a precision the ratio does not
        # have. The dollars still render; only the ratio is withheld.
        if fcf_m and fcf_m > 0:
            out["capital_return_pct_fcf"] = round(total / fcf_m * 100)

    out.update(_price_derived(ticker, as_of, price_rows))

    logger.info(
        "pit_fundamentals_resolved",
        ticker=ticker,
        as_of=as_of.isoformat(),
        fields=sorted(k for k in out if k not in ("support", "breakout", "week52_range_live")),
        facts_loaded=len(facts),
        price_rows=len(price_rows),
        shares_basis=shares_basis if market_cap is not None else "unresolved",
    )
    return out


def _price_derived(
    ticker: str, as_of: date, price_rows: list[tuple],
) -> dict[str, Any]:
    """The fact-sheet fields the live path reads off yfinance `.info` but which
    are computable from stored bars (CR164).

    Row shape from `get_asof_daily_rows`:
    `(date, open, high, low, close, adj_close, volume)`.

    Two gates matter. The day-move and today's volume describe *the as-of
    session*, so they are emitted only when the newest stored bar IS the as-of
    date — on a market holiday the newest bar is an earlier session and calling
    its move "today's" would be wrong by a day. The 52-week trio needs a real
    year of separation present in BOTH this ticker's window and SPY's, checked
    as a date span rather than a row count, because a row count says nothing
    about how much calendar it covers.
    """
    from app.services.price_history import get_asof_daily_rows

    out: dict[str, Any] = {}
    closes = [r[5] for r in price_rows]
    is_as_of_session = price_rows[-1][0] == as_of

    if is_as_of_session and len(closes) >= 2 and closes[-2] > 0:
        out["day_change_pct"] = round((closes[-1] / closes[-2] - 1.0) * 100, 2)
        # A stored daily bar is a settled close, which is exactly what the
        # live field means by CLOSED. Stated, not inferred.
        out["market_state"] = "CLOSED"
        if price_rows[-1][6] is not None:
            out["volume_today"] = int(price_rows[-1][6])

    if len(closes) >= 200:
        sma_200 = sum(closes[-200:]) / 200
        out["sma_200"] = round(sma_200, 2)
        if sma_200 > 0:
            out["price_vs_sma_200_pct"] = round(
                (closes[-1] - sma_200) / sma_200 * 100, 1
            )

    volumes = [r[6] for r in price_rows[-65:]]
    if len(volumes) == 65 and all(v is not None for v in volumes):
        out["volume_avg_3m"] = int(sum(volumes) / 65)

    ticker_return = _year_return(price_rows, as_of)
    if ticker_return is not None:
        out["change_52w_pct"] = round(ticker_return * 100, 1)
        spy_rows = get_asof_daily_rows("SPY", as_of, max_rows=252)
        spy_return = _year_return(spy_rows, as_of) if spy_rows else None
        if spy_return is not None:
            out["change_52w_sp500_pct"] = round(spy_return * 100, 1)
            # Computed from the raw ratios, mirroring the live path, so the
            # spread is not the difference of two separately-rounded numbers.
            out["relative_strength_52w_pct"] = round(
                (ticker_return - spy_return) * 100, 1
            )
    return out


def _year_return(price_rows: list[tuple], as_of: date) -> float | None:
    """Total return over the oldest bar that is 340–380 days before `as_of`.

    None when the stored window does not reach back a genuine year — which is
    the common case at the very start of the backtest window, where the
    backfill itself is only a year deep. Returning None there is the point:
    a "52-week change" measured over seven months is a different number
    wearing the same label.
    """
    if not price_rows:
        return None
    anchor = next(
        (r for r in price_rows if 340 <= (as_of - r[0]).days <= 380), None
    )
    if anchor is None or anchor[5] <= 0:
        return None
    return price_rows[-1][5] / anchor[5] - 1.0
