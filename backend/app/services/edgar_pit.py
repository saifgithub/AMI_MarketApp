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


def resolve_instant(
    facts: Sequence[_FactView], tags: Sequence[str], as_of: date,
    *, max_age_days: int = MAX_INSTANT_AGE_DAYS,
) -> float | None:
    """Latest balance-sheet point for the FIRST tag that resolves.

    Within a tag: newest `period_end` wins, ties broken by newest `filed` —
    so a 10-K/A amendment naturally supersedes the original without any
    amendment-specific handling.
    """
    for tag in tags:
        candidates = [f for f in facts if f.tag == tag]
        if not candidates:
            continue
        best = max(candidates, key=lambda f: (f.period_end, f.filed))
        if (as_of - best.period_end).days > max_age_days:
            return None
        return best.value
    return None


def quarterly_series(
    facts: Sequence[_FactView], tags: Sequence[str],
) -> list[tuple[date, date, float]]:
    """Deduped quarterly duration facts for the first tag with any, ascending
    by period_end. Per (period_start, period_end), the latest-filed value wins.

    Where a fiscal year has an annual duration fact and exactly three known
    quarters inside it, the missing quarter is DERIVED as FY − (Q1+Q2+Q3) —
    the standard companyfacts gap (many filers tag Q4 only inside the 10-K's
    annual figure).
    """
    tag = next((t for t in tags if any(f.tag == t for f in facts)), None)
    if tag is None:
        return []
    mine = [f for f in facts if f.tag == tag and f.period_start is not None]

    def _span(f: _FactView) -> int:
        return (f.period_end - f.period_start).days

    by_period: dict[tuple[date, date], _FactView] = {}
    for f in mine:
        if not (_QUARTER_SPAN[0] <= _span(f) <= _QUARTER_SPAN[1]):
            continue
        key = (f.period_start, f.period_end)
        if key not in by_period or f.filed > by_period[key].filed:
            by_period[key] = f
    quarters = {k: v.value for k, v in by_period.items()}

    annuals: dict[tuple[date, date], _FactView] = {}
    for f in mine:
        if not (_ANNUAL_SPAN[0] <= _span(f) <= _ANNUAL_SPAN[1]):
            continue
        key = (f.period_start, f.period_end)
        if key not in annuals or f.filed > annuals[key].filed:
            annuals[key] = f

    for (fy_start, fy_end), fy_fact in annuals.items():
        inside = {
            (s, e): v for (s, e), v in quarters.items()
            if s >= fy_start - timedelta(days=10) and e <= fy_end + timedelta(days=10)
        }
        if len(inside) != 3:
            continue
        covered_ends = sorted(e for (_, e) in inside)
        if any(abs((e - fy_end).days) <= 10 for e in covered_ends):
            # The missing quarter is not the last one — deriving a mid-year
            # quarter from FY − 3 others is the same arithmetic but a rarer
            # gap shape; keep v1 to the standard Q4 case.
            continue
        derived_start = max(covered_ends) + timedelta(days=1)
        quarters[(derived_start, fy_end)] = fy_fact.value - sum(inside.values())

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


def yoy_quarter_growth(
    series: list[tuple[date, date, float]], as_of: date,
    *, max_age_days: int = MAX_QUARTER_AGE_DAYS,
) -> float | None:
    """Latest quarter vs the same quarter a year earlier, as a decimal ratio
    (0.05 = +5%) — the same definition yfinance's `revenueGrowth` carries, so
    the rendered field means the same thing on both paths."""
    eligible = [item for item in series if item[1] <= as_of]
    if not eligible:
        return None
    latest_start, latest_end, latest_value = eligible[-1]
    if (as_of - latest_end).days > max_age_days:
        return None
    prior = [
        v for s, e, v in eligible
        if abs((latest_end - e).days - 365) <= 20
    ]
    if not prior or prior[-1] == 0:
        return None
    base = prior[-1]
    if base <= 0:
        return None
    return latest_value / base - 1.0


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

    shares = resolve_instant(facts, edgar_tags.SHARES_OUTSTANDING_DEI, as_of)
    market_cap = price * shares if shares and shares > 0 else None

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
    if cash is not None and debt is not None:
        out["net_cash"] = net_cash_millions(cash, debt)

    if market_cap is not None and ttm_rev is not None and ttm_rev > 0:
        out["price_to_sales"] = f"{market_cap / ttm_rev:.1f}"

    ttm_ocf = ttm(quarterly_series(facts, edgar_tags.OPERATING_CASH_FLOW), as_of)
    ttm_capex = ttm(quarterly_series(facts, edgar_tags.CAPEX), as_of)
    if ttm_ocf is not None and ttm_capex is not None:
        fcf = ttm_ocf - ttm_capex
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

    ttm_divs = ttm(quarterly_series(facts, edgar_tags.DIVIDENDS_PAID_COMMON), as_of)
    if ttm_divs is not None and ttm_divs > 0 and market_cap:
        # PaymentsOfDividends* is a cash OUTFLOW (positive in the statement);
        # yield = payments / market cap, rendered percent like the live field.
        out["dividend_yield"] = ratio_to_pct(ttm_divs / market_cap, decimals=2)

    logger.info(
        "pit_fundamentals_resolved",
        ticker=ticker,
        as_of=as_of.isoformat(),
        fields=sorted(k for k in out if k not in ("support", "breakout", "week52_range_live")),
        facts_loaded=len(facts),
    )
    return out
