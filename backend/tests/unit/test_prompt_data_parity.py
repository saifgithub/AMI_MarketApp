"""DEF098 — prompt-data parity guard: no computed live field is silently dropped.

The prompt-data analogue of `test_config_compose_parity.py`. That test exists
because a value defined in one place (`Settings`) was silently not forwarded in
another (`docker-compose.yml`) and a feature shipped dark twice (DEF038/DEF063).
This is the *same shape* for a different resource: a field the market-data /
journal pipeline computes must appear in the prompt block the consuming agent
reads, and until now nothing enforced that. It bit us three times — DEF074
(`support` computed, 52-week low shown instead), DEF096 (three live Reddit fields
computed, dropped from the Room), and the 1-on-1 fundamentals block dropping
next-earnings (fixed in this same DEF098 change).

Root cause the guard addresses: live ticker data has two rendering paths built at
different times — the Room (`room_runner._profile_for_ticker` → `_format_profile`)
and 1-on-1 chat (`build_*_context_block`) — plus the journal has two more
(researcher lookback vs Concierge routing index). Neither pair is a superset of
the other, so a field is safe only by the accident of a developer hand-writing it
into every place.

How this guard stays honest (the "guard-on-the-guard"): the produced-field set of
every source is read from the pipeline's *real output* — the fetcher's actual dict
keys / NamedTuple `_fields` / pydantic `model_fields` — NOT a hand-kept checklist
that would rot exactly like the bug it guards. Each produced field is then flowed,
as a unique sentinel value, through the REAL renderer on every surface the
consuming agent reads; the field must either leave its fingerprint in the rendered
text, or be listed in `INTENTIONALLY_OMITTED` with a one-line reason. A freshly
produced field that is neither rendered nor declared fails the build (proven in
`test_guard_on_the_guard_*`).
"""

from __future__ import annotations

import sys
import types
import zlib
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.config import settings
from app.schemas.journal import EntryType, JournalEntry, Outcome
from app.services import (
    concierge_prompts,
    fundamentals,
    journal_context,
    news_context,
    room_runner,
    social_context,
    technicals,
)
from app.services.journal_context import build_journal_context_block
from app.services.market_data import EarningsInfo
from app.services.news_context import LiveHeadline
from app.services.room_prompts import _format_profile
from app.services.social_context import SocialSentiment, SubredditStat
from app.services.technicals import Technicals

# The single ticker every surface is rendered for. Distinct-looking so an
# accidental substring collision with a fingerprint is obvious.
_TICKER = "ZQXA"


# ── Sentinel fetcher outputs (each carries a unique, searchable fingerprint) ──
# Values are engineered so their *rendered* form is a unique substring: numbers
# that survive the code's own format specifiers, ALL-CAPS string tokens that
# survive `.upper()` on the ticker/symbol path.

_FUND_SENTINEL: dict = {
    "base_price": 271.83,
    "pe": "48.77",            # kept a string — the fetcher emits it pre-formatted
    "forward_pe": "12.34",    # DEF233 — the consensus-estimate basis, string-formatted too
    "peg_basis": "PEGBASISSENT",  # the denominator label the PEG figure carries
    "rev_growth": 23.61,
    "profit_margin": 41.29,
    "net_cash": 944,          # → net_position_phrase → "net cash $944M"
    "low": 155.4,
    "high": 402.9,
    "support": 190.55,        # placeholder — technicals overwrites/owns rendering
    "breakout": 350.25,       # placeholder — technicals overwrites/owns rendering
    "week52_range_live": True,  # boolean render-control flag, not a data value
    "price_to_sales": "7.31",
    "ev_to_ebitda": "19.42",
    "peg_ratio": "2.15",
    "fcf_yield": 3.87,
    "dividend_yield": 1.63,
    "sector": "ENERGYSENT",
    "industry": "DRILLSENT",
    "analyst_target_price": 488.12,
    "analyst_rating": "STRONGSENT",
    # CR145 Tier A — fetched since DEF053, consumed only inside fcf_yield and
    # net_cash, rendered from AT:R68.
    "market_cap": 1234567,
    "free_cash_flow": 45678,
    "total_debt": 8901,
    # CR168 (folded into CR166) — resolved instrument identity. Strings, so they
    # carry ALL-CAPS fingerprints like sector/industry above.
    "long_name": "LONGNAMESENT",
    "exchange_name": "EXCHNAMESENT",
    # CR166 Tier B — the fields fetched inside the same `.info` call and
    # discarded at the render site until AT:R68. Fingerprints picked so each
    # rendered form is a unique substring of the sheet.
    "gross_margin": 63.71,
    "operating_margin": 52.83,
    "trailing_eps": 7.7701,
    "revenue_ttm": 98765,
    "revenue_per_share": 66.4401,
    "return_on_equity": 31.55,
    "return_on_assets": 17.22,
    "current_ratio": 3.19,
    "quick_ratio": 2.71,
    "debt_to_equity": 1.47,
    "payout_ratio": 27.33,
    "analyst_opinion_count": 37,
    "analyst_target_high": 611.25,
    "analyst_target_low": 122.75,
    "analyst_target_median": 355.75,
    "analyst_rating_score": 3.7,
    "held_pct_institutions": 72.19,
    "held_pct_insiders": 4.31,
    "shares_outstanding": 8642,
    "float_shares": 7531,
}

_TECH_SENTINEL = Technicals(
    rsi=57,
    rsi_tone="TONESENT",
    trend="TRENDSENT",
    volume_tone="VOLSENT",
    support=333.11,
    breakout=888.99,
    price=444.22,
    # CR146 Tier B — the numbers `trend` and `volume_tone` are bucketings OF.
    sma_short=411.77,
    sma_long=422.88,
    volume_ratio=1.47,
)

# CR148 Tier B — the snapshot's age renders as a date + a relative age, so its
# fingerprint is the date, derived here independently of the formatter under
# test (the news `published_at` entry below takes the other route and calls the
# formatter; doing that for both would leave neither non-vacuous).
_SOCIAL_FETCHED_AT = int(datetime.now(timezone.utc).timestamp()) - (3 * 86400)
_SOCIAL_FETCHED_DATE = datetime.fromtimestamp(
    _SOCIAL_FETCHED_AT, tz=timezone.utc
).strftime("%Y-%m-%d")

_SOCIAL_SENTINEL = SocialSentiment(
    ticker="TKFIELDSENT",     # distinct from the block arg so we can prove the
    buzz_score=88.0,          # field itself is not what renders the symbol
    sentiment_score=0.42,
    mentions=73561,
    bullish_pct=61,
    bearish_pct=29,
    trend="SOCTRENDSENT",
    period_days=33,
    top_subreddits=("SUBSENT",),
    sample_snippets=("SNIPPETSENT",),
    # CR148 Tier A — six dimensions that arrived on every Adanos call since
    # CR024 and were dropped before they reached any prompt.
    positive_count=4471,
    negative_count=2119,
    neutral_count=6971,
    total_upvotes=98765,
    unique_posts=1234,
    subreddit_count=44,
    subreddit_stats=(SubredditStat("SPLITSENT", 5150, -0.37, 66.0),),
    fetched_at=_SOCIAL_FETCHED_AT,
)

_EARNINGS_SENTINEL = EarningsInfo(
    earnings_date="2026-09-30",
    quarter="Q3",
    eps_estimate=4.44,
    # CR179 Leg 0 — these two were left at their None defaults, so their
    # fingerprints did not exist and every check that walks the fingerprint map
    # skipped them. That is what let four INTENTIONALLY_OMITTED entries go on
    # asserting "deliberately not rendered" for a year after CR166 Stage 1
    # started rendering both: the omission suppressed the parity check, and the
    # empty sentinel suppressed the guard on the omission. Populated so the
    # fixture can see them at all.
    ex_dividend_date="2026-10-17",
    dividend_rate=2.64,
)

_JOURNAL_SENTINEL = JournalEntry(
    user_id=uuid4(),
    entry_type=EntryType.ROOM_RUN,
    title="TITLESENT",
    summary="SUMMARYSENT",
    ticker="TICKSENT",
    agents_involved=["AGENTSENT"],
    tags=["TAGSENT"],
    user_note="USERNOTESENT",
    outcome=Outcome.WIN,
    created_at=datetime(2026, 3, 14, tzinfo=timezone.utc),
)

# News published_at renders as a *relative age* ("Nd ago"), not the raw epoch, so
# its fingerprint is derived from the code's own formatter at render time.
_NEWS_PUBLISHED_AT = int(datetime.now(timezone.utc).timestamp()) - (10 * 86400 + 3600)


def _news_sentinel() -> LiveHeadline:
    return LiveHeadline(
        title="HEADLINESENT",
        link="LINKSENT",
        publisher="PUBSENT",
        published_at=_NEWS_PUBLISHED_AT,
        sentiment="SENTIMENTSENT",
        source="alpha_vantage",
    )


# ── Surfaces each source feeds ────────────────────────────────────────────────

_SURFACES_BY_SOURCE: dict[str, tuple[str, ...]] = {
    "fundamentals": ("room", "one_on_one"),
    "technicals": ("room", "one_on_one"),
    "news": ("room", "one_on_one"),
    "social": ("room", "one_on_one"),
    "earnings": ("room", "one_on_one"),
    "journal": ("researcher", "concierge"),
}


# ── The by-design omissions registry (source, surface, field) → reason ────────
# Every entry is a DELIBERATE non-render. An unexplained or stale entry is a bug
# hiding, so `test_registry_entries_are_valid` verifies each reason is non-empty
# and each field is really produced by that source on that surface.

_JOURNAL_PLUMBING_REASONS: dict[str, str] = {
    "id": "row primary key — persistence plumbing, never prompt content.",
    "user_id": "owner FK — persistence plumbing, never prompt content.",
    "reference_id": "FK to the underlying object — plumbing, not decision content.",
    "mandate_version": "which mandate revision was live — audit metadata, not reasoning.",
    "payload": "full snapshot kept for replay — not distilled prompt content.",
    "deleted_at": "soft-delete marker — lifecycle plumbing, never prompt content.",
}

INTENTIONALLY_OMITTED: dict[tuple[str, str, str], str] = {
    # ── fundamentals ──
    ("fundamentals", "room", "support"): (
        "placeholder ±10% support; compute_technicals overwrites it with the real "
        "50-day low before render — the technicals source owns support/breakout."
    ),
    ("fundamentals", "one_on_one", "support"): (
        "the technicals block renders the real 50-day support; the fundamentals "
        "±placeholder is intentionally not shown to avoid a second, weaker number."
    ),
    ("fundamentals", "room", "breakout"): (
        "placeholder ±3% breakout superseded by compute_technicals' real 50-day "
        "high; the technicals source owns support/breakout rendering."
    ),
    ("fundamentals", "one_on_one", "breakout"): (
        "the technicals block renders the real 50-day breakout; the fundamentals "
        "±placeholder is intentionally not shown."
    ),
    ("fundamentals", "room", "week52_range_live"): (
        "boolean render-control flag (real 52-week range vs ±5% placeholder label), "
        "not a data value."
    ),
    ("fundamentals", "one_on_one", "week52_range_live"): (
        "boolean render-control flag, not a data value."
    ),
    # ── social ──
    ("social", "room", "ticker"): (
        "the lookup symbol, carried on the fetch result but rendered from the "
        "profile/block header, not an analytical field."
    ),
    ("social", "one_on_one", "ticker"): (
        "the lookup symbol, rendered from the block header (call arg), not an "
        "analytical field."
    ),
    ("social", "room", "sample_snippets"): (
        "raw Reddit post text — deliberately never stored in the Room profile dict, "
        "which also feeds the scripted non-LLM fallback shown to users "
        "(social_context.py); LLM-synthesis-only, so 1-on-1 renders it, Room does not."
    ),
    ("social", "one_on_one", "sentiment_score"): (
        "the signed composite score is the Room's compact one-liner; the 1-on-1 "
        "block conveys the same read via the bull/bear split + buzz, so the raw "
        "score is omitted to avoid a redundant number the analyst would double-count."
    ),
    # ── news ──
    ("news", "room", "link"): (
        "the article URL is never placed in the prompt — headline text, publisher "
        "and recency are the signal; a raw link is an unusable token for the LLM."
    ),
    ("news", "one_on_one", "link"): (
        "the article URL is never placed in the prompt; headline + publisher + "
        "recency are the signal."
    ),
    ("news", "room", "source"): (
        "internal provenance / dedup-precedence tag (yfinance vs alpha_vantage); the "
        "block discloses sourcing in prose, a per-item source label would be noise."
    ),
    ("news", "one_on_one", "source"): (
        "internal provenance / dedup-precedence tag; the block discloses sourcing "
        "in prose already."
    ),
    # ── journal · researcher (Bull/Bear decision-lookback) ──
    ("journal", "researcher", "entry_type"): (
        "the researcher block is a per-ticker decision lookback; the entry-type "
        "taxonomy (room_run/sim_trade/…) is not the reasoning it needs."
    ),
    ("journal", "researcher", "ticker"): (
        "the block is already scoped to one ticker in its header; repeating it per "
        "line is redundant."
    ),
    ("journal", "researcher", "tags"): "internal categorisation metadata, not decision reasoning.",
    ("journal", "researcher", "agents_involved"): (
        "roster metadata; the researcher wants the thesis + outcome, not who attended."
    ),
    # ── journal · concierge (routing index, per DEF098 spec) ──
    ("journal", "concierge", "summary"): (
        "Concierge routes to an entry, it does not analyse it — a compact index "
        "(type/ticker/title) is correct (DEF098 spec)."
    ),
    ("journal", "concierge", "user_note"): "routing index, not analysis (DEF098 spec).",
    ("journal", "concierge", "outcome"): "routing index, not analysis (DEF098 spec).",
    ("journal", "concierge", "created_at"): "routing index, not analysis (DEF098 spec).",
    ("journal", "concierge", "tags"): "routing index, not analysis.",
    ("journal", "concierge", "agents_involved"): "routing index, not analysis.",
    # ── earnings ──
    # CR179 Leg 0 removed four entries here — ("earnings", {room,one_on_one},
    # {ex_dividend_date,dividend_rate}) — which read "CR030 mobile ticker-detail
    # dividend chip, not analyst-prompt data … an ex-date is calendar noise in
    # the analyst reasoning prompt." That was true when written and false from
    # CR166 Tier B onward, which renders both on the dividend line on BOTH
    # surfaces (`_capital_allocation_line`). They are now covered by the ordinary
    # parity check rather than excused from it.
    #
    # Worth keeping the mechanism in view: the stale entries were undetectable by
    # construction. `_unrendered` short-circuits on `omitted` before testing the
    # fingerprint, so the omission suppressed the check that would have caught
    # it — and `_EARNINGS_SENTINEL` left both fields at None, so no fingerprint
    # existed for any other check to notice either. Two independent silences over
    # the same fact. `test_no_omission_entry_names_a_field_that_is_actually_
    # rendered` is the guard that ends it.
}

# Journal storage/plumbing fields are non-content on BOTH journal surfaces.
for _surface in ("researcher", "concierge"):
    for _field, _reason in _JOURNAL_PLUMBING_REASONS.items():
        INTENTIONALLY_OMITTED[("journal", _surface, _field)] = _reason


# ── Driving the real pipeline with the sentinels injected ─────────────────────


class _FakeEarningsProvider:
    """Only `.earnings()` is exercised in the paths we drive (Room profile builder
    and the 1-on-1 fundamentals block)."""

    def earnings(self, ticker: str) -> EarningsInfo:
        return _EARNINGS_SENTINEL


class _AllKeysInfo(dict):
    """A yfinance `info` stand-in that returns a distinct numeric for ANY key, so
    every branch of `fetch_live_fundamentals` fires and every possible output key
    is produced — the produced-field set is then read from the real fetcher's
    output, not hand-listed (guard-on-the-guard for the dict-shaped source).

    CR168 — `exchange` is the first key whose VALUE must come from a known set:
    the fetcher maps a venue code to a name and drops anything unmapped, so a
    numeric here would silently stop `exchange_name` being produced and the
    guard would go quietly blind to it. Answered with a real code so the branch
    fires. The fixture's premise ("every branch fires") is preserved rather than
    weakened; any future value-constrained key needs the same treatment.
    """

    def get(self, key, default=None):
        if key == "exchange":
            return "NMS"
        return 1000.0 + (zlib.crc32(key.encode()) % 9000)

    def __bool__(self) -> bool:
        return True


def _fake_yfinance_module() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        __version__="1.2.3",
        Ticker=lambda t: types.SimpleNamespace(info=_AllKeysInfo()),
    )


@pytest.fixture
def env(monkeypatch):
    """Render every surface once, with each source's sentinel fetcher output
    injected into the REAL renderers, and return (produced sets, surface texts,
    fingerprints)."""
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(settings, "suppress_analyst_consensus", False)
    monkeypatch.setattr(settings, "adanos_api_key", "x")  # gates the 1-on-1 social block

    # 1) Discover the fundamentals produced-field set from the REAL fetcher driven
    #    by a fake yfinance that answers every key — BEFORE we stub the fetcher.
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yfinance_module())
    produced_fund = set(fundamentals.fetch_live_fundamentals(_TICKER).keys())

    # 2) Inject the render sentinels into every fetch seam, on BOTH the module that
    #    defines the helper and room_runner's imported copy of it.
    monkeypatch.setattr(fundamentals, "fetch_live_fundamentals", lambda t: dict(_FUND_SENTINEL))
    monkeypatch.setattr(room_runner, "fetch_live_fundamentals", lambda t: dict(_FUND_SENTINEL))
    monkeypatch.setattr(technicals, "compute_technicals", lambda t: _TECH_SENTINEL)
    monkeypatch.setattr(room_runner, "compute_technicals", lambda t: _TECH_SENTINEL)
    monkeypatch.setattr(news_context, "fetch_live_news", lambda t, limit=3: [_news_sentinel()])
    monkeypatch.setattr(room_runner, "fetch_live_news", lambda t: [_news_sentinel()])
    monkeypatch.setattr(social_context, "fetch_live_sentiment", lambda t: _SOCIAL_SENTINEL)
    monkeypatch.setattr(room_runner, "fetch_live_sentiment", lambda t: _SOCIAL_SENTINEL)
    monkeypatch.setattr(fundamentals, "get_market_data_provider", lambda: _FakeEarningsProvider())
    monkeypatch.setattr(room_runner, "get_market_data_provider", lambda: _FakeEarningsProvider())
    monkeypatch.setattr(journal_context, "fetch_recent_journal_entries", lambda *a, **k: [_JOURNAL_SENTINEL])

    # 3) Render every surface through the REAL renderers.
    profile = room_runner._profile_for_ticker(_TICKER)
    room_text = _format_profile(profile)
    fund_block = fundamentals.build_live_data_block(_TICKER)
    tech_block = technicals.build_technicals_context_block(_TICKER)
    news_block = news_context.build_news_context_block(_TICKER)
    social_block = social_context.build_social_context_block(_TICKER)
    researcher_text = build_journal_context_block(uuid4(), _TICKER)
    concierge_text = concierge_prompts._format_journal([_JOURNAL_SENTINEL])

    for name, text in [
        ("room", room_text), ("fund_block", fund_block), ("tech_block", tech_block),
        ("news_block", news_block), ("social_block", social_block),
        ("researcher", researcher_text), ("concierge", concierge_text),
    ]:
        assert text, f"surface {name!r} rendered empty — sentinel injection failed"

    surfaces: dict[tuple[str, str], str] = {
        ("fundamentals", "room"): room_text,
        ("fundamentals", "one_on_one"): fund_block,
        ("technicals", "room"): room_text,
        ("technicals", "one_on_one"): tech_block,
        ("news", "room"): room_text,
        ("news", "one_on_one"): news_block,
        ("social", "room"): room_text,
        ("social", "one_on_one"): social_block,
        ("earnings", "room"): room_text,
        # earnings is rendered inside the 1-on-1 fundamentals block (DEF098 fix).
        ("earnings", "one_on_one"): fund_block,
        ("journal", "researcher"): researcher_text,
        ("journal", "concierge"): concierge_text,
    }

    produced: dict[str, set[str]] = {
        "fundamentals": produced_fund,
        "technicals": set(Technicals._fields),
        "news": set(LiveHeadline._fields),
        "social": set(SocialSentiment._fields),
        "earnings": set(EarningsInfo._fields),
        "journal": set(JournalEntry.model_fields),
    }

    fingerprints: dict[str, dict[str, str]] = {
        "fundamentals": {
            "base_price": "271.83", "pe": "48.77", "rev_growth": "23.61",
            "profit_margin": "41.29", "net_cash": "944M", "low": "155.4",
            "high": "402.9", "price_to_sales": "7.31x", "ev_to_ebitda": "19.42x",
            "peg_ratio": "PEG 2.15", "fcf_yield": "3.87", "dividend_yield": "1.63",
            # CR145 Tier A — thousands-separated $M, which is also what makes
            # the mandate's "< $500M market cap" rule checkable at all.
            "market_cap": "market cap $1,234,567M",
            "free_cash_flow": "FCF $45,678M",
            "total_debt": "gross debt $8,901M",
            # DEF233 — both P/E bases render on both surfaces, and the PEG
            # carries the denominator label the fetcher supplied.
            "forward_pe": "12.34 forward", "peg_basis": "(PEGBASISSENT basis)",
            "sector": "ENERGYSENT", "industry": "DRILLSENT",
            "analyst_target_price": "488.12", "analyst_rating": "STRONGSENT",
            # CR168 (folded into CR166) — resolved instrument identity.
            "long_name": "LONGNAMESENT", "exchange_name": "EXCHNAMESENT",
            # CR166 Tier B — fetched inside the same `.info` call as everything
            # above and discarded at the render site until AT:R68. Each
            # fingerprint is the field's rendered form INCLUDING its label, so a
            # bare number colliding with another field's value cannot pass this.
            "gross_margin": "gross 63.71%",
            "operating_margin": "operating 52.83%",
            "trailing_eps": "EPS $7.7701",
            "revenue_ttm": "revenue $98,765M TTM",
            "revenue_per_share": "revenue/share $66.4401",
            "return_on_equity": "ROE 31.55%",
            "return_on_assets": "ROA 17.22%",
            "current_ratio": "current ratio 3.19",
            "quick_ratio": "quick ratio 2.71",
            "debt_to_equity": "debt/equity 1.47x",
            "payout_ratio": "payout 27.33%",
            "analyst_opinion_count": "37 analysts",
            "analyst_target_high": "$611.25 range",
            "analyst_target_low": "$122.75–",
            "analyst_target_median": "$355.75 median",
            "analyst_rating_score": "mean score 3.7",
            "held_pct_institutions": "institutions 72.19%",
            "held_pct_insiders": "insiders 4.31%",
            "shares_outstanding": "8,642M shares out",
            "float_shares": "7,531M float",
        },
        "technicals": {
            "rsi": "57", "rsi_tone": "TONESENT", "trend": "TRENDSENT",
            "volume_tone": "VOLSENT", "support": "333.11", "breakout": "888.99",
            # DEF228: the last close, rendered on both surfaces as the range's
            # position anchor (`last close $444.22`).
            "price": "444.22",
            # CR146 Tier B: computed since DEF227, discarded until AT:R68.
            "sma_short": "411.77", "sma_long": "422.88",
            "volume_ratio": "1.47",
        },
        "social": {
            "buzz_score": "buzz score 88", "sentiment_score": "+0.42",
            "mentions": "73,561", "bullish_pct": "bullish 61%",
            "bearish_pct": "bearish 29%", "trend": "SOCTRENDSENT",
            "period_days": "over 33d", "top_subreddits": "SUBSENT",
            "sample_snippets": "SNIPPETSENT",
            # CR148 Tier A — the classified split, whose NEUTRAL residue is the
            # majority class and was never stated (42–71% of the sample,
            # median 52.5%, noticed in 2 of 18 turns).
            "positive_count": "4,471 positive",
            "negative_count": "2,119 negative",
            "neutral_count": "6,971 neutral",
            # Engagement intensity — what buzz_score compresses away.
            "total_upvotes": "98,765 total upvotes",
            "unique_posts": "1,234 distinct posts",
            # Breadth: naming 3 communities out of 44 read as the whole sample.
            "subreddit_count": "of 44 subreddits",
            # The per-community split — the evidence that leaves the 9/18
            # fabricated attributions nothing to invent.
            "subreddit_stats": "SPLITSENT",
            # CR148 Tier B — the freshness claim, replaced by the fetch date.
            "fetched_at": _SOCIAL_FETCHED_DATE,
        },
        "news": {
            "title": "HEADLINESENT", "publisher": "PUBSENT",
            "published_at": news_context._relative_age(_NEWS_PUBLISHED_AT),
            "sentiment": "SENTIMENTSENT",
        },
        "earnings": {
            "earnings_date": "2026-09-30", "quarter": "(Q3)", "eps_estimate": "4.44",
            # CR166 Tier B renders both of these on the dividend line, on BOTH
            # surfaces. They had no fingerprint until CR179 Leg 0, which is why
            # four INTENTIONALLY_OMITTED entries claiming the opposite survived.
            "ex_dividend_date": "ex-date 2026-10-17",
            "dividend_rate": "$2.64/share",
        },
        "journal": {
            "title": "TITLESENT", "outcome": "(win)", "summary": "SUMMARYSENT",
            "user_note": "USERNOTESENT", "created_at": "2026-03-14",
            "entry_type": "room_run", "ticker": "[TICKSENT]",
        },
    }

    return types.SimpleNamespace(produced=produced, surfaces=surfaces, fingerprints=fingerprints)


# ── The check ─────────────────────────────────────────────────────────────────


def _unrendered(
    produced: set[str], fingerprints: dict[str, str], omitted: set[str], text: str
) -> list[str]:
    """Produced fields that are neither declared-omitted nor left a rendered
    fingerprint in `text`. Empty ⇒ parity holds. This is the pure kernel every
    test (and the guard-on-the-guard) exercises."""
    missing: list[str] = []
    for field in produced:
        if field in omitted:
            continue
        fp = fingerprints.get(field)
        if fp is None or fp not in text:
            missing.append(field)
    return sorted(missing)


def _omitted_fields(source: str, surface: str) -> set[str]:
    return {f for (s, surf, f) in INTENTIONALLY_OMITTED if s == source and surf == surface}


_SOURCE_SURFACE_PAIRS = [
    (source, surface)
    for source, surfaces in _SURFACES_BY_SOURCE.items()
    for surface in surfaces
]


@pytest.mark.parametrize("source,surface", _SOURCE_SURFACE_PAIRS)
def test_every_produced_field_is_rendered_or_declared(env, source, surface):
    """DEF074/DEF096 regression: a field the pipeline computes for `source` that is
    neither rendered on `surface` nor listed in INTENTIONALLY_OMITTED fails here —
    red on the commit that drops it, instead of spotted by luck months later."""
    text = env.surfaces[(source, surface)]
    missing = _unrendered(
        env.produced[source], env.fingerprints[source], _omitted_fields(source, surface), text
    )
    assert not missing, (
        f"{source} produces these fields that are NOT rendered on the {surface!r} "
        f"surface and NOT in INTENTIONALLY_OMITTED: {missing}. "
        "Render them in the block, or add an INTENTIONALLY_OMITTED entry with a reason."
    )


def test_fundamentals_sentinel_matches_real_fetcher_output(env):
    """Guard-on-the-guard for the dict-shaped source: the render sentinel must
    cover EXACTLY what fetch_live_fundamentals actually produces. If the fetcher
    grows or loses a key, this fails until the sentinel (and the render/omit
    decision) is updated — the produced set can't silently drift out from under
    the parity check."""
    assert set(_FUND_SENTINEL) == env.produced["fundamentals"], (
        "fetch_live_fundamentals' output keys and the parity sentinel disagree: "
        f"only in fetcher={sorted(env.produced['fundamentals'] - set(_FUND_SENTINEL))}, "
        f"only in sentinel={sorted(set(_FUND_SENTINEL) - env.produced['fundamentals'])}"
    )


def test_registry_entries_are_valid(env):
    """An allow-list is only safe while every entry explains itself and names a
    field that really exists — otherwise it becomes where dropped fields hide."""
    for (source, surface, field), reason in INTENTIONALLY_OMITTED.items():
        assert reason.strip(), f"{(source, surface, field)} has no reason"
        assert source in _SURFACES_BY_SOURCE, f"unknown source in registry: {source}"
        assert surface in _SURFACES_BY_SOURCE[source], (
            f"{surface!r} is not a surface of {source!r}"
        )
        assert field in env.produced[source], (
            f"stale registry entry: {field!r} is no longer produced by {source!r}"
        )


def test_no_omission_entry_names_a_field_that_is_actually_rendered(env):
    """CR179 Leg 0 — the omission registry could only rot in one direction.

    `test_registry_entries_are_valid` checks a reason is non-empty and the field
    is still produced. Neither question notices when the field starts being
    RENDERED and the entry's reason becomes the opposite of the truth — and
    `_unrendered` short-circuits on `omitted` before testing the fingerprint, so
    the stale entry silences the very check that would have caught it.

    That is not hypothetical: CR166 Stage 1 began rendering `ex_dividend_date`
    and `dividend_rate` on both surfaces while four entries here still read
    *"an ex-date is calendar noise in the analyst reasoning prompt"*. Four
    permanent lies, invisible to every existing guard.

    An omission entry is a claim that the field is NOT rendered. This checks the
    claim.
    """
    contradicted = []
    for (source, surface, field) in INTENTIONALLY_OMITTED:
        fp = env.fingerprints[source].get(field)
        if fp is not None and fp in env.surfaces[(source, surface)]:
            contradicted.append((source, surface, field))
    assert not contradicted, (
        "these fields ARE rendered but are still listed in INTENTIONALLY_OMITTED, "
        "so the registry asserts the opposite of what the code does — and the "
        f"omission suppresses the parity check for them: {sorted(contradicted)}. "
        "Delete the entry; the field is covered by the normal parity check now."
    )


def test_parity_check_is_non_vacuous(env):
    """A green result must mean 'all rendered', never 'found nothing': every source
    must produce fields AND render at least one on each of its surfaces."""
    for source, surfaces in _SURFACES_BY_SOURCE.items():
        assert env.produced[source], f"{source} produced no fields — enumeration broke"
        for surface in surfaces:
            text = env.surfaces[(source, surface)]
            rendered = [
                f for f, fp in env.fingerprints[source].items() if fp in text
            ]
            assert rendered, (
                f"no {source} field fingerprint found on {surface!r} — the renderer "
                "or the injection is wired wrong, so a green parity result is vacuous"
            )


# ── Guard-on-the-guard (mandatory): prove the check actually bites ────────────


def test_guard_on_the_guard_new_field_goes_red_until_declared(env):
    """Add a field to a fetcher's output and the parity check must go RED until it
    is rendered-or-declared. Uses the REAL social block + REAL produced set plus a
    phantom field: if the guard passed when a freshly produced field is dropped, it
    would be theatre."""
    social_block = env.surfaces[("social", "one_on_one")]
    produced_plus = set(SocialSentiment._fields) | {"phantom_new_field"}
    omitted = _omitted_fields("social", "one_on_one")

    # RED: the phantom field is neither rendered nor declared.
    missing = _unrendered(produced_plus, env.fingerprints["social"], omitted, social_block)
    assert "phantom_new_field" in missing

    # GREEN: declaring it (an INTENTIONALLY_OMITTED entry) clears it.
    missing_after_declare = _unrendered(
        produced_plus, env.fingerprints["social"], omitted | {"phantom_new_field"}, social_block
    )
    assert "phantom_new_field" not in missing_after_declare


def test_guard_on_the_guard_dropping_a_rendered_field_goes_red(env):
    """The other direction: if a currently-rendered field stops appearing in the
    block, the check must catch it. Simulate the drop by stripping the field's
    fingerprint out of the real rendered text."""
    social_block = env.surfaces[("social", "one_on_one")]

    # Baseline: mentions IS rendered, so the check is green for it.
    assert _unrendered({"mentions"}, env.fingerprints["social"], set(), social_block) == []

    # Drop it: the check goes red.
    broken = social_block.replace(env.fingerprints["social"]["mentions"], "REDACTED")
    assert _unrendered({"mentions"}, env.fingerprints["social"], set(), broken) == ["mentions"]
