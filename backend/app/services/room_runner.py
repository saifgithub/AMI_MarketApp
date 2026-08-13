"""Convene the Room — the multi-agent debate orchestrator.

A Room run is a 6-phase, 12-agent sequence that produces a single Verdict
on a ticker. The phases:

  Phase 1 — up to 4 Analysts run in parallel (fewer for a tenure-degraded
            FLOOR_PASS roster, CR098 — Fundamentals always present).
  Phase 2 — Bull and Bear Researchers build cases.
  Phase 3 — Research Manager synthesises.
  Phase 4 — Trader proposes a specific trade.
  Phase 5 — 3 Risk Debators argue sizing.
  Phase 6 — Portfolio Manager runs compliance + final verdict.

The runner produces an async iterator of `AgentMessage`s (streamed live)
followed by a final `Verdict`. The full RoomRun is captured at the end
and persisted to Postgres so the Decision Journal can replay the
transcript verbatim.

MVP scaling tradeoff: instead of fanning out 12 real LLM calls (cost +
latency), the alpha runner uses **deterministic per-agent scripts**
parameterised by ticker. Each phase yields one or more `AgentMessage`s
with realistic-shaped reasoning. Live LLM swap-in is a single-function
change.

The PM's verdict goes through the same deterministic safety floor function
used in 1-on-1 — see app/agents/safety_floor.py. A user with `halal=True`
who runs the Room on a non-halal ticker will see the LLM-style approval
flipped to REJECT by the floor. That's the safety floor working live.

Spec: docs/initial_specs/02_agents/convene_the_room.md
"""

from __future__ import annotations

import asyncio
import random
import re
import zlib
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, select

from app.agents.safety_floor import (
    CONTEXT_NOT_SUPPLIED,
    check_mandate_compliance,
    enforce_safety_floor,
)
from app.core.config import settings
from app.core.logging import logger
from app.core.time import relative_day_phrase
from app.db import get_session, init_schema
from app.db.models import BacktestRunIndexRow, RoomRunRow
from app.services.asof_context import AsOfContext, asof_scope
from app.schemas import AgentId, AgentMessage, Mandate
from app.schemas.journal import EntryType, JournalEntryCreate, Outcome
from app.schemas.mandate import Plan
from app.schemas.room import RoomRun, RoomStatus, Verdict, VerdictAction
from app.schemas.trade import OrderType, ProposedTrade, Side
from app.services.fundamentals import fetch_fundamentals, fetch_live_fundamentals
from app.services.journal_store import get_journal_store
from app.services.market_data import get_market_data_provider
from app.services.sharia_universe import default_halal_universe_async  # CR069 (import for the :1293 rewire)
from app.services.classification_universe import default_classification_universe_async  # DEF061
from app.services.sector_allocation import allocate_by_sector, default_sector_map  # CR026
from app.services.news_context import (
    LiveDataState,
    NewsFeed,
    fetch_live_news,  # re-exported: prompt-parity guard patches it here
    format_headline,
    resolve_news_feed,
)
from app.services.technicals import compute_technicals
from app.services.social_context import (
    SocialFeed,
    fetch_live_sentiment,  # re-exported: prompt-parity guard patches it here
    format_community_read,
    format_engagement,
    format_fetched_age,
    format_mention_trend,
    format_pattern,
    format_sample_size_caveat,
    format_sentiment_score,
    format_sentiment_split,
    format_sentiment_tone,
    format_subreddit_split,
    resolve_social_feed,
)
from app.services.llm_gateway import ChatMessage, LLMGateway, get_llm_gateway
from app.services.llm_json import extract_json_object
from app.services.room_prompts import (
    STANCE_HEADLINE_MAX_CHARS,
    build_room_messages,
    max_tokens_for,
)
from app.services.credit_service import (
    balance_for,
    live_data_surcharge,
    refund,
    room_cost_for_plan,
    spend,
)
from app.services.entitlements import (
    AnalystRoster,
    effective_plan_for_user,
    resolve_roster_for_user,
)
from app.services.tier_policy import pick_tier
from app.services.alpaca_service import snapshot_text as alpaca_snapshot_text
from app.services.sim_engine import get_sim_engine
from app.trading_math.portfolio import shares_for_size
from app.trading_math.risk import drawdown_contribution
from app.trading_math.sizing import resolved_single_name_cap_pct, risk_debator_sizes
from app.trading_math.trade import risk_reward, rr_is_coherent, trade_asymmetry
from app.trading_math.valuation import multiple_compression_downside, net_position_phrase


# ── Startup auto-retry policy (eeeb866f, AT:R34) ──────────────────────────
#
# When the api container restarts mid-run, the startup sweep (see
# _sweep_stuck_runs) auto-retries the run from scratch instead of marking
# it failed and forcing the user to manually resubmit. retry_count on the
# row caps this at MAX_AUTO_RETRIES — a run that dies twice is likely a
# real bug, not a transient restart, and gets surfaced as failed.
MAX_AUTO_RETRIES = 1


# ── Phase definition ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class _Phase:
    label: str
    agents: tuple[AgentId, ...]
    # CR077 Phase 2: True ⇒ this phase's agents do NOT read each other's output,
    # so their LLM calls run concurrently (asyncio.gather) instead of strictly
    # sequentially. The single source of truth for the decision — the loop keys
    # on THIS flag, never on the label string — and the phase-parallelism guard
    # (test_cr077_phase_parallelism.py) asserts the set of parallel phases is
    # EXACTLY {ANALYSTS}. Marking a debate phase (RESEARCHERS/RISK/VERDICT)
    # parallel would silently delete the debate while every other test passes
    # and the UI still renders every contribution — DEF084's exact shape — which
    # is what the guard exists to catch.
    parallel: bool = False


PHASES: tuple[_Phase, ...] = (
    # The four analysts are four independent lenses on ONE shared data block, not
    # a dependency chain (CR077 §"Evidence added 2026-07-23": news quoted social's
    # sentiment score while speaking BEFORE social — it read the profile, not the
    # transcript). So they are blind to each other by construction already; running
    # them concurrently removes serialization latency without changing what the
    # phase is. Every OTHER phase is a genuine debate and stays sequential.
    _Phase("ANALYSTS", (
        AgentId.FUNDAMENTALS_ANALYST,
        AgentId.MARKET_ANALYST,
        AgentId.NEWS_ANALYST,
        AgentId.SOCIAL_MEDIA_ANALYST,
    ), parallel=True),
    _Phase("RESEARCHERS", (AgentId.BULL_RESEARCHER, AgentId.BEAR_RESEARCHER)),
    _Phase("SYNTHESIS", (AgentId.RESEARCH_MANAGER,)),
    _Phase("EXECUTION", (AgentId.TRADER,)),
    _Phase("RISK", (
        AgentId.AGGRESSIVE_DEBATOR,
        AgentId.CONSERVATIVE_DEBATOR,
        AgentId.NEUTRAL_DEBATOR,
    )),
    _Phase("VERDICT", (AgentId.PORTFOLIO_MANAGER,)),
)


# ── Per-agent canned reasoning templates ──────────────────────────────────

# Each template renders one realistic-shaped contribution for the alpha.
# A live LLM swap reads the same context dict and produces real reasoning.

_TEMPLATES: dict[AgentId, list[str]] = {
    AgentId.FUNDAMENTALS_ANALYST: [
        # No sector/peer P/E comparison — DEF053 (AT:R58) dropped the old
        # always-fake `sector_pe` rather than half-fixing it; nothing here
        # claims a peer-average multiple this app doesn't actually compute.
        # DEF233: both bases, since the trailing multiple alone was what the
        # Room kept rejecting growth and cyclical names on.
        "{ticker} trades at a trailing P/E of {pe}x{forward_pe_clause}. "
        "TTM revenue growth {rev_growth}%; profit margin {profit_margin}%. "
        "Balance sheet: {net_cash_phrase}. "
        "On the fundamentals alone, the name is {valuation_tone}.",
    ],
    AgentId.MARKET_ANALYST: [
        # "{trend}" is compute_technicals' measured read — uptrend, downtrend
        # or consolidating (DEF227; it used to be direction-blind). The
        # sentence is worded so all three substitute grammatically. The range
        # is described as the 50-day range it is, not a "breakout level"
        # (DEF229b), and the last close is stated rather than left to be
        # joined from elsewhere (DEF228). Still tied to no MA window this
        # template doesn't compute (DEF052, AT:R58 — was previously "the
        # 200-day", a claim the real computation never backed).
        "Daily chart read for {ticker}: {trend}, measured against the 20/50-"
        "day moving averages. RSI({rsi}) — {rsi_tone}. 50-day range "
        "${support}–${breakout}, last close ${last_close}. 52-week range "
        "${low}–${high}. Volume {volume_tone}.",
    ],
    AgentId.NEWS_ANALYST: [
        # CR038: macro/Fed tone dropped — no macro-calendar feed backed it and
        # it was asserted as fact 70% of the time despite an explicit
        # disclosure. Fixed at source, not by prompting harder.
        "{ticker}'s last catalyst was {catalyst}. Forward catalyst: "
        "{forward_catalyst}.",
    ],
    AgentId.SOCIAL_MEDIA_ANALYST: [
        # Neutral wording, same discipline as NEWS_ANALYST above — the
        # field VALUES carry the real-vs-illustrative honesty (see
        # social_context.py's format_* helpers / room_runner.py's synthetic
        # defaults), not the template text, since this template renders
        # identically whether Adanos is configured or not (AT:R57).
        "Retail sentiment on {ticker} reads as {sentiment_tone} ({sentiment_score}). "
        "{mention_trend}. Community read: {influencer_take}. Pattern: {pattern}.",
    ],
    AgentId.BULL_RESEARCHER: [
        "Thesis: {bull_thesis}. Evidence: {bull_evidence}. What the market is "
        "missing: {bull_missing}. Sizing implication: this supports a {bull_size}% "
        "position. Falsification: I'd be wrong if {bull_falsifier}.",
    ],
    AgentId.BEAR_RESEARCHER: [
        "Risk: {bear_risk}. Quantification: {bear_quant}. Catalysts to watch: "
        "{bear_catalyst}. Sizing implication: cap exposure at {bear_size}%. "
        "What would invalidate the bear case: {bear_invalidator}.",
    ],
    AgentId.RESEARCH_MANAGER: [
        "Synthesis. Bull thesis is well-defended on growth; Bear's multiple-compression "
        "risk is real but partially priced. Asymmetry looks like ~{upside}% upside vs "
        "{downside}% downside. Lean: {synth_lean}. Sized to your mandate "
        "(risk_score={risk_score}), the right starting position is {synth_size}% of portfolio.",
    ],
    AgentId.TRADER: [
        "Translating the synthesis: {action} {ticker} at ${entry}. Stop ${stop} "
        "({stop_basis}). Target ${target} (R:R = {rr}:1). "
        "Time horizon: {horizon_weeks} weeks. Position size: {size_pct}% of portfolio.",
    ],
    AgentId.AGGRESSIVE_DEBATOR: [
        "Push size to {agg_size}%. Asymmetry is good, the technical setup is clean, "
        "and conviction across the team is high. We're under-sizing if we go below this.",
    ],
    AgentId.CONSERVATIVE_DEBATOR: [
        "Cap size at {cons_size}%. Earnings season volatility, drawdown not yet "
        "recovered, and the macro print next week could re-rate the multiple. "
        "Capital preservation first.",
    ],
    AgentId.NEUTRAL_DEBATOR: [
        "The middle path: stay at {neu_size}%. Aggressive is right that this is "
        "a quality setup; Conservative is right that the macro window is fragile. "
        "Neutral sizing respects both.",
    ],
    AgentId.PORTFOLIO_MANAGER: [
        "Verdict: {verdict_action}. {verdict_rationale} "
        "Mandate check: {mandate_check}.",
    ],
}


# ── Ticker-flavoured profile generator ────────────────────────────────────

# Real 2026 FOMC decision dates (press-conference day = 2nd day of each
# 2-day meeting), from the Fed's official calendar:
# https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
# CR034: replaces a hardcoded "FOMC decision in 11 days" literal that was
# only ever true on the one day it was written. Needs a manual refresh once
# the Fed publishes next year's schedule.
_FOMC_DECISION_DATES = [
    date(2026, 1, 28), date(2026, 3, 18), date(2026, 4, 29), date(2026, 6, 17),
    date(2026, 7, 29), date(2026, 9, 16), date(2026, 10, 28), date(2026, 12, 9),
]


def _forward_catalyst_text(today: date | None = None) -> str:
    """Real days-to-next-FOMC-decision (CR034). The sector-earnings-season
    half used to ride along here as "(illustrative, not date-verified)" —
    CR038 removed it at source: no earnings-calendar feed backed it, and
    the disclosure didn't stop agents citing it as fact 70% of the time."""
    today = today or datetime.now(timezone.utc).date()
    upcoming = [d for d in _FOMC_DECISION_DATES if d >= today]
    if upcoming:
        days_out = (upcoming[0] - today).days
        return f"FOMC decision in {days_out} day{'s' if days_out != 1 else ''}"
    return "next FOMC decision date not yet published"


@dataclass
class _RoomContext:
    ticker: str
    mandate: Mandate
    portfolio_value: float
    current_drawdown_pct: float
    halal_universe: set[str]
    classification_universe: object | None
    locale_allowed_universe: set[str] | None
    user_id: UUID | None = None
    # CR055: the always-present portfolio-of-record block (sim holdings + optional
    # Alpaca overlay), built once per run and injected into every agent's prompt.
    portfolio_snapshot: str | None = None
    # CR026: the sector-concentration inputs, built once per run. `sector_map` is the
    # snapshot-backed resolver (no request socket); `sector_holdings`/`sector_marks`
    # feed the deterministic cap check the PM verdict is vetoed against; `sector_weights`
    # is the computed donut injected into the PM prompt context.
    sector_map: object | None = None
    sector_holdings: list = field(default_factory=list)
    sector_marks: dict[str, float] = field(default_factory=dict)
    sector_weights: dict[str, float] = field(default_factory=dict)
    # CR101-BE2 round 2: the same cooldown/over-trading/open-risk trade-history
    # context sim_engine.py builds for its own check_mandate_compliance calls, built
    # once per run so the Room path stops silently skipping these three limits.
    # `CONTEXT_NOT_SUPPLIED` (not None/[]/0.0) on failure — a real "no prior loss"
    # or "no open risk" is a value the floor must accept; an outage computing that
    # value must not be indistinguishable from it (CR040 degrade-loudly).
    risk_last_loss_closed_at: object = field(default=CONTEXT_NOT_SUPPLIED)
    risk_trade_open_timestamps: list | None = None
    risk_existing_open_risk_pct: float | None = None
    # Populated as phases progress
    bull_thesis: str = ""
    bear_risk: str = ""
    synth_size_pct: float = 3.0
    trader_size_pct: float = 3.0
    trader_entry: float = 100.0
    trader_stop: float = 96.0
    trader_target: float = 115.0
    trader_horizon_weeks: int = 6
    aggressive_size_pct: float = 5.0
    conservative_size_pct: float = 1.5
    neutral_size_pct: float = 3.0
    profile: dict[str, Any] = field(default_factory=dict)
    # CR098 — the analysts withheld this run (tenure pull-back), by AgentId.
    # Empty for every plan except FLOOR_PASS past a threshold.
    withheld: tuple[AgentId, ...] = field(default_factory=tuple)
    roster_next_step: tuple[AgentId, int] | None = None


# CR104 — the numeric fundamentals fields tracked per-field in
# `profile["field_state"]`. Each is LIVE only if `fetch_live_fundamentals`
# actually returned that key; there is no synthetic fallback.
_FUNDAMENTALS_NUMERIC_FIELDS = (
    "base_price", "pe", "rev_growth", "profit_margin", "net_cash",
)
# Optional live-only fields with no synthetic counterpart at all. CR104/D8:
# presence-only gating at the render sites was the round-2 MAJOR-2 defect —
# each field's `field_state` entry below is what every render site now
# actually consults.
_FUNDAMENTALS_OPTIONAL_LIVE_ONLY_FIELDS = (
    # DEF233: `forward_pe` is optional rather than a core numeric field
    # because yfinance omits it for names with no forecast earnings, and a
    # non-positive forecast multiple is dropped at the fetcher — so its
    # absence is normal and gets stated, not treated as a provider outage.
    # `peg_basis` is the denominator the PEG figure was built on, carried
    # through the same per-field provenance as the number itself.
    "forward_pe", "price_to_sales", "ev_to_ebitda", "peg_ratio", "peg_basis",
    "fcf_yield", "dividend_yield", "sector", "industry",
    "analyst_target_price", "analyst_rating",
    # CR145 Tier A — fetched since DEF053 and consumed only as the FCF-yield
    # numerator/denominator and inside `net_cash`, never rendered. Optional
    # rather than core: yfinance omits any of the three for some names, and an
    # absence there is normal, not a provider outage.
    "market_cap", "free_cash_flow", "total_debt",
    # CR168 (folded into CR166) — resolved instrument identity. Strings, so they
    # never reach M3's numeric provenance count, but they ride the same per-field
    # `field_state` scheme as everything else: an unmapped exchange code and an
    # absent `longName` (NBIS) render as absent, never as a guess.
    "long_name", "exchange_name",
    # CR166 Tier B — all fetched inside the SAME `yf.Ticker(t).info` call that
    # already serves every field above, then discarded at the render site. The
    # census that found them counted 180 keys returned, 23 read, 112 numeric
    # fields never passed to any agent. Optional-live-only for the same reason
    # as CR145 Tier A: yfinance omits any of these for some names (SNDK has no
    # debtToEquity, a non-payer has no dividend rate) and that absence is
    # normal, not an outage.
    "gross_margin", "operating_margin",
    "trailing_eps", "revenue_ttm", "revenue_per_share",
    "return_on_equity", "return_on_assets",
    "current_ratio", "quick_ratio", "debt_to_equity", "payout_ratio",
    "analyst_opinion_count", "analyst_target_high", "analyst_target_low",
    "analyst_target_median", "analyst_rating_score",
    "held_pct_institutions", "held_pct_insiders",
    "shares_outstanding", "float_shares",
    # CR145 Tier D — margin TREND and buybacks, from `.quarterly_income_stmt`
    # and `.quarterly_cashflow` behind the 6h TTL cache the tier was gated on.
    # Optional-live-only for a sharper reason than the fields above: absence
    # here is COMMON and meaningful. A company with fewer than five quarters of
    # filings has no year-over-year comparison, and one that reports no
    # repurchase line is not the same as one that repurchased zero — measured,
    # NBIS and KTOS carry no `Repurchase Of Capital Stock` row while SNOA does.
    "gross_margin_trend_bps", "operating_margin_trend_bps",
    "net_margin_trend_bps", "margin_trend_basis",
    "buyback_ttm", "buyback_yield",
    # CR179 Leg 3 — gross cash, the half of CR145 Tier A's own argument that
    # shipped without it (gross debt renders, gross cash did not).
    "total_cash",
    # CR179 Leg 3 — the technicals-lane keys `.info` has always returned, held
    # under a "CR166 stage 3" census exemption and rendered by nobody. They
    # arrive from `.info` rather than from `compute_technicals`, so each carries
    # its OWN provenance and renders independently of `field_state["technicals"]`
    # — an OHLCV outage must not hide a 200-day average that is genuinely live.
    "day_change_pct", "market_state",
    "sma_200", "price_vs_sma_200_pct",
    "volume_today", "volume_avg_3m",
    "change_52w_pct", "change_52w_sp500_pct", "relative_strength_52w_pct",
    # CR150 — the Bear Researcher's quantified downside.
    "beta", "short_pct_float", "short_days_to_cover", "short_interest_date",
)

# CR166 Tier B — the dividend fields CR030 already fetches onto `EarningsInfo`
# for the mobile dividend chip, which the Room then dropped at the render site
# even though its next-earnings line comes off that same object. NOT in the
# tuple above: that one is iterated against `fetch_live_fundamentals`' return,
# and these arrive from `get_market_data_provider().earnings()`. Their
# provenance is recorded where that call is handled, on the same per-field
# scheme (CR104) as everything else.
_EARNINGS_DIVIDEND_FIELDS = ("ex_dividend_date", "dividend_rate")


def _forward_pe_clause(profile: dict[str, Any]) -> str:
    """The forward-P/E clause of the scripted Fundamentals sentence (DEF233).

    A clause rather than a bare `{forward_pe}` substitution so an absent
    figure reads as a sentence — the backfill that covers the rest of the
    scripted template renders the literal "not available", which would land
    as "not availablex" mid-sentence. Absence is stated either way; the
    scripted path never quietly drops a basis the fact sheet would have named.
    """
    forward = profile.get("forward_pe")
    if not forward:
        return ", forward P/E not available"
    return f", {forward}x on consensus forward estimates"


def _profile_for_ticker(
    ticker: str,
    *,
    news_feed: NewsFeed | None = None,
    social_feed: SocialFeed | None = None,
    withheld: frozenset[AgentId] = frozenset(),
    as_of: date | None = None,
) -> dict[str, Any]:
    """Ticker-flavoured profile for the Room.

    CR104: numeric facts (base_price, pe, rev_growth, profit_margin,
    net_cash, and the RSI/trend/range/volume technicals block) are LIVE
    or ABSENT — no rng-seeded fallback. Before CR104 this function built a
    complete fake company with `random.Random(seed=ticker)` before any live
    fetch, then `dict.update`d live data on top; any field yfinance didn't
    supply silently kept its rng value under a "LIVE from Yahoo Finance"
    header (DEF123: 178 of 842 live-declared prompts carried a fabricated
    P/E across 36 tickers). `_format_profile` (room_prompts.py) now refuses
    to render a numeric field with no recorded provenance — see
    `profile["field_state"]`, the per-field source-of-truth this function
    populates below.

    Narrative fields (catalysts, sentiment, debate framing) remain
    synthetic — that's the CR034 illustrative-scaffolding convention, a
    separate question from numbers that masquerade as measurements
    (CR104's scope). They are honestly labelled "(illustrative)" or, for
    catalyst/sentiment, covered by the news/social liveness markers below.

    The deterministic rng baseline this function used to compute is
    preserved for tests at
    `backend/tests/unit/fixtures/synthetic_room_baseline.py` — nothing
    under `app/` imports it.
    """
    # zlib.crc32, not the builtin hash() — str hashing is randomized per
    # process (PYTHONHASHSEED) unless pinned, so hash() would break
    # determinism: same ticker, different process, different illustrative
    # narrative (DEF057). Only feeds the narrative/illustrative fields below
    # (CR034 convention, explicitly out of CR104's scope) — no numeric fact
    # is derived from this rng anymore.
    rng = random.Random(zlib.crc32(ticker.upper().encode()))
    # DEF124: one "today" for the whole profile, so the run-date anchor, the
    # FOMC countdown and the earnings interval can never disagree with each
    # other mid-render (D4 — UTC calendar date is the stated basis for all
    # three; a market date computed in local time would be off-by-one for
    # part of the trading day).
    # CR164: an as-of Room run substitutes its historical date HERE, at the
    # single anchor everything else hangs off — the fact sheet then states
    # "as of {as_of}" and every relative-day phrase computes from it.
    today = as_of or datetime.now(timezone.utc).date()
    # Per-field provenance (CR104/D1/D4): every numeric fact below is either
    # overlaid from a live source with its state recorded here as LIVE, or
    # left unset with its state recorded as UNAVAILABLE/WITHHELD_* —
    # `_format_profile` (room_prompts.py) renders a field ONLY when
    # `field_state` says so. This dict is the single provenance mechanism;
    # there is no second, block-level flag living beside it.
    field_state: dict[str, str] = {}
    profile: dict[str, Any] = {
        "ticker": ticker.upper(),
        "field_state": field_state,
        # DEF124/D2: the run date is a fact with a real provenance (the
        # clock) — the ONE anchor every other absolute date in the fact
        # sheet is relative to. Recorded through the same per-field scheme
        # as every other numeric fact, not bolted on as an ungated string.
        "run_date": today.isoformat(),
        "catalyst": "Q3 earnings (beat by ~4%)",
        "forward_catalyst": _forward_catalyst_text(today),
        "sentiment_tone": "moderately bullish" if rng.random() > 0.3 else "mixed",
        # No live social feed exists (CR024) — these are illustrative, not
        # measured. Dropped the fake-precision "+X.Xσ" decimal (borrowed a
        # real statistical unit's credibility for a number nobody measured)
        # and the "up 40% week-over-week" string that used to be identical
        # for every ticker regardless of the rng seed.
        "sentiment_score": rng.choice(["elevated", "typical", "subdued"]) + " intensity (illustrative)",
        "mention_trend": rng.choice([
            "elevated versus a typical week (illustrative)",
            "roughly typical for the week (illustrative)",
            "quieter than a typical week (illustrative)",
        ]),
        "influencer_take": "broadly constructive, no euphoria",
        "pattern": "sentiment confirming price, not yet at exhaustion",
        "bull_evidence": "consensus has under-modelled the next 4 quarters of guidance",
        "bull_missing": "supply-chain commentary that suggests upside to FY guide",
        "bull_size": 4,
        "bull_falsifier": "next quarter's guide is reset lower by 10%+",
        "bear_catalyst": "any miss on forward guide, or sector-wide re-rating event",
        "bear_size": 2,
        "bear_invalidator": "next two quarters both beat AND raise",
        "upside": 28,
        "downside": 18,
        "synth_lean": "constructive bull",
    }
    # The clock is unconditionally live — there is no "unavailable" state for
    # today's date. Recorded explicitly rather than assumed, so the taint
    # guard (test_cr104_no_fabricated_numeric_reaches_room_prompt.py) sees a
    # real provenance write, not an implicit default.
    field_state["run_date"] = LiveDataState.LIVE.value

    # Fundamentals: LIVE per-field, or UNAVAILABLE — never a rng fallback
    # (CR104/DEF123). `fetch_live_fundamentals` already only returns the
    # keys yfinance actually supplied (fundamentals.py); a key it omitted
    # (e.g. no trailingPE for a loss-making name) now stays fully absent
    # from `profile` instead of surfacing the old rng value.
    # CR164: the as-of branch goes through the dispatcher (EDGAR PIT path);
    # the live branch keeps calling `fetch_live_fundamentals` BY NAME — it is
    # a monkeypatch seam for a dozen test files, and the dispatcher would put
    # a layer between the seam and the call.
    if as_of is not None:
        live = fetch_fundamentals(ticker, as_of)
    elif settings.use_real_market_data:
        live = fetch_live_fundamentals(ticker)
    else:
        live = None
    for f in _FUNDAMENTALS_NUMERIC_FIELDS:
        if live and f in live:
            profile[f] = live[f]
            field_state[f] = LiveDataState.LIVE.value
        else:
            field_state[f] = LiveDataState.UNAVAILABLE.value
    # 52-week range is its own field: `fetch_live_fundamentals` sets low/high
    # to a ±5% *placeholder* off price alone when the real 52-week fields
    # aren't available — that placeholder is a derived guess, not a
    # measurement, so it only earns "live" provenance when
    # `week52_range_live` says the real fiftyTwoWeek* fields were used.
    if live and live.get("week52_range_live"):
        profile["low"] = live["low"]
        profile["high"] = live["high"]
        field_state["week52"] = LiveDataState.LIVE.value
    else:
        field_state["week52"] = LiveDataState.UNAVAILABLE.value
    if live:
        for f in _FUNDAMENTALS_OPTIONAL_LIVE_ONLY_FIELDS:
            if f in live:
                profile[f] = live[f]
                field_state[f] = LiveDataState.LIVE.value

    if settings.use_real_market_data:
        # Technicals (DEF052, AT:R58): RSI/trend/volume/support-breakout
        # computed from real yfinance OHLCV — one coherent block, so one
        # state covers all of it (unlike fundamentals, yfinance can't
        # return "RSI but not trend"). MACD/moving-average-crossover/
        # Bollinger Bands are deliberately not computed (see
        # technicals.py) — the prompt no longer claims them.
        #
        # CR098 — Market withheld (roster pull-back): skip the fetch (bank
        # the yfinance OHLCV pull, scope item 4). `_format_profile` reads
        # field_state["technicals"] to strip the fact-sheet lines instead
        # of rendering a fabricated RSI/range/volume.
        if AgentId.MARKET_ANALYST in withheld:
            field_state["technicals"] = LiveDataState.WITHHELD_TENURE.value
        else:
            technicals = compute_technicals(ticker)
            if technicals:
                profile["rsi"] = technicals.rsi
                profile["rsi_tone"] = technicals.rsi_tone
                profile["trend"] = technicals.trend
                profile["volume_tone"] = technicals.volume_tone
                profile["support"] = technicals.support
                profile["breakout"] = technicals.breakout
                # DEF228: the last close of the same series the range was
                # measured over, so `_format_profile` can state position-in-
                # range instead of making the agent join to a separately-
                # sourced quote several lines up.
                profile["last_close"] = technicals.price
                # CR150 A2-family: the numbers `trend` and `volume_tone` are
                # bucketings OF. They ride `field_state["technicals"]` with the
                # rest of the block — yfinance cannot return an SMA without the
                # closes the trend read is derived from.
                profile["sma_short"] = technicals.sma_short
                profile["sma_long"] = technicals.sma_long
                profile["volume_ratio"] = technicals.volume_ratio
                field_state["technicals"] = LiveDataState.LIVE.value
            else:
                field_state["technicals"] = LiveDataState.UNAVAILABLE.value
    else:
        field_state["technicals"] = LiveDataState.UNAVAILABLE.value

    if settings.use_real_market_data:
        # Real earnings date, when within the 90-day window the provider
        # covers — closes the "earnings calendar" claim with real data
        # instead of just disclaiming it (cheap: fetch/cache already exist
        # and are already tested via test_sim_news_earnings.py).
        try:
            earnings = get_market_data_provider().earnings(ticker.upper().strip())
        except Exception as exc:
            logger.warn("room_runner_earnings_error", ticker=ticker, error=str(exc)[:200])
            earnings = None
        if earnings and earnings.earnings_date:
            profile["next_earnings_date"] = earnings.earnings_date
            profile["next_earnings_quarter"] = earnings.quarter
            # DEF124/D1: the interval alongside the absolute date, computed
            # in Python against the same `today` as the FOMC line — never
            # asked of the model. `date.fromisoformat` matches the
            # `earnings_date=target.strftime("%Y-%m-%d")` shape every
            # MarketDataProvider.earnings() implementation returns.
            profile["next_earnings_interval"] = relative_day_phrase(
                date.fromisoformat(earnings.earnings_date), today
            )
            field_state["next_earnings"] = LiveDataState.LIVE.value
            # Real forward consensus EPS for the upcoming report (DEF053,
            # AT:R58) — was already fetched here, just never surfaced. A
            # genuine "forward guidance" data point, distinct from the
            # backward-looking rev_growth/profit_margin fields above.
            if earnings.eps_estimate is not None:
                profile["next_earnings_eps_estimate"] = earnings.eps_estimate
        # CR166 Tier B — the CR030 dividend fields off the SAME object, gated on
        # `earnings` alone rather than on `earnings_date`. A dividend payer with
        # no report inside the 90-day window still has an ex-date and a rate, and
        # nesting these under the earnings-date branch would drop them for
        # exactly the names whose next cash event IS the dividend.
        #
        # `as_of is None` because this provider call is LIVE and knows nothing
        # about the backtest clock: in as-of mode it would state today's ex-date
        # on a sheet dated months earlier. NOTE — the `next_earnings` block above
        # has the same exposure and is NOT guarded, so CR164's harness is already
        # reading a live earnings calendar into a point-in-time run. That is a
        # pre-existing defect, filed separately rather than silently widened
        # here; this CR declines to add two more fields to it.
        if earnings and as_of is None:
            if earnings.ex_dividend_date:
                profile["ex_dividend_date"] = earnings.ex_dividend_date
                field_state["ex_dividend_date"] = LiveDataState.LIVE.value
            if earnings.dividend_rate is not None:
                profile["dividend_rate"] = earnings.dividend_rate
                field_state["dividend_rate"] = LiveDataState.LIVE.value

    # CR090 — News/Social liveness is decided by the pre-resolved feeds priced
    # in start_run (D4: charge == render), NOT a second fetch here. A second
    # fetch could disagree with the one we billed, so the surcharge would buy
    # data the agents never saw. Only a LIVE feed overlays its real payload
    # (CR023/CR024, byte-for-byte); WITHHELD_PAID and UNAVAILABLE leave the
    # honest synthetic scaffolding in place (D5) and are told apart ONLY by the
    # 3-state marker recorded below, which the disclosure header reads. When no
    # feed was threaded in (respawn / direct call / tests) we resolve here at
    # entitled=True — the legacy behaviour, where any available live data was
    # overlaid unconditionally; production always threads a pre-priced feed.
    if news_feed is None:
        # Legacy / direct-call fallback: build the feed straight off the
        # module-level fetcher (entitled=True equivalent — any available live
        # data is overlaid, the pre-CR090 behaviour). Production threads a
        # pre-priced feed in and never reaches this branch.
        items = (
            tuple(fetch_live_news(ticker) or ())
            if settings.use_real_market_data else ()
        )
        news_feed = NewsFeed(
            LiveDataState.LIVE if items else LiveDataState.UNAVAILABLE, items
        )
    nf = news_feed
    if nf.state is LiveDataState.LIVE and nf.headlines:
        # Only the top headline replaces `catalyst` — `forward_catalyst` (the
        # real FOMC-date half; CR038 removed the synthetic sector-earnings half)
        # is untouched, since no real earnings-calendar feed exists for it.
        news_items = list(nf.headlines)
        profile["catalyst"] = format_headline(news_items[0])
        profile["news_headlines"] = news_items
    field_state["news"] = nf.state.value

    if social_feed is None:
        # Same legacy / direct-call fallback as news above, off the same
        # module-level fetcher. Going through `resolve_social_feed` here instead
        # would be behaviourally identical but would move the seam every existing
        # caller and test patches (`room_runner.fetch_live_sentiment`) into
        # `social_context`, silently voiding those patches.
        sentiment = (
            fetch_live_sentiment(ticker) if settings.use_real_market_data else None
        )
        social_feed = SocialFeed(
            LiveDataState.LIVE if sentiment is not None else LiveDataState.UNAVAILABLE,
            sentiment,
        )
    sf = social_feed
    # Adanos is Reddit-only — Twitter/X, StockTwits, Google Trends, Discord
    # remain unconnected (CR024).
    if sf.state is LiveDataState.LIVE and sf.sentiment is not None:
        sentiment = sf.sentiment
        profile["sentiment_tone"] = format_sentiment_tone(sentiment)
        profile["sentiment_score"] = format_sentiment_score(sentiment)
        profile["mention_trend"] = format_mention_trend(sentiment)
        profile["influencer_take"] = format_community_read(sentiment)
        profile["pattern"] = format_pattern(sentiment)
        # CR148 Tier A/B — dimensions fetched on this same call since CR024 and
        # dropped on the floor here until AT:R68. Pre-formatted upstream by the
        # Adanos formatters and rendered verbatim (never recomputed in the
        # prompt layer), same contract as the three above. Empty strings/tuples
        # are left out entirely rather than stored, so `_social_detail_lines`
        # never has to distinguish "no engagement data" from "engagement of
        # zero" — the falsy-collapse trap Batch 7 had to design around.
        for key, value in (
            ("sentiment_split", format_sentiment_split(sentiment)),
            ("social_engagement", format_engagement(sentiment)),
            ("social_sample_caveat", format_sample_size_caveat(sentiment)),
            ("social_fetched_age", format_fetched_age(sentiment)),
        ):
            if value:
                profile[key] = value
        community_lines = format_subreddit_split(sentiment)
        if community_lines:
            profile["subreddit_split"] = list(community_lines)
    field_state["social"] = sf.state.value

    # Derive narrative strings (the `_TEMPLATES` scripted-demo fallback used
    # when no real LLM provider is reachable — see module docstring) from
    # the real numbers ONLY when they're actually live. CR104: pe/rev_growth/
    # profit_margin are no longer guaranteed present, so this must degrade
    # loudly (CR040) rather than crash or silently reuse a stale/fake value.
    fundamentals_live = all(
        field_state.get(f) == LiveDataState.LIVE.value
        for f in ("pe", "rev_growth", "profit_margin")
    )
    if fundamentals_live:
        pe_val = float(profile["pe"])
        rev_growth_val = profile["rev_growth"]
        profit_margin_val = profile["profit_margin"]
        is_growth = pe_val > 30 and rev_growth_val > 15
        profile["is_growth"] = is_growth
        profile["valuation_tone"] = (
            "fairly priced relative to growth" if is_growth
            else "trading at a discount to its peers"
        )
        profile["bull_thesis"] = (
            f"{ticker.upper()}'s revenue growth ({rev_growth_val}%) and profit margin "
            f"({profit_margin_val}%) justify a premium multiple"
        )
        profile["bear_risk"] = (
            f"multiple compression if growth decelerates — {pe_val:.0f}x is sensitive"
        )
        # DEF077: the inline `int(pe/(pe+10)*100-50)` was simply wrong — it printed
        # ~16% for a real 50% drop. A delta-point compression of a P/E is a delta/pe
        # drawdown (price ∝ multiple, earnings held). Computed in trading_math (M07).
        downside = multiple_compression_downside(pe_val, 10)
        profile["bear_quant"] = (
            f"a 10-point multiple compression = ~{downside:.0f}% downside"
            if downside is not None
            else "a multiple compression would pressure the price"
        )
    else:
        profile["is_growth"] = False
        profile["valuation_tone"] = "not enough live data to assess"
        profile["bull_thesis"] = (
            f"live fundamentals for {ticker.upper()} are not available this session"
        )
        profile["bear_risk"] = "live fundamentals are not available to size this risk"
        profile["bear_quant"] = "insufficient live data for a downside estimate"
    return profile


# ── Verdict assembly ──────────────────────────────────────────────────────


# DEF241 — which run-context size each RISK debator is arguing for. Only the three
# debators have a size of their own; every other agent gets `None` and sees the
# reference-position figure alone, unchanged. A table rather than an if-chain so a
# fourth voice added later is a visibly missing key rather than a silent fall-through
# to "no figure" — which is exactly the shape DEF238 cost us on the sector line.
_DEBATOR_SIZE_ATTR: dict[AgentId, str] = {
    AgentId.AGGRESSIVE_DEBATOR: "aggressive_size_pct",
    AgentId.CONSERVATIVE_DEBATOR: "conservative_size_pct",
    AgentId.NEUTRAL_DEBATOR: "neutral_size_pct",
}


# DEF240 — above this share of the portfolio in ONE name, AMI states the
# concentration in plain words instead of letting it pass as an ordinary number.
#
# Saiful's ruling, 2026-08-08, asked as a product question after three per-agent
# reviews found the same thing independently: *"Keep it, but make AMI say the
# number out loud."* Nothing here is broken — `day_trader_preset.py` really does
# set `single_name_cap_pct: 100.0`, 7 of 18 epoch convenes ran under it, and
# `resolved_single_name_cap_pct` is the same resolver the safety floor clamps to,
# so shown == enforced. The agents were behaving correctly when the Bull argued
# 50% of portfolio in one name and the Aggressive argued 100% into a book already
# 95.8% GME.
#
# The defect is DISCLOSURE, not enforcement. A simulator whose purpose is teaching
# let a user watch a 12-analyst team argue for a half-portfolio single-name
# position while every rendered figure stayed neutral about what that means. CR040
# inverted: if this ships constantly and quietly, what does the user end up
# believing?
#
# Explicitly NOT a cap on the rendered number — a ceiling on a *reported* figure is
# exactly how DEF235 shipped a wrong one. Loud and correct beats quiet.
#
# 25% is a disclosure threshold, not a risk limit: four equal names is the point
# past which one company's outcome, rather than a portfolio's, is what the book
# tracks. It gates a sentence, never a decision — the safety floor remains the
# sole vetoer (DEF059).
_LOUD_CONCENTRATION_PCT = 25.0


def _concentration_note(size_pct: float | None, cap_pct: float | None) -> str:
    """DEF240 — the plain-words concentration statement, or "" below the threshold.

    Two facts and no third thing: the share, and the cap it sits under. AMI is
    simulation-only and does not advise, so neither a caution nor a reassurance
    belongs here.

    **Round-1 audit MAJOR — why the second clause reads the way it does.** It
    first shipped as *"…so the safety floor permits it"*, and the auditor was
    asked to read the sentence for tone rather than scan it for banned words.
    "Permits" is an authorization verb: it carries the same connotation as "the
    law permits it" — not merely *this breaks no rule* but *this is sanctioned*.
    A user who has just watched twelve analysts argue for half their portfolio in
    one name, and then reads that the safety floor permits it, has a
    recommendation-shaped inference handed to them for free.

    The sibling disclosures are the standard this failed against. *"(sized down
    to 40.0% — mandate risk-tier ceiling.)"* and *"(stop/target not stated by
    the PM…)"* state **what happened**; "permits" states **an evaluative
    outcome**. Both are true; only one is a disclosure. So the clause now states
    the comparison and stops: the user still learns why this was not blocked,
    without being told it is therefore a good idea.

    No word list can settle this — "permits" was never a banned-word candidate
    because it is not advice-shaped in isolation, only in this position as the
    sentence's conclusion. The assertions below are a floor, not the check; the
    check is a human reading it.
    """
    if size_pct is None or size_pct <= _LOUD_CONCENTRATION_PCT:
        return ""
    cap = (
        f" Your mandate's single-name cap is {cap_pct:.1f}%; this position does "
        f"not exceed it."
        if cap_pct is not None else ""
    )
    return (
        f" (Concentration: this is {size_pct:.1f}% of the portfolio in one name."
        f"{cap})"
    )


def _risk_tier_size_ceiling(mandate: Mandate) -> float:
    """Max position size (%) for a mandate's risk tier — a ceiling the PM's
    LLM-decided size gets clamped to (DEF056), and the default cosmetic size
    for the pre-debate aggressive/conservative/neutral display values.

    Canonical resolver lives in app.trading_math.sizing (CR046 M03 / CR101-BE1):
    the mandate's explicit, settable `single_name_cap_pct` when set, else the
    risk-tier preset — the same value the Trader's prompt narration now reads,
    so shown == enforced."""
    return resolved_single_name_cap_pct(mandate.risk_score, mandate.single_name_cap_pct)


# ── Portfolio holdings block (CR055) ──────────────────────────────────────

_SIM_PORTFOLIO_HEADER = (
    "─── YOUR SIMULATED PORTFOLIO (AMI's portfolio of record — simulation-only) ───"
)


def _prompt_open_risk(value: object) -> object:
    """DEF263 — translate the Room's `None` into the sentinel, for the PROMPT only.

    `_build_room_risk_limit_context` returns `(CONTEXT_NOT_SUPPLIED, None, None)`
    on every failure path, so open risk reaches the prompt as a plain `None`
    that MEANS "could not compute" while being indistinguishable from "the
    caller never asked". `_risk_state_block` renders the second case as nothing,
    so the outage was silent — and silent in the worst possible state, because
    `enforce_safety_floor` treats `existing_open_risk_pct is None` as **block
    every BUY** (the open-risk cap is always active; CR129 resolves an unset one
    from `max_drawdown_pct`). The Room therefore argued about size, with no line
    on the sheet, while the floor was refusing everything.

    Translated HERE and not in the renderer: the renderer genuinely cannot tell
    an outage from a caller that never asked, and collapsing the two there would
    make `prompt_version.py` and every non-Room caller announce that the floor is
    blocking a BUY nobody proposed. The runner is the only layer that knows which
    of the two its own `None` meant.

    The FLOOR still receives the untranslated `ctx` value — it keys on `is None`,
    and handing it a sentinel would fall through to `float()` on an `object`.
    """
    return CONTEXT_NOT_SUPPLIED if value is None else value


def _stop_clause(
    sym: str, stops: dict[str, set[float]], unstopped: dict[str, int]
) -> str:
    """The per-position stop, or a LOUD statement that there isn't one.

    CR040 — an unstopped position must never render as silence. Before this, the
    holdings block stated size and unrealised P&L and said nothing about
    protection, so a Room reasoning about "existing open risk" could not tell a
    fully-stopped book from a naked one. "no stop recorded" is the whole point:
    it is the position the risk figures cannot account for.

    One name can hold several lots at different stops. They are listed rather
    than averaged — a mean of two stops is a level nobody set, and minting one
    here is exactly the class of invented number DEF235 closed.
    """
    have = sorted(stops.get(sym, ()))
    missing = unstopped.get(sym, 0)
    if have and not missing:
        levels = ", ".join(f"${s:g}" for s in have)
        return f" — stop {levels}" if len(have) == 1 else f" — stops {levels}"
    if have and missing:
        levels = ", ".join(f"${s:g}" for s in have)
        return (
            f" — stops {levels}, and {missing} lot{'s' if missing > 1 else ''} "
            f"with NO stop recorded"
        )
    return " — NO stop recorded (this position is unprotected)"


def _build_sim_holdings_block(user_id: UUID | None, ticker: str) -> str:
    """The user's REAL simulated holdings, rendered for EVERY Room agent (CR055).

    Why this exists: the Room used to inject a holdings block only when the user had
    linked an Alpaca paper account, so a brand-new user got ZERO holdings data — pure
    silence. The model resolved the "you know the portfolio" promise against that
    silence by inventing a position (the SCHD incident: a fabricated 10–15% holding
    that made the Trader refuse to buy). This block is ALWAYS present: a new/empty user
    gets an explicit "you hold 0% of <TICKER>", never nothing.

    Degrades LOUDLY (CLAUDE.md / CR040): any sim-fetch failure renders a visible
    'Portfolio unavailable this run.' line — never an omitted or silent block, because
    silence is precisely the defect this closes (a DEF059-class trap).

    This is AMI's portfolio of record; a linked Alpaca paper account (if any) is folded
    in by `_compose_portfolio_block` as a clearly-labelled external overlay, so exactly
    one authoritative portfolio is emitted.
    """
    ticker_u = ticker.upper()
    if user_id is None:
        return (
            f"{_SIM_PORTFOLIO_HEADER}\n"
            f"No portfolio is attached to this run. You hold 0% of {ticker_u} — treat "
            f"any BUY as opening a NEW position.\n"
            f"───"
        )
    try:
        sim = get_sim_engine()
        portfolio = sim.ensure_portfolio(user_id)
        cash = portfolio.current_cash
        total = sim.total_value(user_id)
        open_trades = sim.list_trades(user_id, status="open")
        # Aggregate open trades per name (a name may have more than one open lot).
        agg: dict[str, list[float]] = {}
        # CR153/154/155/156 (deduped) — the per-lot stop, so the Room can see
        # what each open position actually risks. Collected as a set per name
        # because one name can hold several lots at different stops, and
        # collapsing them to one number would invent a stop nobody set.
        stops: dict[str, set[float]] = {}
        unstopped: dict[str, int] = {}
        for t in open_trades:
            sym = t.ticker.upper()
            row = agg.setdefault(sym, [0.0, 0.0])  # [qty, cost_basis]
            row[0] += t.quantity
            row[1] += t.quantity * t.entry_price
            stop = getattr(t, "stop", None)
            if stop:
                stops.setdefault(sym, set()).add(float(stop))
            else:
                unstopped[sym] = unstopped.get(sym, 0) + 1
        marks = sim.current_marks(list(agg)) if agg else {}
    except Exception as exc:  # noqa: BLE001 — degrade loudly, never silence
        logger.warning(
            "room_sim_holdings_failed",
            user_id=str(user_id),
            error=str(exc)[:200],
        )
        return (
            f"{_SIM_PORTFOLIO_HEADER}\n"
            f"Portfolio unavailable this run. Do NOT assume any holding in {ticker_u} "
            f"or any other name — size every idea as if opening a NEW position.\n"
            f"───"
        )

    lines = [
        _SIM_PORTFOLIO_HEADER,
        f"Cash: ${cash:,.2f} | Portfolio value: ${total:,.2f}",
    ]
    if not agg:
        lines.append(
            f"Open positions: none — you hold nothing yet. You hold 0% of {ticker_u}. "
            f"Any BUY here opens a NEW position."
        )
    else:
        lines.append("Open positions:")
        for sym in sorted(agg):
            qty, cost_basis = agg[sym]
            mark = marks.get(sym, 0.0)
            mkt_value = qty * mark
            weight = (mkt_value / total * 100) if total else 0.0
            unrealised = mkt_value - cost_basis
            lines.append(
                f"  {sym} ×{qty:g} ({weight:.1f}% of portfolio, "
                f"unrealised {unrealised:+,.2f}){_stop_clause(sym, stops, unstopped)}"
            )
        if ticker_u in agg:
            held_qty, _ = agg[ticker_u]
            held_weight = (
                (held_qty * marks.get(ticker_u, 0.0)) / total * 100 if total else 0.0
            )
            lines.append(
                f"You currently hold {held_weight:.1f}% of {ticker_u} — a BUY adds to "
                f"it, a SELL trims it."
            )
        else:
            lines.append(
                f"You hold 0% of {ticker_u} — no open position in it. Any BUY here "
                f"opens a NEW position."
            )
    lines.append("───")
    return "\n".join(lines)


def _build_room_sector_context(
    user_id: UUID | None,
) -> tuple[list, dict[str, float], object | None, dict[str, float]]:
    """The user's sim holdings + marks + snapshot-backed sector resolver + computed
    sector weights (CR026), built once per run. Degrades to empties on any failure —
    the sector cap simply doesn't fire (never blocks on an outage; an unclassified
    sector is 'Other', never a block — the DEF059 guard). No request-path socket."""
    if user_id is None:
        return [], {}, None, {}
    try:
        sim = get_sim_engine()
        portfolio = sim.ensure_portfolio(user_id)
        holdings = list(portfolio.holdings)
        marks = sim.current_marks([h.ticker for h in holdings]) if holdings else {}
        smap = default_sector_map()
        # DEF149: cash is part of the denominator, so the weights the agents reason
        # from are the same ones the floor enforces and the donut draws.
        weights = allocate_by_sector(
            holdings, marks, cash=portfolio.current_cash, sector_of=smap.sector,
        )
        return holdings, marks, smap, weights
    except Exception as exc:  # noqa: BLE001 — degrade, never sink the run
        logger.warning("room_sector_context_failed", user_id=str(user_id), error=str(exc)[:200])
        return [], {}, None, {}


def _build_room_risk_limit_context(
    user_id: UUID | None, *, portfolio_value: float, quotes: dict[str, float],
) -> tuple[object, list | None, float | None]:
    """CR101-BE2 round 2: the same cooldown/over-trading/open-risk trade-history
    context `sim_engine.py` builds for its own `check_mandate_compliance` calls,
    built once per run for the Room's scripted path and the LLM-override wrapper —
    previously neither supplied any of it, so a set `post_loss_cooldown_hours` /
    `max_trades_per_day`/`max_trades_per_week` / `max_open_risk_pct` was silently
    unenforced on the path the user actually watches (round-1 BLOCKER).

    Returns `(last_loss_closed_at, trade_open_timestamps, existing_open_risk_pct)`.
    On no `user_id` or any failure, returns `(CONTEXT_NOT_SUPPLIED, None, None)` —
    NOT `(None, [], 0.0)`. Those look like real values (no prior loss, no trade
    history, zero open risk) and `check_mandate_compliance` would silently pass a
    limit the user explicitly set; `CONTEXT_NOT_SUPPLIED`/`None` make it block
    loudly instead (CR040), same as a caller that forgot the argument entirely.
    """
    if user_id is None:
        return CONTEXT_NOT_SUPPLIED, None, None
    try:
        sim = get_sim_engine()
        return sim.risk_limit_context(
            user_id, portfolio_value=portfolio_value, quotes=quotes,
        )
    except Exception as exc:  # noqa: BLE001 — degrade loudly (see docstring), never sink the run
        logger.warning("room_risk_limit_context_failed", user_id=str(user_id), error=str(exc)[:200])
        return CONTEXT_NOT_SUPPLIED, None, None


def _compose_portfolio_block(sim_block: str, alpaca_snap: str | None) -> str:
    """One portfolio block per run (CR055 precedence).

    The sim block is authoritative — AMI's portfolio of record. A linked Alpaca paper
    account, when present, is appended below it as an explicitly-labelled external
    overlay so the two never read as conflicting portfolios. Most users have no Alpaca
    link, so this returns the sim block unchanged.
    """
    if not alpaca_snap:
        return sim_block
    overlay_label = (
        "─── LINKED EXTERNAL PAPER ACCOUNT (informational overlay only — NOT AMI's "
        "portfolio of record; reason about holdings from the SIMULATED portfolio "
        "above) ───"
    )
    return f"{sim_block}\n\n{overlay_label}\n{alpaca_snap}"


# Normalises PM vocabulary drift to the two Room actions (APPROVE/PASS).
# The Room prompt offers only those two, but the shared PM profile still
# advertises MODIFY-AND-APPROVE (in this schema a modification IS an approval),
# and a model can coin further variants. DEF067: 90% of PM verdicts arrived as
# "MODIFY-AND-APPROVE" — every one a complete, sized APPROVE — and the missing
# synonym silently routed them to the fail-safe PASS. Keys are separator-
# stripped (see _normalize_pm_action); values are the canonical action.
_PM_ACTION_SYNONYMS = {
    "APPROVE": "APPROVE", "BUY": "APPROVE", "ENTER": "APPROVE",
    "MODIFY": "APPROVE", "MODIFYANDAPPROVE": "APPROVE",
    "MODIFYAPPROVE": "APPROVE", "APPROVEWITHMODIFICATION": "APPROVE",
    "APPROVEMODIFIED": "APPROVE",
    "PASS": "PASS", "REJECT": "PASS", "WAIT": "PASS", "HOLD": "PASS", "NO": "PASS",
}

# Token-level fallback for an unforeseen action string. An affirmative token
# with no negation → APPROVE; the reverse → PASS; anything mixed or empty →
# None (caller fails safe to PASS). Safe against fabricating a trade because
# _parse_pm_verdict still refuses an APPROVE that carries no size_pct.
_AFFIRMATIVE_ACTION_TOKENS = {"APPROVE", "APPROVED", "BUY", "ENTER", "MODIFY", "LONG"}
_NEGATION_ACTION_TOKENS = {
    "PASS", "REJECT", "REJECTED", "WAIT", "HOLD", "NO", "NOT", "AVOID", "SKIP", "DECLINE",
}


def _normalize_pm_action(raw: Any) -> str | None:
    """Map the PM's raw action string to 'APPROVE' / 'PASS' / None (DEF067)."""
    text = str(raw or "").upper()
    squashed = re.sub(r"[^A-Z]", "", text)
    if not squashed:
        return None
    if squashed in _PM_ACTION_SYNONYMS:
        return _PM_ACTION_SYNONYMS[squashed]
    tokens = {t for t in re.split(r"[^A-Z]+", text) if t}
    affirm = tokens & _AFFIRMATIVE_ACTION_TOKENS
    negate = tokens & _NEGATION_ACTION_TOKENS
    if affirm and not negate:
        return "APPROVE"
    if negate and not affirm:
        return "PASS"
    return None


_RAW_ACTION_RE = re.compile(r'"action"\s*:\s*"([^"]+)"')


def _raw_is_affirmative(text: str) -> bool:
    """True if a raw PM reply carries an affirmative `action` (DEF067 obs).

    Used only to flag the anomaly where the parser could not read an
    affirmative-looking reply and the reformatter then downgraded it to PASS —
    i.e. an APPROVE we may have lost. Best-effort regex over the raw text so it
    still fires on JSON too malformed for the parser to load."""
    m = _RAW_ACTION_RE.search(text or "")
    return bool(m) and _normalize_pm_action(m.group(1)) == "APPROVE"


def _safe_float(value: Any) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


# DEF232 — what the verdict says when the PM wrote nothing at all.
#
# The PM can return a well-formed decision — action, size, entry, stop, target —
# with an EMPTY `narration`. Until now the two fallbacks below filled that
# silence with a claim: an APPROVE shipped `reason: "Synthesis defended."` (19
# chars) and a PASS shipped `"No trade — debate did not support entry."` (40).
# Both assert something nobody said. The PM defended no synthesis; the debate's
# conclusion was never stated. And `reason` is the string CR106 renders on the
# Verdict Board as the decision's justification, so a user reads a defence that
# does not exist — the CR040 question applied to this field: if this fires
# silently, the user believes the Room deliberated and concluded.
#
# Measured on live Alpha 2026-08-07: 3 of 1016 stored verdicts have a
# zero-length PM turn (1 human — a mid-tier sized/stopped/targeted APPROVE on
# 08-07 — plus 2 room-benchmark PASSes on 07-18), and exactly 1 verdict carries
# a reason under 40 characters. Rare, and user-visible on the surface that
# matters most.
#
# The decision still ships. A missing DECISION fails safe to PASS (DEF059); a
# missing SENTENCE is not the same thing — the levels are the PM's own and the
# safety floor still validates them, so vetoing here would discard a real
# verdict over its prose. What changes is that the silence is stated instead of
# papered over, in the `[AMI …]` voice the client already amber-marks
# (CR106 §3.3: `content.contains('[AMI')`), on BOTH the verdict reason and the
# transcript turn — which was otherwise a blank row in the Room.
_PM_NO_RATIONALE = (
    "[AMI: the Portfolio Manager returned this decision as data only — it wrote "
    "no rationale for the call. Nothing was said to defend it, so there is "
    "nothing here to weigh. Treat it as an unexplained decision, not a "
    "reasoned one.]"
)

# DEF258 — a repaired object is a PARTIAL read, and CR040 says a partial read
# announces itself. The decision fields survive a clip intact (`action`,
# `size_pct` and the levels are all emitted before the long trailing narration),
# so the verdict is honest; the rationale is the half that was lost, and saying
# so is the difference between a short explanation and a truncated one. Same
# `[AMI …]` voice the client amber-marks (CR106 §3.3).
_PM_TRUNCATED_NARRATION = (
    " [AMI: the Portfolio Manager hit its length limit mid-sentence. The "
    "decision and its numbers above are complete; this explanation is cut "
    "short.]"
)

# DEF261 — the same disclosure for the case where the clip landed BEFORE the
# narration value, so NO prose survived at all.
#
# The first cut appended `_PM_TRUNCATED_NARRATION` only `if truncated and
# narration`, which reads as harmless and is not: the clip that removes the
# rationale is exactly the clip that removes the condition. A verdict cut at
# `"narration": ` fell straight through to `_PM_NO_RATIONALE` and published
# *"it wrote no rationale for the call … nothing was said to defend it"* over a
# decision whose rationale WE truncated. That is the DEF232 sentence pointed at
# the wrong cause, and DEF232's own comment names the sin — "Both assert
# something nobody said". Before DEF258's repair those bytes produced a loud,
# TRUE "did not return a machine-readable verdict"; the repair made the output
# readable and the caption false, which is a strictly worse trade.
#
# The distinction is the whole point: "the PM chose not to explain" and "we cut
# the PM off" are different facts about different actors, and only one of them
# is the user's business to judge the PM on.
_PM_TRUNCATED_NO_NARRATION = (
    "[AMI: the Portfolio Manager hit its length limit before its explanation "
    "reached us. The decision and its numbers above are complete and are the "
    "PM's own; the reasoning was cut off in transmission, not withheld. Treat "
    "this as an explanation we lost, not one the PM declined to give.]"
)


# DEF239 (≡ CR156 A2) — the PM writes its rationale under a key that is not
# always `narration`, and reading one key alone published "it wrote no rationale"
# over real prose.
#
# An EXPLICIT allowlist, deliberately not a free-text scrape of the object. The
# `_PM_NO_RATIONALE` disclosure exists for genuinely unexplained decisions
# (DEF232) and scraping any string field would destroy it — a verdict whose only
# prose is `{"ticker": "AAPL"}` would start rendering "AAPL" as a defence.
#
# `narrational` is not hypothetical: it is what the model actually emitted on
# live Alpha, SLB, 2026-08-11 11:27:36Z, in the same verdict that exposed
# DEF258. Ordered by precedence — `narration` is what the contract asks for, so
# it wins when more than one key carries prose.
_PM_NARRATION_KEYS = (
    "narration", "narrational", "rationale", "reasoning", "reason", "explanation",
)


# DEF255 — the boundary above which a stated horizon is not supported by any
# evidence the PM was given. `_HISTORY_PERIOD` is 3 months, fundamentals are
# TTM, and the widest window on the fact sheet is the 52-week range. 365 days is
# that widest window, so a thesis beyond it is being asserted from nothing on
# the sheet. Derived from the inputs, not chosen — and stated as a boundary the
# evidence supports, never as a rule about how long anyone should hold.
_MAX_EVIDENCED_HORIZON_DAYS = 365


def _horizon_coherence_note(
    horizon_days: int | None, entry: float | None, stop: float | None
) -> str:
    """Flag a horizon the stop cannot be serving.

    Measured on the epoch: the PM emits `1095` — the `Horizon.LONG` label
    restated as a number — in 4 of 13 approvals, while the code's own fallback
    for the same field is 42 days. A 26× disagreement inside one field.

    It matters because the two numbers describe one trade, and a tight stop
    paired with a multi-year horizon is a thesis the stop will not survive to
    test.

    **DEF267 — the clause states the pairing and stops there.** The first cut
    asserted the OUTCOME: *"a weeks-to-months instrument — over that horizon
    ordinary volatility would take the position out long before the thesis could
    be judged."* That sentence fired on any stop below entry with **no bound on
    the distance**, so the identical prediction was made for a 1.9% stop and a
    90% one. Those are live numbers, not hypotheticals: the R68-BATCH8 auditor
    found 7 of 25 approvals (28%) carrying a horizon over 365 days with stops
    from 1.9% to 15.8%. And nothing tied the prediction to the figure it printed
    — hardcoding the distance to 6.0 left 142 tests green.

    It could not be made true by bounding it either, because **the stack renders
    no volatility at all**: CR146 Tier A deleted the Market Analyst's ATR and
    stdev demands precisely because nothing supplies them, so "ordinary
    volatility would take this out" is a claim AMI has no input for. The repo's
    own standard for this class is the sibling annotator's, recorded in its
    docstring after DEF240's round-1 audit: **state what happened, never an
    evaluative outcome.** So the note now names both numbers and the tension
    between them, and leaves the judgement to the reader who has it to make.

    Flag only, never a veto — the safety floor is the sole vetoer (DEF059), and
    an incoherent horizon is a reasoning flaw to disclose, not a rule breach.
    """
    if not horizon_days or horizon_days <= _MAX_EVIDENCED_HORIZON_DAYS:
        return ""
    note = (
        f" (AMI: the stated horizon of {horizon_days} days reaches beyond every "
        f"input this decision had — 3 months of price history, TTM fundamentals "
        f"and a 52-week range. Nothing on the fact sheet supports a thesis that "
        f"long.)"
    )
    if entry and stop and entry > 0 and stop > 0 and stop < entry:
        stop_pct = (entry - stop) / entry * 100
        note = note[:-2] + (
            f", and the exit is set {stop_pct:.1f}% below entry — the position "
            f"closes on a {stop_pct:.1f}% move against it, whenever that comes, "
            f"so the {horizon_days}-day thesis is only testable if the price "
            f"never travels that far the wrong way in the meantime.)"
        )
    return note


# DEF264 — keys that are definitionally NOT prose, excluded from the fallback
# below by name rather than by shape. `ticker` is the one DEF239 named as the
# reason a general scrape is unsafe: rendering `{"ticker": "AAPL"}` as a defence
# would destroy the one signal telling a user a decision was never explained.
_PM_NON_PROSE_KEYS = frozenset({"ticker", "action", "symbol", "decision"})

# The length below which an UNKNOWN key's string is treated as metadata rather
# than a rationale. Not invented here: DEF232 characterised a non-explanation by
# this same boundary when it measured "exactly 1 verdict carries a reason under
# 40 characters" across 1,016 stored verdicts. Contracted keys are exempt — a
# short `narration` is still the PM's narration — so this only decides what an
# unrecognised key has to clear.
_PM_MIN_PROSE_CHARS = 40


def _pm_narration(parsed: dict[str, Any]) -> str:
    """The PM's rationale, from whichever key carries it.

    DEF239 replaced a single `parsed["narration"]` read with an allowlist, after
    the model emitted `narrational` once on live Alpha. **DEF264 is the same
    defect again, and it is why an allowlist alone was the wrong shape.** The
    26-convene post-promotion sweep found the PM emitting **`narr`** in 6 of 28
    verdicts (21%) — not a synonym, an ABBREVIATION, which no amount of
    enumerating `rationale`/`reasoning`/`explanation` was ever going to reach.
    All six published *"it wrote no rationale for the call"* over three or four
    paragraphs of real analysis, on the field CR106 renders as the decision's
    justification.

    So the allowlist keeps its job — **precedence**, so `narration` wins when
    several keys carry prose — and a shape test picks up the rest. The shape
    test is deliberately narrow, because DEF239's objection to a general scrape
    stands: a value must be long enough to be an explanation and must not sit
    under a key that is definitionally an identifier. `{"ticker": "AAPL"}` fails
    both, which is the case that mattered.

    The trade is stated rather than hidden: a genuine rationale shorter than
    `_PM_MIN_PROSE_CHARS` under an UNRECOGNISED key is still read as absent. A
    short rationale under a CONTRACTED key is unaffected. That is the direction
    to err — DEF232's disclosure exists for decisions nobody explained, and
    weakening it to catch a 39-character stray would cost more than it saves.
    """
    for key in _PM_NARRATION_KEYS:
        value = parsed.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    # Fallback: the longest prose-shaped value under any other key.
    best_key, best = "", ""
    for key, value in parsed.items():
        if key in _PM_NARRATION_KEYS or key in _PM_NON_PROSE_KEYS:
            continue
        if not isinstance(value, str):
            continue
        candidate = value.strip()
        if len(candidate) >= _PM_MIN_PROSE_CHARS and len(candidate) > len(best):
            best_key, best = key, candidate
    if best:
        # CR040 — the fallback firing means the PM used a key we do not know
        # about, and the ONLY reason DEF264 took a 26-convene sweep to surface
        # is that nothing said so. Now it does, by name, every time.
        logger.warning(
            "room_pm_narration_from_unknown_key",
            key=best_key,
            note="rationale recovered by shape, not by contract — add it to "
                 "_PM_NARRATION_KEYS if it recurs",
        )
    return best


def _parse_pm_verdict(text: str, ctx: _RoomContext) -> tuple[str, Verdict | None]:
    """Extract the PM's display narration + intended decision from its raw
    LLM response (DEF056). Returns (display_text, llm_verdict); llm_verdict
    is None when the response couldn't be trusted as a real decision — the
    caller fails safe to PASS in that case rather than fabricating APPROVE.
    """
    parsed = extract_json_object(text)
    truncated = False
    if parsed is None:
        # DEF258 — the decode budget is a ceiling, and the PM reaches it: 2 of
        # 14 verdicts in the 2026-08-11 post-promotion batch stopped mid-string
        # at exactly `max_tokens`. Strict parsing then returns None, the caller
        # fails safe to PASS (DEF059), and the raw half-written JSON is what
        # reaches the transcript as the PM's turn — the user reads
        # `{ "action": "PASS", "narrational": "REJECT: …` cut off mid-word.
        # Repair is tried ONLY here, ONLY after a strict read has already
        # failed, and its result is disclosed below. Raising the budget was the
        # other option and was rejected: the two clipped samples are censored,
        # so they cannot size a cap (P16), and 12 of 14 finished under 425
        # tokens against a 1100 ceiling — the tail is not a budget problem.
        parsed = extract_json_object(text, repair_truncated=True)
        truncated = parsed is not None
    if parsed is None:
        return text.strip(), None

    narration = _pm_narration(parsed)
    if truncated and narration:
        narration += _PM_TRUNCATED_NARRATION
    # DEF261 — pick the absence sentence from the CAUSE, not from the emptiness.
    # `_PM_NO_RATIONALE` is a statement about the PM's conduct and is only true
    # when the PM had the room to explain and did not use it. On a truncated
    # read the emptiness is ours, so the same sentence becomes a false
    # accusation on the one surface CR106 renders as the decision's
    # justification. Resolved once, here, so neither the PASS branch below nor
    # the APPROVE branch further down can pick the wrong one independently.
    absent_rationale = _PM_TRUNCATED_NO_NARRATION if truncated else _PM_NO_RATIONALE
    action = _normalize_pm_action(parsed.get("action"))
    if action is None:
        return narration or text.strip(), None

    if action == "PASS":
        if not narration:
            logger.warning(
                "room_pm_no_rationale",
                action="PASS", ticker=ctx.ticker, truncated=truncated,
            )
            return absent_rationale, Verdict(
                action=VerdictAction.PASS, reason=absent_rationale
            )
        return narration, Verdict(action=VerdictAction.PASS, reason=narration)

    size_pct = _safe_float(parsed.get("size_pct"))
    if size_pct is None:
        # No size the PM is willing to stand behind — don't invent one.
        return narration or text.strip(), None

    # CR106 B1: `entry` needs THREE provenance values, not two — this `or`
    # silently substitutes the Trader's number for a PM that stated none, and
    # a ribbon drawn from it would attribute the Trader's entry to the PM.
    # The `or` (rather than an explicit None-check) is the shipped behaviour and
    # is kept: a zero entry is not a price either.
    entry_raw = _safe_float(parsed.get("entry"))
    entry = entry_raw or ctx.trader_entry
    entry_src = "pm" if entry_raw else ("trader" if ctx.trader_entry else None)
    # Explicit None-checks (not `or`): a real level is used as-is; only a genuinely
    # missing stop/target is defaulted, and that default is disclosed (audit F6) so
    # a minted ~6%/13% protective level is never shown as a PM-chosen price.
    stop_raw = _safe_float(parsed.get("stop"))
    target_raw = _safe_float(parsed.get("target"))
    # DEF172: neither entry source may hold — entry_raw absent (PM stated
    # none) and ctx.trader_entry absent (no Trader price to fall back to).
    # `entry * 0.94` would then be `None * float`, killing the whole turn.
    # There is no honest level to mint in that case, so the derivation is
    # skipped and stop/target stay whatever the PM stated (possibly None) —
    # the absence surfaces below (reason text + a missing provenance key),
    # never a stack trace and never a silently-dropped field (CR040).
    if entry is not None:
        stop = stop_raw if stop_raw is not None else round(entry * 0.94, 2)
        target = target_raw if target_raw is not None else round(entry * 1.13, 2)
    else:
        stop = stop_raw
        target = target_raw
    try:
        horizon_days = int(parsed.get("horizon_days"))
    except (TypeError, ValueError):
        horizon_days = ctx.trader_horizon_weeks * 7
    horizon_note = _horizon_coherence_note(horizon_days, entry, stop)

    ceiling = _risk_tier_size_ceiling(ctx.mandate)
    if not narration:
        logger.warning(
            "room_pm_no_rationale",
            action="APPROVE", ticker=ctx.ticker, truncated=truncated,
        )
    display = narration or absent_rationale
    reason = display
    if size_pct > ceiling:
        size_pct = ceiling
        reason += f" (sized down to {ceiling:.1f}% — mandate risk-tier ceiling.)"
    _defaulted = [n for n, raw in (("stop", stop_raw), ("target", target_raw)) if raw is None and entry is not None]
    if _defaulted:
        reason += (
            f" ({'/'.join(_defaulted)} not stated by the PM — defaulted to a "
            f"~6%/13%-from-entry protective level, not a PM-chosen price.)"
        )
    _unavailable = [n for n, raw in (("stop", stop_raw), ("target", target_raw)) if raw is None and entry is None]
    if _unavailable:
        reason += (
            f" ({'/'.join(_unavailable)} not stated by the PM, and no entry "
            f"price was available to derive a protective level from.)"
        )
    # DEF240: last, and on the APPROVED size — after the risk-tier clamp above, so
    # the number stated is the position the user actually gets, never the one the
    # PM asked for.
    reason += _concentration_note(size_pct, ceiling)
    # DEF255 — the stop and the horizon must be the same trade. Appended beside
    # the other geometry annotations, and DELIBERATELY not a veto: the safety
    # floor is the sole vetoer (DEF059) and an incoherent horizon is a reasoning
    # flaw to disclose, not a mandate violation to block on.
    reason += horizon_note

    # CR106 B1 — the same facts the sentence above states in prose, in a shape
    # a graphic can be gated on. The sentence STAYS: the board clamps `reason`
    # behind a WHY expander, and demoting the only existing disclosure while
    # promoting the same numbers into a to-scale ribbon would be a net loss of
    # honesty (T-PROV). DEF172: a key is only present for a price that was
    # actually attributed to something — a `None` level (entry unresolved,
    # so stop/target never minted) has no source to name and is omitted
    # rather than mislabelled (T-BACKFILL: absence must read as absence).
    _prov: dict[str, str] = {}
    if entry_src is not None:
        _prov["entry"] = entry_src
    if stop is not None:
        _prov["stop"] = "pm" if stop_raw is not None else "ami_default"
    if target is not None:
        _prov["target"] = "pm" if target_raw is not None else "ami_default"

    return display, Verdict(
        action=VerdictAction.APPROVE,
        size_pct=size_pct,
        entry=entry,
        stop=stop,
        target=target,
        time_horizon_days=horizon_days,
        reason=reason,
        level_provenance=_prov or None,
    )


# A reward-to-risk ratio the PM narrated in prose: "R:R = 3:1", "risk/reward of
# 2.5:1", "a 3:1 risk-to-reward", "R/R 4x". Two orderings — keyword then N:1, or
# N:1 then keyword — with a bounded gap so a distant "20:1 earnings multiple"
# doesn't match. Precision-biased: a missed ratio just means no signal (harmless),
# a spurious one would be telemetry noise.
_PM_RR_KEYWORD = r"(?:r[:/\s-]?r|risk[\s/-]*(?:to[\s-]*)?reward|reward[\s/-]*(?:to[\s-]*)?risk)"
_PM_RR_RATIO = r"(\d+(?:\.\d+)?)\s*(?::\s*1|\s*to\s*1|x)\b"
_PM_STATED_RR_RE = re.compile(
    rf"(?:{_PM_RR_KEYWORD}[^0-9]{{0,20}}?{_PM_RR_RATIO})|(?:{_PM_RR_RATIO}[^0-9]{{0,6}}?{_PM_RR_KEYWORD})",
    re.IGNORECASE,
)


def _extract_stated_rr(text: str | None) -> float | None:
    """Pull the reward multiple (the R in "R:R = R:1") the PM narrated in prose,
    or None when it stated no ratio. Best-effort telemetry input — never a control."""
    if not text:
        return None
    m = _PM_STATED_RR_RE.search(text)
    if m is None:
        return None
    try:
        return float(m.group(1) or m.group(2))
    except (TypeError, ValueError):
        return None


def _pm_rr_coherence_signal(
    pm_text: str | None,
    entry: float | None,
    stop: float | None,
    target: float | None,
) -> dict[str, float] | None:
    """Telemetry payload for a PM APPROVE whose *narrated* R:R contradicts the R:R
    its own entry/stop/target imply (CR046 M06 `rr_is_coherent`). Returns
    {stated_rr, implied_rr} when the PM stated a ratio the levels don't support,
    else None. Flag only — the safety floor owns vetoes; this never changes the
    verdict. `implied_rr` is -1.0 when the levels imply no valid ratio (a stated
    ratio on a degenerate setup is itself incoherent).
    """
    stated = _extract_stated_rr(pm_text)
    if stated is None or rr_is_coherent(entry, stop, target, stated):
        return None
    implied = risk_reward(entry, stop, target)
    return {"stated_rr": stated, "implied_rr": implied if implied is not None else -1.0}


# ── DEF095: AMI renders the trade geometry — agents state levels, not ratios ──
#
# The Trader (EXECUTION) states entry/stop/target and used to narrate the derived
# figures — R:R, drawdown contribution — as free prose nothing verified. Over the
# only two live trades in the DEF095 window every two-input figure was wrong (SCHD
# narrated R:R 2.5:1 on a 0.2:1 setup, and the PM approved it), and the wrong number
# entered `Transcript so far:` as the premise the Risk debators and the PM then
# reasoned from. Per CR038 the control is STRUCTURAL, not a prompt instruction: after
# a level-proposing agent speaks, AMI recomputes every ratio from those same levels
# (trading_math) and rewrites the transcript so the figure downstream agents — and
# the user — read is AMI's computed one, never the narration. Flag-only: an
# incoherence is surfaced/corrected, never routed into `enforce_safety_floor`
# (DEF059 — the safety floor stays the sole vetoer; a flag must not change a verdict).

# One narrated price per label: "Entry: $32.75", "Stop: $29.60 (10% below entry)",
# "Target: $33.50 then $95+", "Size: 10% of portfolio". The label must be a whole
# word (so "entering"/"below entry)" don't false-match) and the price must follow
# within a short, digit-free gap so a distant number isn't captured.
#
# CR144 — WHAT STRUCTURED FIELD COULD THIS HAVE READ INSTEAD? For `size`, the
# answer was "one that already existed", and DEF235 is the bill for not asking.
#
# There used to be a fourth pattern here:
#
#     "size": r"\bsize\b[^\n$0-9]{0,15}\$?\s*(\d+(?:\.\d+)?)\s*%?"
#
# `\bsize\b` then any number within a 15-char digit-free gap. In *"a MEDIUM size
# entry at $188.62"* the very next words are the entry, so `size` and `entry`
# both returned 188.62; `drawdown_contribution` was handed a share price where a
# percentage belongs and AMI published 11.32 pt against a true 0.18 pt — 63×
# too large, under the words "These are the figures of record". A hand read of
# the epoch found 7 of 11 size matches wrong (stop distances, upside
# percentages, raw prices). It is gone: `size` is now passed in from
# `ctx.trader_size_pct`, which `_risk_tier_size_ceiling(mandate)` sets once per
# run from the mandate's own cap — the SAME number the safety floor clamps to
# and the Trader's prompt narrates, so shown == enforced == annotated.
#
# The three that remain are irreducibly prose: entry/stop/target are the agent's
# OWN proposal, and there is no structured field carrying what THIS turn claimed
# (`ctx.trader_*` holds the Trader's, not the speaker's). They keep the label
# anchor — a whole word, price within a short digit-free gap — and, unlike
# `size`, a mis-parse cannot silently rescale a figure by 63×: the triple has to
# form a valid long setup before anything is rendered at all.
#
# The deeper cause of DEF235, which removing one pattern does NOT fix: this
# family was written against `trader.md`'s ticket block, where each label sits
# alone on its own line inside a code fence and collision is impossible — but
# `_PROSE_FORMAT` then told the same agent "no headings, no tables, no code
# fences". **The parser depended on a format a later prompt layer forbade** (69%
# of Trader turns state levels inline in running prose). That conflict was
# DEF236's; it was resolved on 2026-08-11 in the parser's favour — the no-fence
# clause is no longer asserted at the Trader — so the block and this family
# agree again. Whether the block is the right contract at all is CR152 Tier A.4.

# DEF234 — the level, WITH its thousands separators. `(\d+(?:\.\d+)?)` stops at
# the comma, so *"break above $1,073.46"* parses as a level of **$1.00** and the
# check then announces the close is "107900.0% ABOVE $1.00". Found by sweeping
# the pattern over all 946 real PM verdict reasons on Alpha — the corpus check
# that should have preceded the original fix, not followed it.
#
# DEF242 — defined HERE, above `_LEVEL_PATTERNS`, because that family had the
# identical bug and did not get this group: *"Entry: $1,507.00"* parsed as an
# entry of **1.0**, which is not a silent miss but a fabricated level that flows
# into `_annotate_rr_against_levels` and prints under "These are the figures of
# record". One definition serves both families, so the next widening cannot
# reach one and miss the other — which is exactly how these two drifted apart.
_LEVEL_NUMBER = r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"

_LEVEL_PATTERNS: dict[str, re.Pattern[str]] = {
    "entry": re.compile(rf"\bentry\b[^\n$0-9]{{0,15}}\$?\s*{_LEVEL_NUMBER}", re.IGNORECASE),
    "stop": re.compile(
        rf"\bstop(?:[\s-]*loss)?\b[^\n$0-9]{{0,15}}\$?\s*{_LEVEL_NUMBER}", re.IGNORECASE
    ),
    "target": re.compile(rf"\btarget\b[^\n$0-9]{{0,15}}\$?\s*{_LEVEL_NUMBER}", re.IGNORECASE),
}

# The keyword-then-ratio span of a narrated R:R, split so the ratio can be
# rewritten to AMI's computed value while the keyword prefix is preserved:
# "R:R: 2.5:1" → "R:R: 0.2:1". Number-first phrasings ("2.5:1 R:R") aren't
# rewritten inline — the appended AMI note still carries the authoritative figure.
_RR_CLAIM_RE = re.compile(
    rf"({_PM_RR_KEYWORD}\s*[:=]?\s*(?:of|is|about|approx\.?|~|>|≈)?\s*)"
    r"(\d+(?:\.\d+)?\s*(?::\s*1|\s*to\s*1|x))",
    re.IGNORECASE,
)


def _match_level(text: str, kind: str) -> float | None:
    """First price stated for `kind` (entry/stop/target/size) in `text`, or None."""
    m = _LEVEL_PATTERNS[kind].search(text)
    if m is None:
        return None
    try:
        # DEF242 — the separators come back in the match now, and `float()` does
        # not take them. Stripping is what turns the widened group into a
        # correct VALUE rather than merely a longer match; asserting on the
        # match alone would have passed while `1,507.00` still read as 1.0.
        return float(m.group(1).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _annotate_rr_against_levels(
    text: str,
    entry: float | None,
    stop: float | None,
    target: float | None,
    size: float | None,
    *,
    levels_trusted: bool = True,
) -> tuple[str, dict[str, Any] | None]:
    """Rewrite any narrated R:R in `text` to the one `entry/stop/target` imply, and —
    on a genuine discrepancy or a ratio the levels imply but the agent omitted —
    append a loud AMI verification note carrying the computed R:R / asymmetry /
    drawdown contribution. Returns (annotated_text, signal); `signal` is a telemetry
    payload when the narration contradicted the levels (or none was rendered though
    the levels imply one), else None. Flag-only (DEF059).

    `levels_trusted=False` (DEF237) says the caller has already judged one of the
    levels a mis-parse. AMI then renders NO computed figure — that is the whole
    point of the gate — but the refusal still travels: a narrated ratio is struck
    as unverifiable exactly as it is for a setup that does not form. Silence
    would leave the agent's own claim standing unmarked, which is the CR040
    failure this check exists to avoid, one level up."""
    implied = None if not levels_trusted else risk_reward(entry, stop, target)
    stated = _extract_stated_rr(text)
    if implied is None:
        # The levels form no valid long setup, or one of them is not a level at
        # all — either way AMI can't render a ratio. If the agent narrated one
        # regardless, strike it loudly rather than let an unverifiable figure
        # enter the transcript unmarked.
        if stated is None:
            return text, None
        reason = (
            "the stated levels form no valid long setup"
            if levels_trusted
            else "AMI could not read a price level out of this proposal"
        )
        annotated = _RR_CLAIM_RE.sub(
            lambda m: f"{m.group(1)}[AMI: unverifiable — {reason}]",
            text,
        )
        return annotated, {"stated_rr": stated, "implied_rr": -1.0}

    rr_str = f"{implied:.1f}:1"
    annotated = _RR_CLAIM_RE.sub(lambda m: f"{m.group(1)}{rr_str}", text)
    if stated is not None and abs(implied - stated) <= 0.3:
        # Narration already agreed with the levels; the transcript now carries AMI's
        # figure inline. No correction note — don't add noise on a coherent trade.
        return annotated, None

    parts = [f"R:R {rr_str}"]
    asym = trade_asymmetry(entry, stop, target)
    if asym is not None:
        parts.append(f"{asym.upside_pct:.1f}% upside vs {asym.downside_pct:.1f}% downside")
    # DEF235: `size` is the mandate's own single-name cap, passed in from the run —
    # never read out of the prose. Say so in the annotation: entry/stop/target are
    # the agent's stated levels, the size is not, and a figure of record that hides
    # where its inputs came from is how 11.32 pt shipped for a true 0.18 pt.
    dd = drawdown_contribution(size, entry, stop) if size is not None else None
    if dd is not None:
        parts.append(
            f"drawdown contribution ≈ {dd.contribution_pts:.2f} pt "
            f"at the mandate's {size:.1f}% single-name cap"
        )
        # DEF240: the same figure, said in words, once it is large enough that the
        # percentage alone under-reads. The cap IS the size here (DEF235), so a
        # permissive mandate makes this fire on the annotation the user watches
        # stream — which is the point.
        if size > _LOUD_CONCENTRATION_PCT:
            parts.append(f"that cap is {size:.1f}% of the portfolio in one name")
    tail = (
        "the proposal stated no R:R, so AMI rendered it"
        if stated is None
        else "a narrated ratio that differed has been replaced with AMI's computed figure"
    )
    annotated += (
        f"\n\n[AMI verified the trade geometry from the stated levels "
        f"(entry ${entry:.2f} / stop ${stop:.2f} / target ${target:.2f}): "
        f"{'; '.join(parts)} — {tail}. These are the figures of record.]"
    )
    return annotated, {"stated_rr": stated, "implied_rr": implied}


# ── DEF231: a directional instruction the price has already invalidated ──────
#
# Twice in one afternoon on live Alpha the PM's `verdict.reason` — the string
# CR106 renders as the decision's justification — told the user to wait for a
# move the price had already made. SNDK: *"wait for the price to reclaim the
# 50-day range low of $998.19"* with the last close at $1212.21, 21% above it.
# GRAB: *"await a retest of the $3.18 support level"* while passing on a claimed
# breakdown below that same level. Both numbers were correct; the instruction
# composed from them was not followable.
#
# DEF228's general form — cross-check every agent's prose against its inputs —
# was rejected because it needs claims read out of free text, and a regex that
# silently passes reads as coverage (CLAUDE.md: prompt instructions are not
# controls). This is the narrow version that survives that objection: ONE
# agent, ONE field, and a comparison between two numbers rather than a claim
# extraction. The only thing parsed out of prose is the level the sentence
# itself names, in a `$`-anchored span immediately after a directional verb;
# the price it is compared against is the structured `last_close` the fact
# sheet already carries (DEF228), not another parse.
#
# Precision-biased, like CR106's stance parser: verbs whose required side is
# ambiguous are deliberately absent. "Retest" can be awaited from either side
# of a level and is NOT listed — GRAB's incoherence lived in the breakdown
# claim beside it, which is a prose claim and stays out of scope. A miss costs
# nothing; a false annotation on the Verdict Board would cost the surface its
# credibility.
#
# Flag-and-annotate, never veto (DEF059 — the safety floor is the sole vetoer).
#
# CR144 — WHAT STRUCTURED FIELD COULD THIS HAVE READ INSTEAD? Both of the two
# numbers this check compares: the price is `profile["last_close"]` and the
# level is one of `_structured_levels()`. Neither is parsed. What the prose
# pattern below supplies is the one thing no field can — **which level the
# sentence is making a claim about, and in which direction**. Grammar is not
# recoverable from a number.
#
# That division was learned the expensive way. The first build had no structured
# half at all and matched any `$` figure a directional verb governed; all four of
# its defects, including one that reached live Alpha, were figures that were not
# levels of the run (see the row). The pattern is deliberately kept no wider than
# the residual: an unrecognised word ends the match, and a figure that matches no
# level of the run is refused and logged.
_DIRECTIONAL_CLAIMS: tuple[tuple[str, str], ...] = (
    # (verb phrase, the side of the level the price must be on for the
    #  instruction to describe a move that is still ahead of it)
    (r"reclaim(?:s|ing|ed)?", "below"),
    (r"recover(?:s|ing|ed)?\s+(?:back\s+)?(?:to|above)", "below"),
    (r"(?:break|breaks|breaking|broke)\s+(?:out\s+)?(?:back\s+)?above", "below"),
    (r"(?:get|gets|getting|move|moves|moving|climb|climbs|climbing|back)\s+(?:back\s+)?above", "below"),
    (r"rise[sn]?\s+(?:back\s+)?(?:to|above)", "below"),
    (r"(?:break|breaks|breaking|broke)\s+(?:down\s+)?below", "above"),
    (r"(?:fall|falls|falling|fell|drop|drops|dropping|decline[sd]?|slip[sp]*(?:ed|ing)?)"
     r"\s+(?:back\s+)?(?:to|below)", "above"),
    (r"pull(?:s|ing)?\s*back\s+(?:to|toward|towards)", "above"),
    # ── added by the offline LLM sweep (AT:R66) ──────────────────────────────
    #
    # The bake-off recorded in this defect's audit lane disqualified the LLM at
    # RUNTIME — on constructed cases the regex scored 10/10 to its 8/10, failing
    # on exactly the two audit MAJORs, and on real verdicts it fired where the
    # regex was silent and mostly fabricated. What it did have was better
    # RECALL. So it was run offline over the 692 verdicts that carry a `$` and
    # from which this pattern extracted nothing, purely as a lead generator; the
    # 373 leads it claimed were clustered by shape and hand-read. Three families
    # survived that reading, and between them they are the largest single block
    # of real directional instructions the verb set was blind to.
    #
    # Everything else the LLM proposed was rejected on reading, and the rejects
    # are worth naming because they are what an unread lead list would have
    # encoded: stop placements ("a hard stop at $X", "the stop loss is widened
    # to $X"), entry statements ("entering at $X", "raise the entry trigger to
    # $X") and retests. None of those instructs the price to go anywhere.
    #
    # `breakout` as a NOUN — "wait for a confirmed breakout above $236.26" — is
    # the single most common miss (~70 of the leads). The existing rule above
    # matches "break out above" but a `\b` after `break` stops it one letter
    # short of the one-word form the PM actually writes.
    (r"breakout\s+(?:above|to)", "below"),
    # "a decisive close above $244.07", "we await a close above $19.62". Present
    # tense and gerund only: `closed above $X` is a claim about the past, and
    # comparing it to the LAST close would frame a historical statement as an
    # unmet condition. `close(?:s|ing)?` cannot match `closed` — the optional
    # group does not admit `d` — so the exclusion is structural, not a promise.
    (r"clos(?:e|es|ing)\s+above", "below"),
    (r"clos(?:e|es|ing)\s+below", "above"),
    # "until price clears the $23.67 breakout resistance". Third-person and
    # gerund only: bare "clear" is more often an adjective ("a clear $50
    # discount") and carries no direction.
    #
    # Round-6 audit MAJOR — and the SUBJECT is the fix, not the gap. Every other
    # verb here is unambiguously about price movement; `clear` is not. It is
    # ambiguous between "the price moves past a level" and "an entity EARNS a
    # figure", the second carries no direction at all, and the gap grammar
    # cannot tell them apart because both go straight from the verb to `$`:
    #
    #     "The company clears $52.30 million in annual free cash flow"
    #     "Net of fees the trader clears $52.30 on this position."
    #
    # Both fired. If that dollar figure lands within `_DIRECTION_TOLERANCE_PCT`
    # of any level the run holds, the Verdict Board renders a confident
    # directional note about a number that was never a price claim — the exact
    # failure this check exists to prevent, reached through the family added to
    # reduce misses. A suffix gate (`million|per share|in <noun>`) kills three
    # of the five and leaves "clears $52.30 on this position" standing, so it
    # is not the fix either.
    #
    # What separates the two senses is what is DOING the clearing, and the
    # corpus is unambiguous about it: of the 12 real matches in the 811-row
    # fixture, 11 read `price clears` / `price action clears` / `the stock
    # clears` / `a confirmed breakout clears` (the 12th is "RSI clearing 50",
    # no `$`). Every false positive has an AGENT subject — company, management,
    # fund manager, position, trader. So the verb takes a required price-sense
    # subject, and the vocabulary is exactly what the corpus attests: `prices`
    # and `shares` are NOT here, because widening a pattern past its evidence
    # is the P16 mistake this lane has now made twice.
    #
    # Measured: 365 → 364 extractions over all 811 rows. The single loss is
    # `"until price corrects toward the $50.00 support level or clears the
    # $57.67 breakout"` — a coordinated clause whose subject sits six words
    # back. Admitting a bare `or clears` to recover it would re-open the whole
    # agent-subject class ("the company earns X and clears $52.30 million"), so
    # it stays a miss. A miss costs nothing; a fabricated directional note on
    # the Verdict Board costs the surface its credibility.
    (r"(?:price(?:\s+action)?|stock|breakout)\s+clear(?:s|ing)", "below"),
)

# The verb, then the level it names: "reclaim the 50-day range low of $998.19".
#
# What may sit between the two is a WHITELIST, not a length cap — round-1 audit
# MAJOR. The cap was `[^\n$]{0,45}?`, which asks only that the `$` figure be
# NEAR the verb, never that it be the verb's own object. So ordinary PM prose
# where "reclaim" takes a non-price object and an unrelated price follows —
# *"the company must reclaim its margin story before we'd pay $52.30 for it"* —
# annotated a level the sentence made no directional claim about. Same shape
# broke `pull back toward caution … last quoted at $52.30`: anchoring the
# preposition to the verb does not make what follows the preposition the object.
#
# Every token between verb and level must now come from the small vocabulary a
# level reference is actually built from. An unrecognised noun ends the match,
# so an unknown phrase means no fire — the precision bias this check is built
# on, enforced by the grammar rather than by distance. The whitelist also makes
# the old "no second `$` in the gap" rule redundant: `$` is not in it.
# Round-2 audit MAJOR: the whitelist above was itself built out of level nouns
# PLUS the prepositions that relate two levels to each other, so a sentence
# naming TWO different levels — *"recover to the prior high, above the recent
# low of $52.30"* — walked the vocabulary end to end and attributed the second
# level's price to the first level's verb. Nothing required the captured figure
# to belong to the level the verb actually names.
#
# The split below is the grammar that distinguishes them. A preposition sitting
# ADJACENT to the verb is part of the verb phrase ("reclaim above $51.40" — the
# corpus contains this). The same word deeper in the gap OPENS A NEW
# prepositional phrase, and the level that follows belongs to that phrase, not
# to the verb. So a preposition is admitted once, in the verb's own slot, and
# never again.
_LEVEL_PREPOSITION = (
    r"(?:to|toward|towards|above|below|over|under|near|around|back|beneath|atop|at)"
)
# Note what is NOT in here, because it is load-bearing rather than an omission.
# `and`/`or` are absent, and a second preposition is refused by the split below.
# Those are the only two ways English builds a genuine second referent — "the
# range low AND the range high of $52.30", "the range low, ABOVE the range high
# of $52.30". A bare comma-chain of these nouns cannot: "reclaim the range low,
# the key level of $52.30" reads as apposition, where the trailing clauses
# re-describe the SAME thing the figure names, however redundantly. So the
# comma-apposition class is safe by construction and not by luck — worth knowing
# before adding a word here, since a conjunction would break the property.
# (Round-5 auditor, who spent four constructions establishing it.)
#
# `entry`/`stop`/`target` are here because `_structured_levels` made them
# candidate levels, and a vocabulary that admits `support` but not `entry` would
# let a PM's own words reach one and not the other. Adding them changes the
# extraction set over all 811 corpus rows by exactly ZERO — measured, not
# assumed — so this closes a gap without spending any of the precision the
# whitelist exists to buy.
_LEVEL_NOUN = (
    r"(?:the|a|an|its|their|this|that|prior|previous|former|recent|old|key|of|"
    r"level|levels|support|resistance|line|low|lows|high|highs|price|mark|"
    r"zone|area|floor|ceiling|band|base|range|session|close|day|week|month|"
    r"entry|entries|stop|stops|target|targets|"
    r"moving|average|sma|ema|\d+(?:-(?:day|week|month))?)"
)
_LEVEL_GAP = (
    rf"(?:\s+{_LEVEL_PREPOSITION}\b)?(?:[\s,–—-]+{_LEVEL_NOUN}\b)*[\s,]*[*_(]*"
)

# `_LEVEL_NUMBER` (DEF234, and DEF242's reuse of it) is defined once, above
# `_LEVEL_PATTERNS` — a second copy here is what let the two families drift.

# Round-7 audit MAJOR — and it is the SUBJECT gate that failed, not just one
# word in it. Round 6 fixed `clear` firing on the earnings sense by requiring a
# price-sense subject. The auditor broke that with `"The stock clears $52.30
# billion in market capitalization"` — `stock` is as good a metonym for the
# company as `management` is. Probing my own remaining three before submitting,
# ALL of them break the same way:
#
#     "The offering price clears $52.30 million in gross proceeds."
#     "The strike price clears $52.30 per share in option premium."
#     "The breakout clears $52.30 billion in market value added."
#     "Price action clears $52.30 million in cumulative volume."
#
# So the subject is not the discriminator. It never was — it correlated with
# one in the corpus and nowhere else. **What actually separates a price level
# from a quantity of money is the OBJECT: a level is bare, a quantity carries a
# scale or a measure.** No price is ever "$52.30 billion" or "$52.30 in short
# interest". (This sentence originally also claimed "$52.30 per share". Round 8
# corrected that — a share price IS a per-share figure; see `_NOT_A_PRICE_AFTER`.)
#
# This gate therefore applies to the WHOLE family, not to `clear` alone — which
# also closes the round-6 residual I left open and the auditor declined to gate
# on: `"posted a breakout to $52.30 in quarterly revenue"`.
#
# Measured: excludes **0 of the 364** real extractions across all 811 corpus
# rows. The corpus does carry 243 scale-suffixed figures (`$7.59B`, `$6,912M`)
# — they are the fundamentals numbers in the PM's prose, and not one of them is
# a level any directional verb names. A free gate, and it is a proper subset
# rule: it can only ever remove a match, never create one.
#
# The subject gate STAYS. Neither alone is sufficient — this one does not stop
# *"Net of fees the trader clears $52.30 on this position"* (no scale, no
# measure), and the subject gate does not stop the four constructions above.
# Round-8 audit MAJOR — the first draft asserted *"no price is ever `$52.30 per
# share`"*, and that is simply false. A share price IS a per-share dollar
# figure, and PM prose says so out loud exactly when a level needs
# disambiguating from an aggregate in the same paragraph:
#
#     "Price breaks above $52.30 per share resistance."          was MISSED
#     "Shares reclaim $52.30 per share support in the final hour." was MISSED
#     "The stock clears $52.30 per share, confirming the breakout." was MISSED
#
# The auditor also checked the obvious repair before filing, and it is wrong
# too: deleting the clause outright lets *"$52.30 per share in cumulative
# dividends"* and *"$52.30 per share in option premium"* back in. The clause was
# necessary AND insufficient — because **the gate was reading the wrong word.**
# What makes those two non-prices is "cumulative dividends" and "option
# premium"; "per share" carries no information about which sense is meant, and
# on its own it is as compatible with a level as with a payout.
#
# So a share-denomination phrase no longer excludes anything by itself — it may
# only sit BETWEEN the figure and a quantity noun. A scale word still excludes
# on its own, because "$52.30 billion" has no price reading at all.
#
# Measured: 364 extractions, unchanged, and the corpus contains zero `$X per
# share` / `$X a share` of either sense — so this is derived from the language,
# not from the fixture, and the fixture is only evidence that it costs nothing.
_NOT_A_PRICE_AFTER = (
    r"(?!"
    r"\s*(?:million|billion|trillion|[mb]n\b|[MBK]\b)"
    r"|(?:\s+(?:per|a)\s+share)?\s+(?:in|of)\s+\w+"
    r")"
)

# Round-4 audit MINOR: most verb phrases END in their own preposition
# ("break above", "pull back to"). Handing those a second, independent
# preposition slot lets two compose — `break above near the recent low of $X`
# — which is not grammatical English but did fire. The two never legitimately
# compose, so a verb that already carries its preposition does not get the slot.
_VERB_ENDS_IN_PREPOSITION = re.compile(
    r"(?:to|toward|towards|above|below|over|under|near|around|at)\)?$"
)
_LEVEL_GAP_NO_PREP = rf"(?:[\s,–—-]+{_LEVEL_NOUN}\b)*[\s,]*[*_(]*"

_DIRECTIONAL_CLAIM_RES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (
        re.compile(
            rf"\b(?:{verb})\b"
            rf"{_LEVEL_GAP_NO_PREP if _VERB_ENDS_IN_PREPOSITION.search(verb) else _LEVEL_GAP}"
            # The number is ATOMIC. Without `(?>…)` the gate below is worthless:
            # on "$52.30 billion" the engine simply backtracks the number to
            # "52.3", sees "0 billion" — not a scale word — and the negative
            # lookahead passes, capturing a shortened figure. Worse at "52",
            # which reads ".30 billion" and also passes. Atomic grouping locks
            # the longest number in so the gate decides the whole match rather
            # than being negotiated around. (Verified: the naive form fired on
            # all 9 constructions it was written to stop.)
            rf"\$\s*(?>{_LEVEL_NUMBER}){_NOT_A_PRICE_AFTER}",
            re.IGNORECASE,
        ),
        side,
    )
    for verb, side in _DIRECTIONAL_CLAIMS
)

# Below this the price is effectively AT the level, and "reclaim $X" from
# 0.4% under it is a fair description of the next move, not a contradiction.
_DIRECTION_TOLERANCE_PCT = 1.0

# DEF234 — and above this, the two numbers are not a price and a level it is
# waiting for; something was mis-parsed. A PM does not tell a user to wait for
# a level five times away from the price, so a gap that large is evidence the
# extraction failed, not evidence of an incoherent instruction. Refusing to
# annotate is a miss, which is this check's designed failure mode; rendering
# "107900.0% ABOVE" confidently is the failure mode it must never have. The
# comma bug above is fixed at source — this is the backstop for the NEXT parse
# defect in the same class, and it is loud rather than silent.
#
# Superseded by `_MAX_PLAUSIBLE_LEVEL_RATIO` below (DEF237) and kept only as the
# derivation of it — 400% gap IS 5× ratio. Nothing reads this constant.
_DIRECTION_MAX_PLAUSIBLE_GAP_PCT = 400.0

# DEF237 — the SAME threshold, said symmetrically, because said as a signed
# percentage gap it only ever guarded one direction.
#
#     gap_pct = 100 × (close − level) / level  =  100 × (close/level − 1)
#
# so |gap| > 400 resolves to `close > 5 × level` and to nothing else: the other
# branch needs close/level < −3, which no pair of positive prices reaches. A
# level far BELOW the close (DEF234's comma bug: $1,073.46 → 1.0) trips it at
# 107900%; a level far ABOVE the close never trips it at all. A level 13.8× the
# close evaluates to −92.8% and sails through a 400% bound.
#
# That asymmetry is the whole of DEF237's exposure on this check, and DEF242
# widens the number group, which makes more prose numerals candidate levels.
# 5.0 is therefore DERIVED, not chosen — it is 400% restated so that the caught
# side keeps exactly its current behaviour and only the uncaught side gains it.
# It is deliberately not tuned against the corpus: 216 turns hold 5 full level
# triples, which cannot validate a threshold (P16), and a number fitted to five
# examples would read as evidence-backed while being nothing of the sort.
_MAX_PLAUSIBLE_LEVEL_RATIO = 5.0


def _level_is_implausible(level: float | None, close: float | None) -> bool:
    """True when `level` and `close` are too far apart to be a price and a level
    of the same instrument — i.e. when the likeliest explanation is a mis-parse.

    Symmetric by construction: the ratio is taken the larger way round, so a
    level 5× the close and a close 5× the level are judged identically. Returns
    False when either number is missing or non-positive, because the caller then
    has nothing to compare and silence is the designed miss (DEF234)."""
    if not level or not close or level <= 0 or close <= 0:
        return False
    return max(level / close, close / level) > _MAX_PLAUSIBLE_LEVEL_RATIO


def _reference_close(profile: dict[str, Any]) -> float | None:
    """The price a directional instruction is measured against: the last close
    of the same series the 50-day range was computed over (DEF228), which is
    what the PM was actually shown. Gated on its own `field_state` entry — a
    profile with no recorded technicals provenance yields no reference price
    and no check, rather than a comparison against a number of unknown origin
    (CR104)."""
    if (profile.get("field_state") or {}).get("technicals") != LiveDataState.LIVE.value:
        return None
    try:
        return float(profile["last_close"])
    except (KeyError, TypeError, ValueError):
        return None


# How a matched level is named back to the user. Being able to say WHICH level
# the instruction referred to is the point of matching against the run's own
# numbers rather than against any figure in the sentence — the annotation stops
# being "some price you wrote" and becomes "the 50-day range low we handed you".
_STRUCTURED_LEVEL_LABELS: dict[str, str] = {
    "support": "the 50-day range low",
    "breakout": "the 50-day range high",
    "low": "the 52-week low",
    "high": "the 52-week high",
    "entry": "this verdict's entry",
    "stop": "this verdict's stop",
    "target": "this verdict's target",
}

# A quoted level is the same level when it agrees to within this much. The PM
# quotes off the fact sheet, so most matches are exact; the band exists for the
# rounding it does when it writes `$998.2` or `$1,212` for `$1212.21`. It is
# deliberately far too tight to let a different level of the same run stand in,
# and far too tight for a round number the PM invented ($100 against a support
# of $104) to pass as a quote of one.
#
# Being HALF `_DIRECTION_TOLERANCE_PCT` is what makes naming the matched level
# safe. It is not what makes the DIRECTION safe — the direction is computed from
# `close` and the matched run's own `level`, and never reads the quoted figure at
# all, so the PM's rounding cannot reach the verdict either way. What the
# ordering buys is that the level AMI names is on the same side of the close as
# the number the PM wrote, so the note can substitute one for the other without
# describing a different situation: |level−close| ≥ 0.01·level and
# |quoted−level| ≤ 0.005·level give |quoted−close| ≥ 0.005·level > 0, with the
# sign of (level−close). Holds with equality at both bounds simultaneously.
_STRUCTURED_LEVEL_MATCH_PCT = 0.5


def _structured_levels(
    profile: dict[str, Any], verdict: Verdict
) -> list[tuple[str, float]]:
    """Every price level THIS run actually holds, as a (name, value) list.

    DEF231's own row specified the fix this way and it was not built that way:
    *"the referenced level is already a structured number the verdict carries…
    so a comparison is available without parsing free text"*. What shipped
    instead compared the close against ANY `$` figure a directional verb
    governed, and that extra generality turned out to be the entire defect
    surface — all three audit MAJORs and DEF234 are cases where the captured
    number was not a level of this run at all (`we'd pay $52.30`, a second
    sentence's level, `$1.00` truncated out of `$1,073.46`). A figure that has
    to match one of these cannot be any of them.

    Each source is gated on the provenance that was recorded when it was
    fetched (CR104), so a level AMI never actually held is never a candidate:

      * `support`/`breakout` need `field_state["technicals"] == live` — the
        same gate `_reference_close` uses, since they come from one OHLCV pull.
      * `low`/`high` need `field_state["week52"] == live`. That key is
        deliberately separate: `fetch_live_fundamentals` substitutes a ±5%
        placeholder off price when the real `fiftyTwoWeek*` fields are absent,
        and a placeholder is a derived guess, not a level anyone was shown.
      * `entry`/`stop`/`target` exist only on an APPROVE, and one whose
        `level_provenance` says `ami_default` is dropped: AMI minted that
        number after the PM had finished writing, so the PM cannot have been
        quoting it, and leaving it in would let a coincidence read as a quote.

    `last_close` is not a candidate. It is the reference the comparison is
    made against; a level equal to it is 0% away and the tolerance below
    discards it anyway.
    """
    state = profile.get("field_state") or {}
    out: list[tuple[str, float]] = []

    def _add(name: str, raw: Any) -> None:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return
        if value > 0:
            out.append((name, value))

    if state.get("technicals") == LiveDataState.LIVE.value:
        _add("support", profile.get("support"))
        _add("breakout", profile.get("breakout"))
    if state.get("week52") == LiveDataState.LIVE.value:
        _add("low", profile.get("low"))
        _add("high", profile.get("high"))
    if verdict.action == VerdictAction.APPROVE:
        provenance = verdict.level_provenance or {}
        for name in ("entry", "stop", "target"):
            if provenance.get(name) == "ami_default":
                continue
            _add(name, getattr(verdict, name, None))
    return out


def _match_structured_level(
    quoted: float, levels: Sequence[tuple[str, float]]
) -> tuple[str, float] | None:
    """The run's own level the sentence quoted, or None if it quoted no level
    of this run. On several near matches the closest wins — they are within
    half a percent of each other by construction, so they are on the same side
    of the close and the choice only affects which name is printed."""
    best: tuple[str, float] | None = None
    best_rel = _STRUCTURED_LEVEL_MATCH_PCT
    for name, value in levels:
        rel = 100.0 * abs(quoted - value) / value
        if rel <= best_rel:
            best, best_rel = (name, value), rel
    return best


def _direction_contradictions(
    text: str, close: float | None, levels: Sequence[tuple[str, float]]
) -> list[dict[str, Any]]:
    """Every directional instruction in `text` that names one of this run's own
    levels and puts it on the side of `close` that makes the move already-made.
    Empty when the text states none, when no reference close is available, when
    the run holds no structured level to check against, or when every named
    level is on the coherent side.

    Two independent gates have to agree before anything is said, and they fail
    in opposite directions, which is why both are kept (P16). The grammar
    decides whether the figure is the verb's own object — it is what stops
    *"recover to the prior high, above the recent low of $52.30"* attributing
    the second level's price to the first level's verb, and no amount of
    matching would catch that, because $52.30 there IS a real level. The
    structured-level match decides whether the figure is a level of this run at
    all — it is what stops *"we'd pay $52.30"* and DEF234's truncated `$1.00`,
    and no amount of grammar would catch those, because both are grammatical.
    """
    if not text or close is None or close <= 0 or not levels:
        return []
    out: list[dict[str, Any]] = []
    for pattern, required_side in _DIRECTIONAL_CLAIM_RES:
        for m in pattern.finditer(text):
            try:
                quoted = float(m.group(1).replace(",", ""))
            except (TypeError, ValueError):
                continue
            if quoted <= 0:
                continue
            matched = _match_structured_level(quoted, levels)
            if matched is None:
                # The designed miss. The sentence gave an instruction about a
                # number this run does not hold, so AMI has nothing to compare
                # it against and says nothing — silence, not a guess.
                logger.info(
                    "room_pm_direction_unmatched_level",
                    claim=m.group(0).strip()[:120], quoted=quoted,
                    levels={k: v for k, v in levels},
                )
                continue
            name, level = matched
            # The RUN's number, not the sentence's, from here on: the PM may
            # have rounded when it quoted, and the arithmetic the user reads
            # should be AMI's own figure to the cent.
            gap_pct = 100.0 * (close - level) / level
            if abs(gap_pct) < _DIRECTION_TOLERANCE_PCT:
                continue
            if _level_is_implausible(level, close):
                # DEF234: not an incoherent instruction — a mis-parse. Loud, so
                # the next one is found by reading logs rather than by a user
                # reading nonsense on the Verdict Board. Reaching this now means
                # a level of the run is itself absurd against its own close,
                # which is a different bug again; still refuse, still loudly.
                #
                # DEF237 made the comparison symmetric. It read `abs(gap_pct) >
                # 400`, which caught a level far below the close and nothing far
                # above it — see `_MAX_PLAUSIBLE_LEVEL_RATIO`. Same threshold,
                # both directions.
                logger.warning(
                    "room_pm_direction_implausible_gap",
                    claim=m.group(0).strip()[:120],
                    level=level, level_name=name, close=close,
                    gap_pct=round(gap_pct, 1),
                )
                continue
            actual_side = "above" if gap_pct > 0 else "below"
            if actual_side == required_side:
                continue
            out.append({
                "claim": m.group(0).strip(),
                "level": level,
                "level_name": name,
                "quoted": quoted,
                "close": close,
                "gap_pct": round(gap_pct, 1),
                "price_is": actual_side,
            })
    return out


def _annotate_direction_against_price(
    text: str, close: float | None, levels: Sequence[tuple[str, float]]
) -> tuple[str, list[dict[str, Any]]]:
    """Append AMI's reading of the price against any level the text tells the
    user to wait for from the wrong side. Returns (annotated_text, signals);
    `signals` is empty when the text is coherent, and the text is then returned
    untouched — no note on a clean verdict (same rule as
    `_annotate_rr_against_levels`).

    The instruction is NOT rewritten. AMI does not know what the PM meant to
    say, only that the two numbers in front of it do not support what it said,
    so the correction states the numbers and leaves the sentence standing —
    the user can see both and judge.
    """
    signals = _direction_contradictions(text, close, levels)
    if not signals:
        return text, []
    first = signals[0]
    named = _STRUCTURED_LEVEL_LABELS.get(first["level_name"], "that level")
    where = f"{named} (${first['level']:.2f})"
    if first["price_is"] == "above":
        detail = (
            f"the last close ${first['close']:.2f} is already "
            f"{abs(first['gap_pct']):.1f}% ABOVE {where}, so that "
            f"level is not something the price has yet to win back"
        )
    else:
        detail = (
            f"the last close ${first['close']:.2f} is already "
            f"{abs(first['gap_pct']):.1f}% BELOW {where}, so that "
            f"level is not something the price has yet to give up"
        )
    return (
        text
        + f"\n\n[AMI checked this instruction against the price: {detail}. "
          f"The close and the level are the figures of record — read them, not "
          f"the direction the sentence implies.]",
        signals,
    )


# CR106 B2 / DEF147 — the stance envelope, and its extraction.
#
# DEF147: one regex used to do BOTH jobs — locate-and-strip, and parse — and it
# demanded both brackets and all three fields intact at the very end of the
# turn. So an envelope the model got slightly wrong was neither read (→ a null
# stance → the comb reports "did not state a view", a lie: the agent stated one)
# nor removed (→ the user reads raw machine syntax inside what CR106 calls a
# quotation). Measured 3 of 11 agents on live Alpha the day it shipped, 27% —
# worse than the ~22% JSON-parse rate (DEF058) this shape was chosen to beat.
# One mechanism silently doing two jobs, so neither could fail alone. Split:
#
#   * FIND + STRIP is deliberately loose. A line that merely BEGINS with
#     `STANCE:` (opening bracket optional, terminator optional) IS the machine
#     channel and comes off, whether or not a single field parses. A tail the
#     user can read is a defect regardless of what the parser made of it.
#   * PARSE is per-field and independently nullable, so a truncation that ate
#     the headline still yields the stance.
#
# Position: the envelope now LEADS the turn (Saiful's ruling, DEF147). Appended
# after prose in a length-capped generation it was the first thing truncation
# ate — sacrificed precisely on the longest, most substantive turns, which
# DEF125's bigger budgets move but cannot fix. The trailing position is still
# accepted on read, because the model drifts and a tail we refuse to recognise
# is a leak by construction; it is simply no longer what the prompt asks for.
# When both positions carry one, the front wins — that is the instructed slot.
# DEF247: and the strip is not positional at all. Position was the last thing
# still coupling STRIP to PARSE, and a single opener line ahead of the envelope
# was enough to defeat both at once. Where it sits is now only a log line.
#
# Precision-biased throughout, unchanged: every unrecognised token yields
# `None`, and `None` reaches the pixel as "did not state a view". Nothing here
# guesses — a stance inferred from prose would be exactly the client-side
# keyword heuristic CR106 §2.2 rejected, moved one layer down.

# The locator. Bracket optional, terminator absent by design: this must match
# every tail the model has actually produced, not the one the prompt asked for.
# DEF257: markdown emphasis is part of the shape now. The model started writing
# `**STANCE: for | CONVICTION: medium | HEADLINE: $1231.94 entry**` — bold, and
# often instead of the brackets — which this locator did not accept, so the line
# was neither stripped nor read and went to the user as raw syntax. Zero such
# turns in the first 2,974 stored; 5 since 2026-08-10. The prompt has always
# shown the envelope in a bare code-ish form and says nothing about emphasis, so
# nothing changed to invite it: the model's formatting habits simply drift, which
# is the whole reason FIND is deliberately loose and PARSE is strict.
#
# Bounded to what has actually been observed plus its trivial neighbours: one or
# two `*`/`_`, either side of the optional bracket — so the effective cap on a
# consecutive run is FOUR, not two, because `_EMPHASIS` appears twice below.
# `***STANCE: …***` (bold+italic, and the more plausible next drift than plain
# bold was) therefore already works; 5+ leaks. That held by accident of the
# pattern appearing twice until the DEF257 round-1 auditor built the mutation
# this file's own table DESCRIBED rather than the one that was run — it survived,
# and `test_the_repetition_bound_is_a_decision_too` now pins it. The bound is conservatism,
# not protection — a mutation widening it to `-`, `>` and `#` breaks no test and
# no realistic input, because everything it newly matches (`- STANCE: …`,
# `> STANCE: …`) would arguably be the machine channel too. It stays narrow
# because inventing shapes nobody has emitted is the P16 mistake, and the cost of
# being wrong here is one round of measurement, not a defect. If a list-marker or
# blockquote envelope shows up in the corpus, widen it THEN — and
# `test_the_decoration_boundary_is_a_decision` pins where the line currently sits
# so that widening is deliberate rather than incidental.
_EMPHASIS = r"[*_]{0,2}\s*"
_STANCE_LINE_RE = re.compile(
    rf"^\s*{_EMPHASIS}\[?\s*{_EMPHASIS}STANCE\s*:", re.IGNORECASE
)

# Emphasis also has to come off before the FIELDS are read, or the headline keeps
# its trailing `**` and the comb renders "$1231.94 entry**". Leading/trailing
# runs only — an inner `_` belongs to whatever the agent was naming.
_ENVELOPE_TRIM_RE = re.compile(r"^[\s*_]+|[\s*_]+$")

# The legacy inline form — an envelope sharing its line with the prose that
# precedes it, at the very end of the turn. Kept strict and end-anchored so a
# bracketed aside mid-paragraph is read as the prose it is.
_STANCE_TAIL_RE = re.compile(
    r"\[\s*STANCE\s*:\s*[A-Za-z]*\s*\|"
    r"\s*CONVICTION\s*:\s*[A-Za-z]*\s*\|"
    r"\s*HEADLINE\s*:\s*[^\]]*\]\s*\Z",
    re.IGNORECASE,
)

# Read one field at a time. Each stops at the next `|`, the terminator, or the
# end of the line — so a missing `]` costs nothing, and one mangled field costs
# one field rather than all three.
_STANCE_FIELD_RE = re.compile(r"STANCE\s*:\s*([^|\]\n]*)", re.IGNORECASE)
_CONVICTION_FIELD_RE = re.compile(r"CONVICTION\s*:\s*([^|\]\n]*)", re.IGNORECASE)
_HEADLINE_FIELD_RE = re.compile(r"HEADLINE\s*:\s*([^\]\n]*)", re.IGNORECASE)

_STANCE_VALUES = {"for", "against", "neutral"}
_CONVICTION_VALUES = {"low", "medium", "high"}


@dataclass(frozen=True)
class _StanceEnvelope:
    stance: str | None = None
    conviction: str | None = None
    headline: str | None = None


def _stance_field(pattern: re.Pattern[str], envelope: str) -> str | None:
    match = pattern.search(envelope)
    return match.group(1).strip() if match else None


def parse_stance_envelope(text: str) -> tuple[str, _StanceEnvelope]:
    """Split a Room agent's turn into (prose, stance envelope).

    Two independent jobs, deliberately decoupled (DEF147). Anything shaped like
    the machine channel is REMOVED whether or not it parses; whatever parses is
    read field by field. An absent envelope returns the text unchanged and an
    all-`None` envelope — not an error and not logged as one, because a null
    stance is a supported, rendered outcome (the comb's §3.4 gutter).
    """
    lines = text.split("\n")
    filled = [i for i, line in enumerate(lines) if line.strip()]
    if not filled:
        return text, _StanceEnvelope()

    # DEF247: every line the locator matches is a candidate, wherever it sits.
    # This bound used to be the first and last non-blank lines, on the premise
    # that the envelope is never mid-turn. It is: the model writes a one-line
    # conversational opener ahead of it — "I'd argue for smaller sizing" — which
    # displaces the envelope off the front while real prose runs past it off the
    # back, so neither end matched, `_STANCE_TAIL_RE` is `\Z`-anchored and did
    # not either, and the turn came back untouched. 3 of 9 debator turns on the
    # 2026-08-09 post-promotion batch: raw machine syntax on the user's screen
    # AND a null stance — the exact pair DEF147 split these two jobs to prevent,
    # re-coupled through position rather than through a shared regex.
    #
    # Nothing is lost by widening it. The bracketed aside the old bound was
    # protecting is protected by `_STANCE_LINE_RE` itself, which is anchored at
    # the start of a line: an aside inside a sentence is not a line that opens
    # with `STANCE:`, so it was never a candidate at any position.
    found = [i for i in filled if _STANCE_LINE_RE.match(lines[i])]

    if found:
        # Front wins, unchanged — that is the slot the prompt names (DEF147).
        envelope = lines[found[0]]
        body = "\n".join(line for i, line in enumerate(lines) if i not in found)
        # Removing an interior line leaves the blank lines that flanked it back
        # to back; the user reads that as a hole in the argument.
        body = re.sub(r"\n{3,}", "\n\n", body)
        if len({lines[i].strip() for i in found}) > 1:
            # More than one, and they disagree. All are stripped either way;
            # this says which the user is being shown, and is the signal that
            # the prompt's position instruction is not landing.
            logger.warning(
                "room_stance_envelope_conflict",
                front=lines[found[0]].strip()[:120],
                tail=lines[found[-1]].strip()[:120],
            )
        if found[0] != filled[0]:
            # Its own key, deliberately. The fix above makes this shape harmless
            # to the user, and a harmless failure that stops being counted is how
            # a 30% instruction-following rate becomes invisible — the reason
            # DEF147 decoupled these jobs rather than papering over one with the
            # other. This is the emission rate, still measurable after the leak
            # is closed, and it is evidence for CR143's model arm.
            logger.warning(
                "room_stance_envelope_displaced",
                opener=lines[filled[0]].strip()[:120],
                envelope=lines[found[0]].strip()[:120],
            )
    else:
        match = _STANCE_TAIL_RE.search(text)
        if match is None:
            return text, _StanceEnvelope()
        envelope = match.group(0)
        body = text[: match.start()]

    # DEF257: strip the emphasis the locator now tolerates, so the last field
    # does not carry a trailing `**` onto the pixel.
    envelope = _ENVELOPE_TRIM_RE.sub("", envelope)
    stance = (_stance_field(_STANCE_FIELD_RE, envelope) or "").lower()
    conviction = (_stance_field(_CONVICTION_FIELD_RE, envelope) or "").lower()
    headline = _stance_field(_HEADLINE_FIELD_RE, envelope)

    # "none" is the prompt's own opt-out and lands here as an unrecognised
    # value — same destination, no special case needed.
    if stance not in _STANCE_VALUES:
        stance = None  # type: ignore[assignment]
    if conviction not in _CONVICTION_VALUES:
        conviction = None  # type: ignore[assignment]
    if not headline or len(headline) > STANCE_HEADLINE_MAX_CHARS:
        # Nulled, never cut. A truncated headline is an assertion with its
        # qualifier removed, which is how a summary inverts its own meaning.
        headline = None  # type: ignore[assignment]

    # A conviction without a stance is meaningless — "strongly, about nothing"
    # — and would draw a conviction bar under a hex sitting in the gutter.
    if stance is None:
        conviction = None  # type: ignore[assignment]

    return body.strip(), _StanceEnvelope(
        stance=stance, conviction=conviction, headline=headline
    )


# DEF125 — the transcript mark for a turn the model was cut off mid-writing.
#
# Written in the established `[AMI …]` annotation voice (see
# `_annotate_rr_against_levels`) for three reasons, all load-bearing:
#   1. It travels INTO the transcript, so the Trader, the three Risk debators
#      and the PM read "this synthesis is incomplete" rather than inheriting a
#      fragment as a finished conclusion — DEF095's contagion vector, closed.
#   2. The user sees it. CR040: a failure this total must not be silent, and
#      the alternative — a sentence that simply stops — reads as the agent
#      having nothing more to say.
#   3. `content.contains('[AMI')` is already the client's amber-mark test
#      (CR106 §3.3), so a truncated row is flagged in the collapsed transcript
#      with no client change at all.
_TRUNCATION_MARK = (
    "\n\n[AMI: this contribution hit its length limit and stops mid-thought — "
    "it is incomplete. Treat the final sentence as unfinished, not as a "
    "conclusion.]"
)


def _mark_if_truncated(
    text: str,
    *,
    agent_id: AgentId,
    meta: dict[str, Any],
) -> str:
    """Append the DEF125 incompleteness mark when the provider reports a length
    stop. A no-op for every other stop reason, and for a provider that reports
    none — the mark asserts a fact, so it is never inferred from text shape."""
    if meta.get("finish_reason") != "length":
        return text
    logger.warning(
        "room_agent_truncated",
        agent_id=agent_id.value,
        max_tokens=max_tokens_for(agent_id),
        chars=len(text),
    )
    if _TRUNCATION_MARK.strip() in text:
        return text
    return text + _TRUNCATION_MARK


def _verify_and_annotate_geometry(
    text: str,
    *,
    size_pct: float | None = None,
    reference_close: float | None = None,
) -> tuple[str, dict[str, Any] | None]:
    """Verify a level-proposing agent's OWN narrated derived figures against AMI's
    trading_math (DEF095). An agent has "proposed levels" only when it states a full
    long-setup triple (entry + stop + target); anything less isn't a level claim and
    passes through untouched. Generalises the PM-only coherence check to any agent —
    principally the Trader, whose narrated ratio drives the whole downstream debate.

    `size_pct` is the run's mandate cap (`ctx.trader_size_pct`), NOT parsed from the
    text — DEF235. Callers that omit it get the R:R and asymmetry but no drawdown
    contribution, which is the honest degradation: without a size there is no such
    figure, and inventing one out of the prose is the defect.

    `reference_close` is the run's own last close (`_reference_close(ctx.profile)`,
    which yields None unless the technicals are LIVE). DEF237: without it this
    function had no plausibility gate of any kind, so a single mis-parsed level
    produced a fabricated downside and printed it under *"These are the figures of
    record"* — the one phrase in the transcript that tells the user a number was
    checked. Three levels all pass through `_match_level`, and DEF242 has just
    widened its number group, which makes more prose numerals candidates.

    A triple containing an implausible level is refused ENTIRELY rather than
    partially annotated: the levels are only meaningful together (`risk_reward`
    needs all three), so salvaging two of them would compute a ratio from a set
    AMI has already decided it does not believe.
    """
    if not text:
        return text, None
    entry = _match_level(text, "entry")
    stop = _match_level(text, "stop")
    target = _match_level(text, "target")
    if entry is None or stop is None or target is None:
        return text, None
    implausible = {
        name: value
        for name, value in (("entry", entry), ("stop", stop), ("target", target))
        if _level_is_implausible(value, reference_close)
    }
    if implausible:
        # Loud, and a REFUSAL rather than a guess — the same shape as the DEF231
        # direction check. Computing a figure from a mis-parse puts an invented
        # number in front of the user with AMI's name on it, and every
        # downstream agent then reasons from it. But the refusal is not silence:
        # a ratio the agent narrated is still struck, or the gate would trade a
        # fabricated AMI figure for an unmarked agent one.
        logger.warning(
            "room_geometry_implausible_level",
            levels=implausible,
            reference_close=reference_close,
            max_ratio=_MAX_PLAUSIBLE_LEVEL_RATIO,
        )
        return _annotate_rr_against_levels(
            text, entry, stop, target, size_pct, levels_trusted=False
        )
    return _annotate_rr_against_levels(text, entry, stop, target, size_pct)


# CR098 Amendment 2 — fixed, ticker-slot-only PM copy for a Market-withheld
# run. Verbatim from the CR doc: credits the fundamentals work done, names the
# missing input factually, frames the refusal as professional discipline, and
# contains no plan name / "upgrade" / pricing (acceptance #13 — the CTA is app
# chrome, never the PM's voice).
_NO_VERDICT_REASON = (
    "No verdict — and that is deliberate.\n"
    "The fundamentals case for {ticker} was argued in full, and it stands on its own.\n"
    "But entry, stop and target are price decisions, and this session ran without a "
    "market read. Issuing a position on that basis would be a guess presented as a "
    "call, and I won't put that on your book.\n"
    "The analysis holds. The trade doesn't — not until someone reads the tape."
)


def _assemble_no_verdict(ctx: _RoomContext) -> Verdict:
    """CR098 Amendment 2 — built in code, bypassing `_parse_pm_verdict` entirely,
    so no LLM output (however well-formed) can ever produce a tradeable verdict
    when Market is withheld (acceptance #10). `opinions_not_included` is filled
    here too — this function never routes through the shared post-loop
    `model_copy` accident of omission, it's just consistent with it."""
    return Verdict(
        action=VerdictAction.NO_VERDICT,
        size_pct=None, entry=None, target=None, stop=None, time_horizon_days=None,
        reason=_NO_VERDICT_REASON.format(ticker=ctx.ticker),
        opinions_not_included=[a.value for a in ctx.withheld],
    )


def _assemble_verdict(ctx: _RoomContext, profile: dict[str, Any]) -> Verdict:
    """Deterministic scripted verdict — NOT the live path's decision-maker.

    Used only by the non-live/scripted demo path. In the live path the PM's
    own parsed decision is the verdict (see `_parse_pm_verdict`, DEF056);
    a failed/timed-out live PM call fails safe to PASS instead of coming
    here (DEF059 — an outage must never produce this function's APPROVE).
    """
    proposed = ProposedTrade(
        ticker=ctx.ticker,
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        quantity=shares_for_size(ctx.portfolio_value, ctx.trader_size_pct, ctx.trader_entry),
        limit_price=ctx.trader_entry,
    )
    result = check_mandate_compliance(
        proposed,
        portfolio_value=ctx.portfolio_value,
        current_drawdown_pct=ctx.current_drawdown_pct,
        mandate=ctx.mandate,
        halal_universe=ctx.halal_universe,
        classification_universe=ctx.classification_universe,
        locale_allowed_universe=ctx.locale_allowed_universe,
        # CR026: the scripted-path check bites the sector cap too.
        holdings=ctx.sector_holdings,
        quotes=ctx.sector_marks,
        sector_map=ctx.sector_map,
        # CR101-BE2 round 2: same trade-history context sim_engine.py supplies at
        # submit()/preview() — previously omitted here, so a set post-loss cooldown
        # / over-trading brake / open-risk cap was silently unenforced.
        last_loss_closed_at=ctx.risk_last_loss_closed_at,
        trade_open_timestamps=ctx.risk_trade_open_timestamps,
        existing_open_risk_pct=ctx.risk_existing_open_risk_pct,
        proposed_stop=ctx.trader_stop,
    )

    if not result.passed:
        return Verdict(
            action=VerdictAction.REJECT,
            reason=f"Mandate violation: {'; '.join(result.violations)}",
            violations=result.violations,
            overridden_from_llm=True,
        )

    return Verdict(
        action=VerdictAction.APPROVE,
        size_pct=ctx.trader_size_pct,
        entry=ctx.trader_entry,
        target=ctx.trader_target,
        stop=ctx.trader_stop,
        time_horizon_days=ctx.trader_horizon_weeks * 7,
        reason=(
            f"Synthesis defended; sizing consistent with risk_score "
            f"{ctx.mandate.risk_score}; mandate checks pass."
        ),
        # CR106 B1 — the scripted path takes all three levels from the Trader,
        # so it says so. There is no PM decision on this route to attribute
        # them to.
        level_provenance={
            "entry": "trader",
            "stop": "trader",
            "target": "trader",
        },
    )


# ── Streaming the contributions ───────────────────────────────────────────


# Per-character delay range (mock streaming — gives the Matrix Console
# typewriter feel without burning real LLM cost).
_CHAR_DELAY_MIN = 0.004
_CHAR_DELAY_MAX = 0.012
_PHASE_GAP_S = 0.25
# Maximum seconds to wait for a single agent's LLM response. If the
# upstream model hangs (network stall, vLLM queue backup), the agent
# falls back to its scripted template so the room run can still finish
# and produce a verdict rather than stalling forever.
_AGENT_LLM_TIMEOUT_S = 90.0


@dataclass
class RoomEvent:
    """A single streamed event from the Room runner.

    The API layer (room.py) translates this into SSE.
    """
    # 'live_data_notice' (CR090) is the structural live-data disclosure — the
    # LLM is out of the loop; the client renders `live_data` directly. The
    # shipped Flutter parser tolerates unknown SSE event kinds (both switch
    # layers have no `default`), so emitting it does not break clients that
    # predate CR090-MOBILE — they simply ignore it.
    kind: str  # 'started' | 'live_data_notice' | 'phase' | 'agent_token' | 'agent_done' | 'agent_withheld' | 'verdict' | 'error'
    phase: str | None = None
    agent_id: AgentId | None = None
    text: str | None = None
    verdict: Verdict | None = None
    run_id: UUID | None = None
    live_data: dict[str, Any] | None = None
    # CR098 — carried on 'agent_withheld' only. `reason` is always "upgrade"
    # (tenure pull-back — Fundamentals is unwithholdable so there's no other
    # reason a Room event carries this kind). `next_step_*` is the roster's
    # single nearest upcoming pull-back event (not per-agent — see hand-off),
    # for the client's countdown; None once nothing further is scheduled.
    reason: str | None = None
    next_step_agent: AgentId | None = None
    next_step_days: int | None = None
    # CR106 B2 — carried on 'agent_done' only. All three are None whenever the
    # agent did not state a position; the client puts that hex in the comb's
    # gutter and never in a band (T-SUM11).
    stance: str | None = None
    conviction: str | None = None
    headline: str | None = None


PLAN_TO_TIER: dict[Plan, str] = {
    Plan.FLOOR_PASS: "cheap",
    Plan.TRADER: "mid",
    Plan.TRIAL_TRADER: "mid",
    Plan.FLOOR_MANAGER: "premium",
}


@dataclass(frozen=True)
class _PendingRetry:
    """Stuck-run row claimed by _sweep_stuck_runs for async respawn (eeeb866f)."""

    run_id: UUID
    user_id: UUID
    ticker: str
    mandate_version: int


def _row_to_room_run(row: RoomRunRow) -> RoomRun:
    transcript = [AgentMessage.model_validate(m) for m in (row.transcript or [])]
    verdict = Verdict.model_validate(row.verdict) if row.verdict else None
    return RoomRun(
        id=row.id,
        user_id=row.user_id,
        ticker=row.ticker,
        triggered_at=row.triggered_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
        mandate_version=row.mandate_version,
        model_tier=row.model_tier,  # type: ignore[arg-type]
        rounds=row.rounds,
        transcript=transcript,
        verdict=verdict,
        credit_cost=row.credit_cost,
        status=RoomStatus(row.status),
        error_message=row.error_message,
        duration_ms=row.duration_ms,
    )


def _persist_run(run: RoomRun) -> None:
    """Upsert a RoomRun into the DB. Last-write-wins on (id)."""
    with get_session() as s:
        row = s.execute(
            select(RoomRunRow).where(RoomRunRow.id == run.id)
        ).scalar_one_or_none()
        transcript_json = [m.model_dump(mode="json") for m in run.transcript]
        verdict_json = run.verdict.model_dump(mode="json") if run.verdict else None
        if row is None:
            s.add(RoomRunRow(
                id=run.id,
                user_id=run.user_id,
                ticker=run.ticker,
                triggered_at=run.triggered_at,
                started_at=run.started_at,
                finished_at=run.finished_at,
                mandate_version=run.mandate_version,
                model_tier=run.model_tier,
                rounds=run.rounds,
                transcript=transcript_json,
                verdict=verdict_json,
                credit_cost=run.credit_cost,
                status=run.status if isinstance(run.status, str) else run.status.value,
                error_message=run.error_message,
                duration_ms=run.duration_ms,
            ))
        else:
            row.ticker = run.ticker
            row.started_at = run.started_at
            row.finished_at = run.finished_at
            row.mandate_version = run.mandate_version
            row.model_tier = run.model_tier
            row.rounds = run.rounds
            row.transcript = transcript_json
            row.verdict = verdict_json
            row.credit_cost = run.credit_cost
            row.status = run.status if isinstance(run.status, str) else run.status.value
            row.error_message = run.error_message
            row.duration_ms = run.duration_ms


def _checkpoint_run(run: RoomRun) -> None:
    """Incremental transcript snapshot after each agent completes.

    Wrapped in try/except so a transient DB hiccup does not kill the run —
    the final _persist_run() call at completion is still authoritative.
    Narrows the data-loss window from "entire run" to "last one agent".
    """
    try:
        _persist_run(run)
    except Exception as exc:
        logger.warning(
            "room_checkpoint_failed",
            run_id=str(run.id),
            error=str(exc)[:200],
        )


JOURNAL_SUMMARY_MAX = 240


def _clip_summary(text: str, limit: int = JOURNAL_SUMMARY_MAX) -> str:
    """Clip to [limit] on a word boundary, marking the cut.

    DEF150: this was a bare ``summary[:240]``, so the Journal's permanent
    record of a decision ended ``"…the 3.05 PEG and the potential fo"`` — no
    ellipsis, no marker, a severed word. Two readers consume this field and
    both were served a fragment: the user on the Journal detail screen, and
    **Bull/Bear via ``journal_context.format_journal_entry``**, which feeds it
    back into a later run as decision-lookback (DEF098). An agent reasoning
    from a sentence that stops mid-word is the DEF125 class arriving through a
    different door — the model cannot tell a deliberate ending from a cut one.

    The mark is what makes it honest rather than merely tidier: a clip with an
    ellipsis says "there is more"; a clip without one asserts that this is the
    whole thought.
    """
    if len(text) <= limit:
        return text
    head = text[: limit - 1]
    cut = head.rsplit(" ", 1)[0] if " " in head else head
    return f"{cut.rstrip(',;:').rstrip()}…"


def build_journal_entry_for_run(run: RoomRun, user_id: UUID) -> JournalEntryCreate:
    """Build a JournalEntryCreate from a finished (or failed) RoomRun.

    Completed runs: title = "Room on {ticker} — APPROVE/REJECT"
    Failed/incomplete runs: title = "Room on {ticker} — {status}", summary
    describes how many agents completed and what error occurred (if any).

    Lives here (rather than api/room.py) so the runner's startup auto-retry
    path (AT:R34, eeeb866f) can re-fire the journal write after a container
    restart without an upward import from services → api. api/room.py
    re-exports as `_build_journal_entry` for back-compat.
    """
    if run.verdict is not None:
        title = f"Room on {run.ticker} — {run.verdict.action}"
        summary = f"{run.verdict.action} — {run.verdict.reason}"
    else:
        status = run.status if isinstance(run.status, str) else run.status.value
        agents_done = len(run.transcript)
        error_detail = (
            f" — {run.error_message[:80]}" if run.error_message else ""
        )
        title = f"Room on {run.ticker} — {status}"
        summary = (
            f"Run stopped after {agents_done} of 12 agents "
            f"without reaching a verdict{error_detail}"
        )
    return JournalEntryCreate(
        user_id=user_id,
        entry_type=EntryType.ROOM_RUN,
        reference_id=run.id,
        title=title,
        summary=_clip_summary(summary),
        ticker=run.ticker,
        agents_involved=[
            m.agent_id if isinstance(m.agent_id, str) else m.agent_id.value
            for m in run.transcript
        ],
        mandate_version=run.mandate_version,
        tags=["room"],
        outcome=Outcome.PENDING,
        payload={
            "verdict": (
                run.verdict.model_dump(mode="json") if run.verdict else None
            ),
            "model_tier": run.model_tier,
            "transcript": [
                {
                    "agent_id": (
                        m.agent_id if isinstance(m.agent_id, str)
                        else m.agent_id.value
                    ),
                    "content": m.content,
                    # CR106 B2 — frozen with the rest of the snapshot, so the
                    # Journal replays the comb this run actually produced. An
                    # entry written before the field existed has all three
                    # absent, and the replay says "not recorded" rather than
                    # reconstructing a stance from the prose (T-BACKFILL).
                    "stance": m.stance,
                    "conviction": m.conviction,
                    "headline": m.headline,
                } for m in run.transcript
            ],
        },
    )


class RoomRunner:
    """Orchestrates a Convene the Room session, streams events, persists runs."""

    def __init__(self, llm: LLMGateway | None = None) -> None:
        init_schema()
        # Late-bound so tests can pass a fake gateway via constructor.
        # In production, get_room_runner() wires get_llm_gateway() once.
        self._llm: LLMGateway | None = llm
        # Per-run event queues: keyed by run_id, alive while _pump() runs.
        # SSE consumers read from these; background tasks write to them.
        self._active_queues: dict[UUID, asyncio.Queue[RoomEvent | None]] = {}
        # In-memory dedup index: (user_id, ticker) → run_id for runs that
        # are scheduled or running. Populated before create_task; cleared in
        # _pump finally. Avoids a race where the DB INSERT hasn't fired yet
        # but a second request arrives for the same user+ticker.
        self._active_by_key: dict[tuple[UUID, str], UUID] = {}
        # Rows claimed by _sweep_stuck_runs for auto-retry on next boot
        # (AT:R34, eeeb866f). Drained by resume_pending_retries() which
        # runs from the FastAPI lifespan — splitting sync claim from async
        # respawn so __init__ doesn't need a live event loop.
        self._pending_retry: list[_PendingRetry] = []
        self._sweep_stuck_runs()

    def get_run(self, run_id: UUID) -> RoomRun | None:
        with get_session() as s:
            row = s.execute(
                select(RoomRunRow).where(RoomRunRow.id == run_id)
            ).scalar_one_or_none()
            return _row_to_room_run(row) if row else None

    def list_runs_for_user(self, user_id: UUID, limit: int = 50) -> list[RoomRun]:
        with get_session() as s:
            rows = s.execute(
                select(RoomRunRow)
                .where(RoomRunRow.user_id == user_id)
                .order_by(RoomRunRow.triggered_at.desc())
                .limit(limit)
            ).scalars().all()
            return [_row_to_room_run(r) for r in rows]

    def _sweep_stuck_runs(self) -> None:
        """On startup, claim stuck RUNNING rows for auto-retry or mark FAILED.

        A run left in status=running means the server was restarted (or the
        process was killed) while the run was in progress. These rows will
        never progress on their own.

        AT:R34 (eeeb866f) policy:
          * retry_count < MAX_AUTO_RETRIES: bump retry_count, clear the
            transcript + verdict, refresh started_at, queue for respawn
            via resume_pending_retries(). Status stays "running" — the row
            is now claimed for re-execution; dedup tier 1 will attach any
            client resubmits to the live re-run.
          * retry_count >= MAX_AUTO_RETRIES: a run that has already died
            once on retry is likely a real bug, not a transient restart.
            Mark failed so the client surfaces it and the user can
            manually resubmit (or report).

        Pure DB work — no event loop needed, runs from __init__. The
        respawn happens later in resume_pending_retries() from the
        lifespan startup hook.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(
            minutes=settings.room_dedup_running_minutes
        )
        try:
            now = datetime.now(timezone.utc)
            with get_session() as s:
                rows = s.execute(
                    select(RoomRunRow)
                    .where(RoomRunRow.status == "running")
                    .where(RoomRunRow.started_at < cutoff)
                ).scalars().all()
                retried = 0
                failed = 0
                for row in rows:
                    if row.retry_count < MAX_AUTO_RETRIES:
                        row.retry_count = row.retry_count + 1
                        row.started_at = now
                        row.transcript = []
                        row.verdict = None
                        row.error_message = None
                        self._pending_retry.append(_PendingRetry(
                            run_id=row.id,
                            user_id=row.user_id,
                            ticker=row.ticker,
                            mandate_version=row.mandate_version,
                        ))
                        retried += 1
                    else:
                        row.status = "failed"
                        row.error_message = (
                            f"abandoned: auto-retried {row.retry_count} time(s), gave up"
                        )
                        failed += 1
                if rows:
                    logger.info(
                        "room_startup_sweep",
                        queued_for_retry=retried,
                        marked_failed=failed,
                    )
        except Exception as exc:
            logger.warning("room_startup_sweep_failed", error=str(exc)[:200])

    async def resume_pending_retries(self) -> None:
        """Spawn background tasks for runs claimed by _sweep_stuck_runs.

        Called once on FastAPI startup (lifespan hook) — splits the sync
        claim done in __init__ from the async respawn so __init__ never
        needs a running event loop.

        Each respawn re-runs the entire room from scratch (transcript was
        cleared by the sweep) using the original mandate version + ticker.
        Mid-run resumption from the checkpointed transcript is Tier 2
        (10-12 days per the bug); a full retry is cheaper to ship and the
        user-visible effect is the same: the verdict eventually lands in
        the journal regardless of whether the SSE consumer is still around.
        """
        pending = list(self._pending_retry)
        self._pending_retry.clear()
        for p in pending:
            try:
                await self._respawn_run_from_row(p)
            except Exception as exc:
                logger.warning(
                    "room_startup_retry_spawn_failed",
                    run_id=str(p.run_id),
                    error=str(exc)[:200],
                )

    async def _respawn_run_from_row(self, p: _PendingRetry) -> None:
        """Re-spawn a stuck run from its DB state (AT:R34, eeeb866f).

        Reuses the existing run_id so client-side references (mobile's
        cached run_id, journal reference_id, dedup attach) keep working.

        Mandate resolution: prefer the exact version originally used
        (preserves intent if the row references v1 and the user has since
        moved to v2). Fall back to resolve_mandate when the stored
        version doesn't exist — typical for users who never customised
        their mandate, where mandate_version=1 is just a default-hydrated
        placeholder that was never persisted to the mandates table.
        """
        from app.services.mandate_store import get_mandate_store, resolve_mandate

        mandate = get_mandate_store().get_version(p.user_id, p.mandate_version)
        if mandate is None:
            # Default-hydrated mandate path — common before Brief Your Agent
            # has been used. resolve_mandate always returns a Mandate.
            mandate = resolve_mandate(p.user_id, None)
            logger.info(
                "room_startup_retry_mandate_fallback",
                run_id=str(p.run_id),
                user_id=str(p.user_id),
                mandate_version=p.mandate_version,
            )

        key = (p.user_id, p.ticker.upper())
        q: asyncio.Queue[RoomEvent | None] = asyncio.Queue()
        self._active_queues[p.run_id] = q
        self._active_by_key[key] = p.run_id

        async def _pump() -> None:
            try:
                async for ev in self.run(
                    run_id=p.run_id,
                    user_id=p.user_id,
                    ticker=p.ticker,
                    mandate=mandate,
                ):
                    await q.put(ev)
            except Exception as exc:
                await q.put(RoomEvent(
                    kind="error", run_id=p.run_id, text=str(exc)[:300],
                ))
            finally:
                await q.put(None)
                self._active_queues.pop(p.run_id, None)
                self._active_by_key.pop(key, None)
                # Re-fire the journal write the original request's
                # on_complete would have done — the closure is gone after
                # restart, so we replay it here. Same 3× retry shape as
                # api/room.py:_finalise_to_journal.
                run = self.get_run(p.run_id)
                if run is None:
                    return
                for attempt in range(3):
                    try:
                        get_journal_store().append(
                            build_journal_entry_for_run(run, p.user_id)
                        )
                        logger.info(
                            "room_startup_retry_journal_written",
                            run_id=str(p.run_id),
                        )
                        return
                    except Exception as exc:
                        if attempt == 2:
                            logger.error(
                                "room_startup_retry_journal_failed",
                                run_id=str(p.run_id),
                                error=str(exc)[:200],
                            )
                        else:
                            await asyncio.sleep(2 ** attempt)

        asyncio.create_task(_pump())
        logger.info(
            "room_startup_retry_respawned",
            run_id=str(p.run_id),
            ticker=p.ticker,
        )

    def _find_active_run(self, user_id: UUID, ticker: str) -> UUID | None:
        """Return run_id of an in-flight run for this user+ticker.

        Catches the mobile-retry case where a client resubmits because the
        SSE connection dropped — instead of starting a fresh run, the new
        SSE consumer attaches to the one already executing.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(
            minutes=settings.room_dedup_running_minutes
        )
        with get_session() as s:
            row = s.execute(
                select(RoomRunRow)
                .where(RoomRunRow.user_id == user_id)
                .where(RoomRunRow.ticker == ticker)
                .where(RoomRunRow.status == "running")
                .where(RoomRunRow.started_at >= cutoff)
                .order_by(RoomRunRow.triggered_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            return row.id if row else None

    def _find_recent_completed_run(self, user_id: UUID, ticker: str) -> UUID | None:
        """Return run_id of a recently COMPLETED run for this user+ticker.

        Implements the design-doc resubmission rule: if the same user already
        has a successful verdict on this ticker within the configurable lookback
        window (settings.room_dedup_completed_hours), return that verdict
        instead of burning another 5 minutes of LLM time on essentially the
        same analysis. The market hasn't moved enough since this morning to
        warrant a fresh debate.

        Only matches `status="completed"` runs that produced a verdict — failed
        and cancelled runs are not deduped (the user should be free to retry).
        """
        if settings.room_dedup_completed_hours <= 0:
            return None  # window disabled
        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=settings.room_dedup_completed_hours
        )
        with get_session() as s:
            row = s.execute(
                select(RoomRunRow)
                .where(RoomRunRow.user_id == user_id)
                .where(RoomRunRow.ticker == ticker)
                .where(RoomRunRow.status == "completed")
                .where(RoomRunRow.verdict.isnot(None))
                .where(RoomRunRow.finished_at >= cutoff)
                .order_by(RoomRunRow.finished_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            return row.id if row else None

    def _resolve_and_charge_feeds(
        self, user_id: UUID, ticker: str, *, withheld: frozenset[AgentId] = frozenset()
    ) -> tuple[NewsFeed, SocialFeed, int]:
        """CR090 (D1/D2/D4/D5) — resolve the two live-data feeds ONCE, decide
        entitlement off the credit balance, and make the single atomic charge.

        Returns `(news_feed, social_feed, charged_total)` — the feeds carry the
        final 3-state marker (LIVE / WITHHELD_PAID / UNAVAILABLE / WITHHELD_TENURE)
        and `LIVE` ones carry their real payload; `charged_total` is exactly what
        was debited (base, or base + surcharge). Raises `InsufficientCredits` (the
        402 path) untouched when the balance won't even cover the base.

        The probe runs at `entitled=True`, so `state is LIVE` means data really
        exists right now; a non-entitled turn then downgrades those to
        WITHHELD_PAID (payload dropped) — never a silent synthetic swap (DEF059).

        CR098 (D1/D2): `withheld` is the roster gate — a THIRD, independent
        question from credit entitlement (D1: compose, don't overwrite). A
        roster-withheld analyst's feed is never probed at all (its fetch is
        skipped outright, banking the API cost per scope item 4) and never
        counted in `n_available`, so the surcharge naturally reflects only what
        was actually fetched (D2) without a second debit call site.
        """
        base = room_cost_for_plan(effective_plan_for_user(user_id))
        live = settings.use_real_market_data
        news_probe = (
            NewsFeed(LiveDataState.WITHHELD_TENURE, ())
            if AgentId.NEWS_ANALYST in withheld
            else resolve_news_feed(ticker, entitled=True) if live
            else NewsFeed(LiveDataState.UNAVAILABLE, ())
        )
        social_probe = (
            SocialFeed(LiveDataState.WITHHELD_TENURE, None)
            if AgentId.SOCIAL_MEDIA_ANALYST in withheld
            else resolve_social_feed(ticker, entitled=True) if live
            else SocialFeed(LiveDataState.UNAVAILABLE, None)
        )
        n_available = sum(
            1 for p in (news_probe.state, social_probe.state)
            if p is LiveDataState.LIVE
        )
        surcharge = live_data_surcharge(n_available)

        # Entitled ONLY when the balance covers the whole live bundle. The
        # balance read re-grants first (idempotent — spend's own _ensure_period
        # is then a no-op), so the two agree on the plan/period. n_available == 0
        # short-circuits, so a no-live-data run never reads the balance early and
        # never leaves the byte-for-byte CR039 spend(None) path (winzip intact).
        entitled = n_available > 0 and balance_for(user_id)[0] >= base + surcharge

        if entitled:
            # Explicit amount folds the surcharge into the one atomic spend (D1).
            _, charged_total = spend(
                user_id, base + surcharge,
                reason=f"room:{ticker.upper()}:live+{surcharge}",
            )
        else:
            # Base only, via spend(None): preserves the CR047 winzip soft-wall
            # and the CR039 402 for a genuinely broke user (both live inside
            # spend, keyed on amount is None). Available feeds become
            # WITHHELD_PAID and cost nothing (D5).
            _, charged_total = spend(user_id, None, reason=f"room:{ticker.upper()}")

        def _final_state(probe_state: LiveDataState) -> LiveDataState:
            if probe_state is LiveDataState.LIVE and not entitled:
                return LiveDataState.WITHHELD_PAID
            return probe_state

        news_state = _final_state(news_probe.state)
        social_state = _final_state(social_probe.state)
        news_feed = NewsFeed(
            news_state,
            news_probe.headlines if news_state is LiveDataState.LIVE else (),
        )
        social_feed = SocialFeed(
            social_state,
            social_probe.sentiment if social_state is LiveDataState.LIVE else None,
        )
        return news_feed, social_feed, charged_total

    async def start_run(
        self,
        *,
        user_id: UUID,
        ticker: str,
        mandate: Mandate,
        portfolio_value: float = 100_000.0,
        current_drawdown_pct: float = 0.0,
        char_delay_min: float = _CHAR_DELAY_MIN,
        char_delay_max: float = _CHAR_DELAY_MAX,
        agent_timeout_s: float = _AGENT_LLM_TIMEOUT_S,
        on_complete: Callable[[UUID], Awaitable[None]] | None = None,
        backtest: AsOfContext | None = None,
    ) -> UUID:
        """Start a room run as a detached background task. Returns run_id immediately.

        CR164 `backtest`: an as-of context puts the ENTIRE run into historical
        mode — the data layer serves only facts knowable on `backtest.as_of`
        (ContextVar, set around the pump task), the news/social probes are
        skipped (UNAVAILABLE feeds, honest absence), and both dedup tiers are
        bypassed (they exist to stop mobile-retry double-billing; a sweep
        legitimately convenes one ticker at many dates). Idempotency moves to
        `backtest_run_index`'s UNIQUE(batch_id, ticker, as_of) — a duplicate
        (batch, ticker, as_of) raises here, loudly, BEFORE anything is charged.
        Only the admin backtest endpoint constructs an AsOfContext; the public
        Room API cannot reach this parameter.

        The run executes in a background asyncio.Task independent of the SSE
        connection — a client disconnect does not cancel the run. Events flow
        into a per-run asyncio.Queue; callers consume them via subscribe().

        Deduplication: if the same user already has a RUNNING run for this
        ticker (within the last 30 min), attach to it and return its run_id
        instead of starting a new one. This prevents double-billing on mobile
        retries after a connection drop.

        on_complete is called once the run reaches a terminal state (completed,
        failed, or cancelled). It fires even when the SSE consumer is gone, so
        journal writes and push notification hooks happen regardless of whether
        the client was still connected.
        """
        key = (user_id, ticker.upper())

        if backtest is not None:
            run_id = uuid4()
            # Idempotency gate FIRST — a driver retry of a completed
            # (batch, ticker, as_of) pair must die here, before any charge.
            # IntegrityError propagates loudly; the sweep driver skips on it.
            with get_session() as session:
                session.add(BacktestRunIndexRow(
                    room_run_id=run_id,
                    batch_id=backtest.batch_id,
                    arm=backtest.arm,
                    ticker=ticker.upper(),
                    as_of=backtest.as_of,
                ))
            # Base charge through the real spend path (CR039 metering stays
            # exercised); no live-data surcharge — both feeds are ablated.
            #
            # A failed charge must UNDO the index row. The gate is written
            # first so a duplicate pair dies before spending anything, but
            # that ordering means a 402 would otherwise leave the pair
            # indexed-but-never-run: the sweep tops up credits, retries, and
            # gets 409 from its own orphan — the pair is silently lost for
            # the life of the batch. Observed once in the CR164 pilot
            # (PLD@2025-12-05), which is exactly one convene of evidence that
            # this is not theoretical.
            try:
                _, charged_total = spend(
                    user_id, None, reason=f"room:{ticker.upper()}:backtest",
                )
            except Exception:
                with get_session() as session:
                    session.execute(
                        delete(BacktestRunIndexRow).where(
                            BacktestRunIndexRow.room_run_id == run_id
                        )
                    )
                raise
            news_feed = NewsFeed(LiveDataState.UNAVAILABLE, ())
            social_feed = SocialFeed(LiveDataState.UNAVAILABLE, None)
            roster = resolve_roster_for_user(user_id)
            logger.info(
                "backtest_run_starting",
                run_id=str(run_id),
                ticker=ticker,
                as_of=backtest.as_of.isoformat(),
                batch_id=backtest.batch_id,
                dedup_bypassed=True,
                feeds_ablated=True,
            )
            q: asyncio.Queue[RoomEvent | None] = asyncio.Queue()
            self._active_queues[run_id] = q

            async def _pump_backtest() -> None:
                try:
                    with asof_scope(backtest):
                        async for ev in self.run(
                            run_id=run_id,
                            user_id=user_id,
                            ticker=ticker,
                            mandate=mandate,
                            portfolio_value=portfolio_value,
                            current_drawdown_pct=current_drawdown_pct,
                            char_delay_min=char_delay_min,
                            char_delay_max=char_delay_max,
                            agent_timeout_s=agent_timeout_s,
                            news_feed=news_feed,
                            social_feed=social_feed,
                            credit_cost=charged_total,
                            roster=roster,
                            backtest=backtest,
                        ):
                            await q.put(ev)
                except Exception as exc:
                    await q.put(RoomEvent(kind="error", run_id=run_id, text=str(exc)[:300]))
                finally:
                    await q.put(None)
                    self._active_queues.pop(run_id, None)
                    if on_complete is not None:
                        try:
                            await on_complete(run_id)
                        except Exception as exc:
                            logger.warning(
                                "room_on_complete_failed",
                                run_id=str(run_id),
                                error=str(exc)[:200],
                            )

            asyncio.create_task(_pump_backtest())
            return run_id

        # Dedup tier 1 — in-flight run (in-memory first, DB fallback).
        # In-memory catches the create_task → first INSERT race; DB fallback
        # catches the case where the in-memory dict was cleared by a restart
        # but the row is still status=running.
        existing = self._active_by_key.get(key)
        if existing is None:
            existing = self._find_active_run(user_id, ticker)
        if existing is not None:
            logger.info(
                "room_dedup_attached_running",
                run_id=str(existing),
                user_id=str(user_id),
                ticker=ticker,
            )
            return existing

        # Dedup tier 2 — recently completed run with a verdict.
        # Returns the previous verdict instead of re-analysing the same
        # ticker before the market has meaningfully moved.
        completed = self._find_recent_completed_run(user_id, ticker)
        if completed is not None:
            logger.info(
                "room_dedup_attached_completed",
                run_id=str(completed),
                user_id=str(user_id),
                ticker=ticker,
                window_hours=settings.room_dedup_completed_hours,
            )
            return completed

        # CR039 (AT:R60): charge here — past both dedup tiers, before any work
        # is committed to. This is the only point where we've decided to run a
        # real Room, so it's the only point that can bill exactly once. Charging
        # in the API layer instead would bill every reconnect and re-analysis
        # request, defeating the dedup above (whose stated purpose is to prevent
        # double-billing) and turning a flaky LTE handoff into a paywall.
        # InsufficientCredits propagates to the endpoint as a 402.
        #
        # CR090 (D1/D2/D5): the live-data surcharge folds into THIS one spend —
        # there is exactly one spend() in the whole run, so a second mid-run
        # debit can never raise InsufficientCredits after the base is paid and
        # the Room is half-streamed. Entitlement is the credit BALANCE, not a
        # plan tier (D2): probe both feeds' availability (cache-first), and only
        # if the balance covers base + surcharge does the run buy the live
        # bundle. Otherwise it pays the base alone via spend(None) — which keeps
        # the CR047 winzip soft-wall and the CR039 402 wall intact — and the
        # available feeds resolve WITHHELD_PAID (loud disclosure, charged
        # nothing, D5). All-or-nothing on the bundle: both live feeds or neither
        # (a partial "buy what you can afford" was rejected as unpredictable
        # pricing — a one-branch change here if ever wanted).
        # CR098 — resolve the analyst roster BEFORE the feeds so a roster-
        # withheld News/Social analyst's fetch is never probed (D2: money
        # moves as a deliberate consequence of the roster gate, not a side
        # effect discovered later).
        roster = resolve_roster_for_user(user_id)
        news_feed, social_feed, charged_total = self._resolve_and_charge_feeds(
            user_id, ticker, withheld=frozenset(roster.withheld)
        )

        run_id = uuid4()
        q: asyncio.Queue[RoomEvent | None] = asyncio.Queue()
        self._active_queues[run_id] = q
        self._active_by_key[key] = run_id  # register before task starts

        async def _pump() -> None:
            try:
                async for ev in self.run(
                    run_id=run_id,
                    user_id=user_id,
                    ticker=ticker,
                    mandate=mandate,
                    portfolio_value=portfolio_value,
                    current_drawdown_pct=current_drawdown_pct,
                    char_delay_min=char_delay_min,
                    char_delay_max=char_delay_max,
                    agent_timeout_s=agent_timeout_s,
                    news_feed=news_feed,
                    social_feed=social_feed,
                    credit_cost=charged_total,
                    roster=roster,
                ):
                    await q.put(ev)
            except Exception as exc:
                await q.put(RoomEvent(kind="error", run_id=run_id, text=str(exc)[:300]))
            finally:
                await q.put(None)  # sentinel — unblocks any waiting subscribe() call
                self._active_queues.pop(run_id, None)
                self._active_by_key.pop(key, None)  # deregister dedup key
                if on_complete is not None:
                    try:
                        await on_complete(run_id)
                    except Exception as exc:
                        logger.warning(
                            "room_on_complete_failed",
                            run_id=str(run_id),
                            error=str(exc)[:200],
                        )

        asyncio.create_task(_pump())
        return run_id

    def is_active(self, run_id: UUID) -> bool:
        """True if the run has an active event queue (fresh run or dedup-of-running).
        False means the run_id was returned by completed-run dedup (or the run
        finished between start_run and the check) — the caller should replay
        the persisted snapshot rather than wait for events on subscribe().
        """
        return run_id in self._active_queues

    async def subscribe(self, run_id: UUID) -> AsyncIterator[RoomEvent]:
        """Yield events from the queue for an in-progress run.

        Returns immediately if the run is no longer in _active_queues (already
        completed before the caller subscribed). In that case the caller should
        GET /v1/room/{run_id} for the persisted snapshot.
        """
        q = self._active_queues.get(run_id)
        if q is None:
            return
        while True:
            ev = await q.get()
            if ev is None:
                return  # sentinel — background task finished
            yield ev

    async def run(
        self,
        *,
        run_id: UUID | None = None,
        user_id: UUID,
        ticker: str,
        mandate: Mandate,
        portfolio_value: float = 100_000.0,
        current_drawdown_pct: float = 0.0,
        halal_universe: set[str] | None = None,
        classification_universe: object | None = None,
        locale_allowed_universe: set[str] | None = None,
        char_delay_min: float = _CHAR_DELAY_MIN,
        char_delay_max: float = _CHAR_DELAY_MAX,
        agent_timeout_s: float = _AGENT_LLM_TIMEOUT_S,
        news_feed: NewsFeed | None = None,
        social_feed: SocialFeed | None = None,
        credit_cost: int | None = None,
        roster: AnalystRoster | None = None,
        backtest: AsOfContext | None = None,
    ) -> AsyncIterator[RoomEvent]:
        """Run a Room session, yielding events as agents speak.

        The function returns an async generator. Callers consume it; the
        final event is a `verdict` with the assembled Verdict, after which
        the RoomRun is finalised and stored.

        `run_id` is optional — if provided (by start_run), the caller
        pre-allocated the ID so it can set up the event queue before the
        generator starts. If omitted, a fresh UUID is generated here.

        CR090 (D1/D4): `news_feed`/`social_feed` are the live-data feeds
        start_run already resolved AND priced before the atomic charge — they
        are threaded down so the profile the agents see matches exactly what was
        billed (never a second, possibly-divergent fetch). `credit_cost` is the
        total actually charged (base + live-data surcharge) so the persisted row
        and the failure-path refund cover the real amount, not just the base.
        All three are optional: the respawn / direct-call path leaves them None
        and falls back to base pricing + entitled=True feed resolution, which is
        the pre-CR090 behaviour verbatim.
        """
        run_id = run_id or uuid4()
        now = datetime.now(timezone.utc)
        # CR098: start_run already resolved the roster (and priced the feeds
        # against it); the respawn/direct-call path (roster is None) resolves
        # it fresh here, same fallback shape as news_feed/social_feed above.
        if roster is None:
            roster = resolve_roster_for_user(user_id) if user_id is not None else AnalystRoster(
                present=(
                    AgentId.FUNDAMENTALS_ANALYST, AgentId.MARKET_ANALYST,
                    AgentId.NEWS_ANALYST, AgentId.SOCIAL_MEDIA_ANALYST,
                ),
                withheld=(), next_step=None,
            )
        # BL11 (AT:R33): effective_plan downgrades expired trials.
        plan = effective_plan_for_user(user_id)
        tier = pick_tier(plan, AgentId.PORTFOLIO_MANAGER)
        # CR039/CR090: the charge start_run actually made is the source of truth
        # for the row (so a refund on failure returns the surcharge too). Absent
        # (respawn/direct) it falls back to the plan's base Room price.
        credit_cost = credit_cost if credit_cost is not None else room_cost_for_plan(plan)

        run = RoomRun(
            id=run_id,
            user_id=user_id,
            ticker=ticker.upper(),
            triggered_at=now,
            started_at=now,
            mandate_version=mandate.version,
            model_tier=tier,  # type: ignore[arg-type]
            rounds=1,
            transcript=[],
            verdict=None,
            credit_cost=credit_cost,
            status=RoomStatus.RUNNING,
        )
        _persist_run(run)
        logger.info("room_started", run_id=str(run_id), ticker=ticker, tier=tier)

        # Emit `started` first so clients have the run_id immediately —
        # critical for the "phone went to sleep, come back and see results"
        # recovery path. Without this, the run_id only landed on the final
        # `done` event, useless to a disconnected client.
        yield RoomEvent(kind="started", run_id=run_id)

        # CR090 (D3/D4) — the live-data disclosure, emitted STRUCTURALLY from the
        # runner with the model completely out of the loop. A prompt instruction
        # would be dropped ~70% of the time (CR038) and the user would silently
        # believe the synthetic block is just how the agent behaves — DEF059's
        # exact shape. Resolve the feeds ONCE here (start_run pre-resolves +
        # prices them; None only on the respawn/direct path, where entitled=True
        # reproduces the pre-CR090 behaviour) and thread the SAME objects into
        # the profile the agents see, so what was charged always matches what was
        # rendered. The surcharge reported is what was ACTUALLY billed
        # (credit_cost − base), never merely what the feeds imply.
        # CR098 round-2 fix (MINOR 1) — gate these fallbacks by the SAME
        # roster the analysts are already filtered against. The respawn/
        # direct-call path (news_feed/social_feed both None) previously
        # resolved at entitled=True ungated by roster, so a withheld
        # analyst's real data was fetched and rendered anyway, and
        # live_data_notice reported "live" for an analyst that never ran —
        # asymmetric with Market, which reads `roster.withheld` directly.
        if news_feed is None:
            news_feed = (
                NewsFeed(LiveDataState.WITHHELD_TENURE, ())
                if AgentId.NEWS_ANALYST in roster.withheld
                else resolve_news_feed(ticker, entitled=True)
                if settings.use_real_market_data
                else NewsFeed(LiveDataState.UNAVAILABLE, ())
            )
        if social_feed is None:
            social_feed = (
                SocialFeed(LiveDataState.WITHHELD_TENURE, None)
                if AgentId.SOCIAL_MEDIA_ANALYST in roster.withheld
                else resolve_social_feed(ticker, entitled=True)
                if settings.use_real_market_data
                else SocialFeed(LiveDataState.UNAVAILABLE, None)
            )
        surcharge_charged = max(0, credit_cost - room_cost_for_plan(plan))
        yield RoomEvent(
            kind="live_data_notice",
            run_id=run_id,
            live_data={
                "news": news_feed.state.value,
                "social": social_feed.state.value,
                "surcharge_charged": surcharge_charged,
            },
        )

        # Halal universe: sourced AAOIFI allowlist w/ three-state resolver + loud degrade (CR069).
        halal = halal_universe or await default_halal_universe_async()
        # DEF061: sourced sector/industry exclusion sets (no_fossil_fuels /
        # no_tobacco_alcohol_gambling) — four-state resolver + loud degrade, same
        # off-request-path stored-row read the halal universe uses.
        classification = (
            classification_universe or await default_classification_universe_async()
        )
        # None = no locale restriction (default for alpha). Explicit set ⇒ enforced.
        locale_allowed = locale_allowed_universe

        # AT:R45 — fetch Alpaca paper portfolio once per run; folded into the
        # portfolio block as a clearly-labelled overlay. Best-effort: None if
        # unlinked or error.
        alpaca_snap: str | None = None
        if user_id is not None:
            from app.db.models import User
            from sqlalchemy import select as sa_select
            with get_session() as s:
                urow = s.execute(sa_select(User).where(User.id == user_id)).scalar_one_or_none()
                if urow and urow.alpaca_access_token:
                    alpaca_snap = alpaca_snapshot_text(
                        urow.alpaca_access_token,
                        auth_mode=urow.alpaca_auth_mode or "oauth",
                        api_secret=urow.alpaca_refresh_token if urow.alpaca_auth_mode == "apikey" else None,
                    )

        # CR055 — the real simulated holdings, injected UNCONDITIONALLY into every
        # agent's prompt (never gated on an Alpaca link). Degrades loudly on failure;
        # the sim block is authoritative, Alpaca is a labelled overlay on top.
        # DEF136: `to_thread`, not a bare call. Both builders reach
        # `SimEngine.current_marks` -> `_marks_with_quotes`, which opens a
        # ThreadPoolExecutor and `pool.map`s a yfinance quote per holding. Called
        # directly from this coroutine that fan-out ran ON the loop thread, so
        # every other Room stream, SSE heartbeat and request served by this
        # worker stalled for its full duration, on every single convene.
        sim_block = await asyncio.to_thread(_build_sim_holdings_block, user_id, ticker)
        portfolio_snapshot = _compose_portfolio_block(sim_block, alpaca_snap)

        # CR026: sector-concentration inputs (holdings + marks + resolver + weights),
        # built once per run off the request path.
        sector_holdings, sector_marks, sector_map, sector_weights = (
            await asyncio.to_thread(_build_room_sector_context, user_id)
        )

        # CR101-BE2 round 2: same trade-history context sim_engine.py's submit()/
        # preview() build for themselves — the Room used to supply none of it.
        risk_last_loss_closed_at, risk_trade_open_timestamps, risk_existing_open_risk_pct = (
            await asyncio.to_thread(
                _build_room_risk_limit_context,
                user_id, portfolio_value=portfolio_value, quotes=sector_marks,
            )
        )

        profile = await asyncio.to_thread(
            _profile_for_ticker,
            ticker,
            news_feed=news_feed,
            social_feed=social_feed,
            withheld=frozenset(roster.withheld),
            # CR164 — explicit beside the ContextVar (belt and braces): the
            # date anchor and the PIT fundamentals fetch take the parameter;
            # provider reads under this call ride the inherited context.
            as_of=backtest.as_of if backtest is not None else None,
        )
        ctx = _RoomContext(
            ticker=ticker.upper(),
            mandate=mandate,
            portfolio_value=portfolio_value,
            current_drawdown_pct=current_drawdown_pct,
            halal_universe=halal,
            classification_universe=classification,
            locale_allowed_universe=locale_allowed,
            user_id=user_id,
            portfolio_snapshot=portfolio_snapshot,
            sector_map=sector_map,
            sector_holdings=sector_holdings,
            sector_marks=sector_marks,
            sector_weights=sector_weights,
            risk_last_loss_closed_at=risk_last_loss_closed_at,
            risk_trade_open_timestamps=risk_trade_open_timestamps,
            risk_existing_open_risk_pct=risk_existing_open_risk_pct,
            withheld=roster.withheld,
            roster_next_step=roster.next_step,
            profile=profile,
        )

        profile = ctx.profile
        # Initialise trader prices off the profile. CR104: `base_price` is no
        # longer guaranteed (live-or-absent, no rng fallback) — this is the
        # scripted-`_TEMPLATES` demo path (no real LLM reachable), not the
        # LLM-facing prompt, so it falls back to the market-data provider's
        # own declared-simulation price (MockWalkProvider, out of CR104's
        # scope per D3) rather than crashing on a missing key.
        base = profile.get("base_price")
        if base is None:
            base = get_market_data_provider().get_price(ticker.upper().strip()) or 100.0
        ctx.trader_entry = round(base, 2)
        ctx.trader_stop = round(base * 0.94, 2)
        ctx.trader_target = round(base * 1.13, 2)
        ctx.trader_size_pct = _risk_tier_size_ceiling(mandate)
        # Debate spread lives next to the caps it orbits (CR046 M03).
        _debator = risk_debator_sizes(ctx.trader_size_pct)
        ctx.aggressive_size_pct = _debator.aggressive
        ctx.conservative_size_pct = _debator.conservative
        ctx.neutral_size_pct = _debator.neutral

        # Derived figures — computed in trading_math, never left to the scripted
        # f-strings to (mis-)do: R:R (M06), upside/downside asymmetry (M08).
        _rr = risk_reward(ctx.trader_entry, ctx.trader_stop, ctx.trader_target)
        _asym = trade_asymmetry(ctx.trader_entry, ctx.trader_stop, ctx.trader_target)
        _net_phrase = net_position_phrase(profile.get("net_cash")) or "net cash n/a"

        # Run-context sent into f-string formatters; we merge per-template
        formatter = dict(profile)
        # CR104: the scripted `_TEMPLATES` fallback (used only when no real
        # LLM is reachable — never the LLM-facing prompt, which is
        # `_format_profile`) still names these fields positionally in its
        # canned sentences. They're no longer guaranteed live, so backfill
        # an honest "not available" for `.format()` rather than a KeyError.
        for _field in (
            "pe", "rev_growth", "profit_margin", "rsi", "rsi_tone", "trend",
            "support", "breakout", "last_close", "low", "high", "volume_tone",
            "base_price",
        ):
            formatter.setdefault(_field, "not available")
        formatter.update({
            "ticker": ctx.ticker,
            "forward_pe_clause": _forward_pe_clause(profile),
            "risk_score": mandate.risk_score,
            "action": "BUY",
            "entry": ctx.trader_entry,
            "stop": ctx.trader_stop,
            "target": ctx.trader_target,
            "horizon_weeks": ctx.trader_horizon_weeks,
            "size_pct": f"{ctx.trader_size_pct:.1f}",
            # The scripted stop is a fixed ~6% protective stop, not a 20-day low —
            # don't claim a level-basis the number wasn't derived from (audit F8).
            "stop_basis": "~6% protective stop",
            "rr": f"{_rr:.1f}" if _rr is not None else "n/a",
            "net_cash_phrase": _net_phrase,
            "agg_size": f"{ctx.aggressive_size_pct:.1f}",
            "cons_size": f"{ctx.conservative_size_pct:.1f}",
            "neu_size": f"{ctx.neutral_size_pct:.1f}",
            "synth_size": f"{ctx.trader_size_pct:.1f}",
        })
        if _asym is not None:
            # Replace the fixed "28% vs 18%" seed constants with the real
            # asymmetry of the reference levels (M08).
            formatter["upside"] = _asym.upside_pct
            formatter["downside"] = _asym.downside_pct

        gateway = self._llm or get_llm_gateway()
        live = gateway.has_real_provider()

        try:
            for phase in PHASES:
                yield RoomEvent(kind="phase", phase=phase.label, run_id=run_id)
                # CR098 — analysts on the tenure pull-back roster never run.
                # Filtering by ctx.withheld is safe for every phase: withheld
                # only ever names ANALYSTS-phase agents, so this is a no-op
                # for RESEARCHERS/SYNTHESIS/EXECUTION/RISK/VERDICT.
                phase_agents = tuple(a for a in phase.agents if a not in ctx.withheld)
                if phase.label == "ANALYSTS" and ctx.withheld:
                    for agent_id in phase.agents:
                        if agent_id not in ctx.withheld:
                            continue
                        yield RoomEvent(
                            kind="agent_withheld",
                            run_id=run_id,
                            agent_id=agent_id,
                            reason="upgrade",
                            next_step_agent=(
                                ctx.roster_next_step[0] if ctx.roster_next_step else None
                            ),
                            next_step_days=(
                                ctx.roster_next_step[1] if ctx.roster_next_step else None
                            ),
                        )
                if phase.label != "VERDICT":
                    if phase.parallel:
                        # CR077 Phase 2 — concurrent phase (ANALYSTS only).
                        #
                        # Each agent sees the transcript as of phase START: a
                        # snapshot taken here, before any of the four run. For
                        # ANALYSTS (the first phase) that is empty by design —
                        # the four analysts are blind to EACH OTHER and nothing
                        # else (§Build 4). The four LLM calls run concurrently
                        # against the gateway (asyncio.gather); the measured
                        # 4-stream speedup is the whole point of the lane.
                        #
                        # Deterministic stream order (§Build 3, hard req): whichever
                        # call finishes first, contributions are streamed AND
                        # committed to the transcript in the fixed PHASES order
                        # (fundamentals → market → news → social), never completion
                        # order. Collect-then-emit-in-order below guarantees it; the
                        # guard test injects a gateway that finishes social first and
                        # asserts the emitted order is unchanged.
                        snapshot = list(run.transcript)
                        results = await asyncio.gather(*[
                            _compute_agent_text(
                                agent_id=agent_id,
                                ctx=ctx,
                                profile=profile,
                                formatter=formatter,
                                transcript=snapshot,
                                gateway=gateway,
                                live=live,
                                agent_timeout_s=agent_timeout_s,
                                portfolio_snapshot=ctx.portfolio_snapshot,
                                parallel_phase=True,
                            )
                            for agent_id in phase_agents
                        ])
                        # Emit in fixed order. After all four are committed to
                        # run.transcript, RESEARCHERS onward see every analyst —
                        # only the analysts are blind to each other.
                        for agent_id, (text, geom_sig, envelope) in zip(
                            phase_agents, results
                        ):
                            async for ev in _stream_agent_text(
                                agent_id=agent_id,
                                run_id=run_id,
                                run=run,
                                text=text,
                                geom_sig=geom_sig,
                                char_delay_min=char_delay_min,
                                char_delay_max=char_delay_max,
                                envelope=envelope,
                            ):
                                yield ev
                    else:
                        for agent_id in phase_agents:
                            async for ev in _speak_one_agent(
                                agent_id=agent_id,
                                run_id=run_id,
                                ctx=ctx,
                                profile=profile,
                                formatter=formatter,
                                run=run,
                                gateway=gateway,
                                live=live,
                                char_delay_min=char_delay_min,
                                char_delay_max=char_delay_max,
                                agent_timeout_s=agent_timeout_s,
                                portfolio_snapshot=ctx.portfolio_snapshot,
                            ):
                                yield ev
                else:
                    # CR098 Amendment 2 — Market withheld ⇒ NO_VERDICT, built
                    # in code and NEVER passed through the LLM parser at all
                    # (stronger than a post-hoc contradiction check: there is
                    # no LLM narration in this path for a recommendation to
                    # contradict — see the hand-off for why this deliberately
                    # narrows the spec's "narrow-prompt + post-check" design).
                    # This runs AFTER EXECUTION/RISK (FLAG #2 — kept per the
                    # spec's recommendation; the debate still happens, the
                    # wall lands at the very end).
                    if AgentId.MARKET_ANALYST in ctx.withheld:
                        verdict = _assemble_no_verdict(ctx)
                        pm_text = verdict.reason
                        async for ev in _typewriter(
                            run_id, AgentId.PORTFOLIO_MANAGER, pm_text,
                            char_delay_min, char_delay_max,
                        ):
                            yield ev
                    # Phase 6 — PM: the LLM decides, informed by the full
                    # 11-agent debate; the deterministic safety floor then
                    # vetoes/validates that decision afterward — it never
                    # invents it beforehand. See DEF056.
                    elif live:
                        raw_text = await _stream_pm_response(
                            run_id=run_id, ctx=ctx, profile=profile,
                            formatter=formatter, run=run, gateway=gateway,
                            agent_timeout_s=agent_timeout_s,
                        )
                        if not raw_text:
                            # DEF059: LLM unreachable — fail SAFE to PASS.
                            # The scripted _assemble_verdict APPROVE belongs
                            # to the non-live demo path only; an outage must
                            # never mint a confident buy verdict.
                            verdict = Verdict(
                                action=VerdictAction.PASS,
                                reason=(
                                    "AMI's analyst room lost its model "
                                    "connection before the Portfolio Manager "
                                    "could rule. No trade — reconvene the "
                                    "room in a little while."
                                ),
                                overridden_from_llm=True,
                            )
                            logger.error("room_pm_llm_unavailable", run_id=str(run_id))
                            pm_text = verdict.reason
                        else:
                            pm_text, parsed = _parse_pm_verdict(raw_text, ctx)
                            if parsed is None:
                                # DEF058: the PM's shape slipped past the parser.
                                # One reformat retry re-expresses the same
                                # decision as the JSON schema (nulls for unstated
                                # numbers — never invented) before failing safe.
                                reformatted = await _reformat_pm_response(
                                    raw_text, ctx=ctx, gateway=gateway,
                                    agent_timeout_s=agent_timeout_s,
                                )
                                if reformatted:
                                    narration, reparsed = _parse_pm_verdict(reformatted, ctx)
                                    # DEF067: the reformatter exists only to
                                    # RECOVER an APPROVE the parser missed. Accept
                                    # its output only when it does so. A
                                    # reformatter PASS recovered nothing — never
                                    # let its narration (often a schema-complaint
                                    # like "'MODIFY-AND-APPROVE' is not a valid
                                    # enum value") become the user's verdict;
                                    # fall through to the clean fail-safe below.
                                    if reparsed is not None and reparsed.action == VerdictAction.APPROVE:
                                        parsed = reparsed
                                        pm_text = pm_text or narration
                                        logger.info(
                                            "room_pm_verdict_reformatted",
                                            run_id=str(run_id),
                                        )
                                    elif reparsed is not None and _raw_is_affirmative(raw_text):
                                        logger.warning(
                                            "room_pm_reformat_downgrade_rejected",
                                            run_id=str(run_id),
                                        )
                            if parsed is None:
                                verdict = Verdict(
                                    action=VerdictAction.PASS,
                                    reason=(
                                        "Portfolio Manager did not return a "
                                        "machine-readable verdict; defaulting "
                                        "to no trade for safety."
                                    ),
                                    overridden_from_llm=True,
                                )
                                logger.warning("room_pm_verdict_parse_failed", run_id=str(run_id))
                                if not pm_text:
                                    pm_text = verdict.reason
                            elif parsed.action == VerdictAction.APPROVE:
                                proposed = ProposedTrade(
                                    ticker=ctx.ticker, side=Side.BUY, order_type=OrderType.LIMIT,
                                    quantity=shares_for_size(ctx.portfolio_value, parsed.size_pct, parsed.entry),
                                    limit_price=parsed.entry,
                                )
                                # CR046 M06 / DEF095: flag (never veto) an APPROVE whose
                                # narrated R:R contradicts its own levels, and SURFACE it —
                                # rewrite the PM's verdict narration so the ratio the user
                                # reads is AMI's computed one, not a log nobody sees. The
                                # safety floor still owns vetoes; this only corrects text.
                                _rr_sig = _pm_rr_coherence_signal(
                                    pm_text, parsed.entry, parsed.stop, parsed.target
                                )
                                if _rr_sig is not None:
                                    logger.warning(
                                        "room_pm_rr_incoherent", run_id=str(run_id), **_rr_sig
                                    )
                                    pm_text, _ = _annotate_rr_against_levels(
                                        pm_text, parsed.entry, parsed.stop,
                                        parsed.target, parsed.size_pct,
                                    )
                                verdict = enforce_safety_floor(
                                    llm_verdict=parsed, proposed=proposed,
                                    portfolio_value=ctx.portfolio_value,
                                    current_drawdown_pct=ctx.current_drawdown_pct,
                                    mandate=mandate, halal_universe=ctx.halal_universe,
                                    classification_universe=ctx.classification_universe,
                                    locale_allowed_universe=ctx.locale_allowed_universe,
                                    # CR026: veto a PM APPROVE that breaches the sector cap.
                                    holdings=ctx.sector_holdings,
                                    quotes=ctx.sector_marks,
                                    sector_map=ctx.sector_map,
                                    # CR101-BE2 round 2: same trade-history context
                                    # sim_engine.py supplies at submit()/preview() —
                                    # previously omitted here, so a set post-loss
                                    # cooldown / over-trading brake / open-risk cap
                                    # was silently unenforced on the live PM's own
                                    # APPROVE (round-1 BLOCKER).
                                    last_loss_closed_at=ctx.risk_last_loss_closed_at,
                                    trade_open_timestamps=ctx.risk_trade_open_timestamps,
                                    existing_open_risk_pct=ctx.risk_existing_open_risk_pct,
                                    proposed_stop=parsed.stop,
                                )
                            else:
                                verdict = parsed  # PASS — nothing to check compliance on
                        async for ev in _restream_for_ui(
                            run_id, AgentId.PORTFOLIO_MANAGER, pm_text,
                            char_delay_min, char_delay_max,
                        ):
                            yield ev
                    else:
                        verdict = _assemble_verdict(ctx, profile)
                        mandate_check = (
                            "PASS" if verdict.action == VerdictAction.APPROVE
                            else f"FAIL — {', '.join(verdict.violations)}"
                        )
                        pm_text = _TEMPLATES[AgentId.PORTFOLIO_MANAGER][0].format(
                            **formatter, verdict_action=verdict.action,
                            verdict_rationale=verdict.reason, mandate_check=mandate_check,
                        )
                        async for ev in _typewriter(
                            run_id, AgentId.PORTFOLIO_MANAGER, pm_text,
                            char_delay_min, char_delay_max,
                        ):
                            yield ev

                    run.transcript.append(AgentMessage(
                        agent_id=AgentId.PORTFOLIO_MANAGER,
                        role="agent",
                        content=pm_text,
                        timestamp=datetime.now(timezone.utc),
                    ))
                    yield RoomEvent(
                        kind="agent_done", run_id=run_id,
                        agent_id=AgentId.PORTFOLIO_MANAGER,
                    )
                    # CR098 acceptance #8 — deterministic even when the LLM
                    # says nothing about it; applies to EVERY path above
                    # (APPROVE/PASS/NO_VERDICT/fail-safe), one insertion point.
                    verdict = verdict.model_copy(
                        update={"opinions_not_included": [a.value for a in ctx.withheld]}
                    )
                    # DEF231 — the same insertion point, for the same reason:
                    # BOTH live instances were PASS verdicts, so a check hung
                    # off the APPROVE branch (where the R:R coherence check
                    # lives) would have caught neither. The narration has
                    # already streamed by here; `reason` is the string CR106
                    # renders as the justification and is what both instances
                    # landed in.
                    _reason, _dir_signals = _annotate_direction_against_price(
                        verdict.reason,
                        _reference_close(profile),
                        _structured_levels(profile, verdict),
                    )
                    if _dir_signals:
                        logger.warning(
                            "room_pm_direction_incoherent",
                            run_id=str(run_id),
                            ticker=ctx.ticker,
                            action=str(verdict.action),
                            count=len(_dir_signals),
                            **_dir_signals[0],
                        )
                        verdict = verdict.model_copy(update={"reason": _reason})
                    run.verdict = verdict
                    yield RoomEvent(kind="verdict", run_id=run_id, verdict=verdict)
                await asyncio.sleep(_PHASE_GAP_S)

            run.status = RoomStatus.COMPLETED
            run.finished_at = datetime.now(timezone.utc)
            run.duration_ms = int(
                (run.finished_at - (run.started_at or run.finished_at)).total_seconds() * 1000
            )
            _persist_run(run)
            logger.info(
                "room_completed",
                run_id=str(run_id),
                ticker=ticker,
                action=str(run.verdict.action if run.verdict else "n/a"),
            )
        except (asyncio.CancelledError, GeneratorExit):
            # Client disconnect: the SSE consumer's `async for ev in run_iter`
            # tears the iterator down via aclose(), sending GeneratorExit here.
            # The previous code let it propagate uncaught — the generator died
            # before reaching the bottom-of-function `_persist_run`, leaving
            # the DB row at status=running with an empty transcript. The
            # detached drain task in room.py would then finalise a journal
            # entry from that stale snapshot. Catch here, persist whatever
            # transcript was collected, then re-raise.
            run.status = RoomStatus.CANCELLED
            run.error_message = "client disconnected mid-run"
            run.finished_at = datetime.now(timezone.utc)
            run.duration_ms = int(
                (run.finished_at - (run.started_at or run.finished_at)).total_seconds() * 1000
            )
            _persist_run(run)
            logger.info(
                "room_cancelled",
                run_id=str(run_id),
                ticker=ticker,
                agents_completed=len(run.transcript),
            )
            raise
        except Exception as e:
            run.status = RoomStatus.FAILED
            run.error_message = str(e)[:500]
            _persist_run(run)
            # CR039: the run was billed at start_run. It failed on our side, so
            # give the credits back — otherwise a bad deploy silently eats a
            # Floor Pass user's entire monthly allowance in one tap. Refund is
            # best-effort: a failure here must not mask the original error.
            try:
                refund(user_id, run.credit_cost, reason=f"room_failed:{run_id}")
            except Exception as refund_exc:
                logger.error(
                    "room_refund_failed",
                    run_id=str(run_id),
                    credits=run.credit_cost,
                    error=str(refund_exc)[:200],
                )
            logger.error("room_failed", run_id=str(run_id), error=str(e))
            yield RoomEvent(kind="error", run_id=run_id, text=str(e)[:300])

    def clear(self) -> None:
        from sqlalchemy import delete as _delete
        with get_session() as s:
            s.execute(_delete(RoomRunRow))


async def _collect_agent_stream(gen) -> list[str]:
    """Drain an async-generator into a list of string chunks."""
    buf: list[str] = []
    async for chunk in gen:
        buf.append(chunk)
    return buf


async def _typewriter(
    run_id: UUID,
    agent_id: AgentId,
    text: str,
    delay_min: float,
    delay_max: float,
) -> AsyncIterator[RoomEvent]:
    """Yield character-by-character agent_token events."""
    for ch in text:
        yield RoomEvent(
            kind="agent_token",
            run_id=run_id,
            agent_id=agent_id,
            text=ch,
        )
        await asyncio.sleep(random.uniform(delay_min, delay_max))


async def _compute_agent_text(
    *,
    agent_id: AgentId,
    ctx: _RoomContext,
    profile: dict[str, Any],
    formatter: dict[str, Any],
    transcript: list[AgentMessage],
    gateway: LLMGateway,
    live: bool,
    agent_timeout_s: float = _AGENT_LLM_TIMEOUT_S,
    portfolio_snapshot: str | None = None,
    parallel_phase: bool = False,
) -> tuple[str, dict[str, Any] | None, "_StanceEnvelope"]:
    """Produce one agent's final contribution text (LLM when live, scripted
    otherwise) plus its DEF095 geometry-verification signal — WITHOUT streaming
    it or touching `run.transcript`.

    This is the awaitable a concurrent phase (CR077 ANALYSTS) gathers; the
    sequential path (`_speak_one_agent`) awaits it inline. The prompt is built
    from the `transcript` snapshot the CALLER passes — so four concurrent
    analysts all read the phase-start transcript, never each other's
    half-committed turns — and `parallel_phase` rescopes the "build on the
    transcript" line for an agent that has no transcript to build on
    (room_prompts.py).

    The live path buffers the full LLM response (with a per-agent timeout); if
    the upstream model hangs past `agent_timeout_s` (or errors, or returns
    empty) the agent falls back to its scripted template so the run can still
    finish. Returns `(text, geom_signal)`; `geom_signal` is a DEF095 telemetry
    payload when the agent narrated a ratio its own levels don't support, else
    None. The caller logs it (so run_id stays with the streamer).
    """
    # BL11 (AT:R33): effective_plan downgrades expired trials.
    plan = effective_plan_for_user(ctx.user_id)
    tier = pick_tier(plan, agent_id)

    text: str
    # CR106 B2: every path that is NOT a parsed live turn leaves this empty, so
    # a scripted fallback, a timeout and an LLM failure all reach the comb's
    # gutter rather than borrowing a stance from somewhere.
    envelope = _StanceEnvelope()
    if live:
        # Pass ctx.user_id so build_agent_prompt picks up the user's
        # active Brief overlay (was user_id=None — AT:R27 bugfix).
        system_prompt, messages = build_room_messages(
            agent_id=agent_id,
            mandate=ctx.mandate,
            user_id=ctx.user_id,
            ticker=ctx.ticker,
            profile=profile,
            transcript=transcript,
            portfolio_snapshot=portfolio_snapshot,
            plan=plan,
            trade_proposal={
                "size_pct": ctx.trader_size_pct,
                "entry": ctx.trader_entry,
                "stop": ctx.trader_stop,
            },
            # CR069: the same universe enforce_safety_floor decides against, so the
            # narration and the deterministic verdict cannot contradict each other.
            halal_universe=ctx.halal_universe,
            classification_universe=ctx.classification_universe,
            # CR077 §Build 5: a concurrent analyst has no transcript to build on —
            # rescope the "do not repeat" line so it sharpens the own-domain lens
            # instead of pointing at an empty transcript.
            parallel_phase=parallel_phase,
            # CR026: the PM sees the real sector allocation it gatekeeps against.
            sector_weights=ctx.sector_weights,
            # DEF241: the size THIS debator's role argues for, so it is handed the
            # drawdown contribution of its own position instead of deriving it.
            # `risk_debator_sizes` already computed these once per run for the
            # scripted templates; until now they never reached an LLM prompt, so
            # every debator was told to argue a size it was never given and then
            # asked to quantify the result.
            agent_size_pct=(
                getattr(ctx, _DEBATOR_SIZE_ATTR[agent_id])
                if agent_id in _DEBATOR_SIZE_ATTR else None
            ),
            # CR153 B ≡ CR154 B ≡ CR155 C ≡ CR156 C (deduped per CR156's rule) —
            # the risk budget's CONSUMPTION, not just its limits. Threaded from
            # ctx so the prompt and the safety floor read the same values; the
            # CONTEXT_NOT_SUPPLIED sentinel survives the trip, because "could not
            # compute" and "zero" must not render identically (CR040).
            current_drawdown_pct=ctx.current_drawdown_pct,
            existing_open_risk_pct=_prompt_open_risk(ctx.risk_existing_open_risk_pct),
            last_loss_closed_at=ctx.risk_last_loss_closed_at,
            trade_open_timestamps=ctx.risk_trade_open_timestamps,
        )
        # DEF125: the provider reports its terminal stop reason here.
        stream_meta: dict[str, Any] = {}
        try:
            chunks = await asyncio.wait_for(
                _collect_agent_stream(gateway.stream_chat(
                    system_prompt=system_prompt,
                    messages=messages,
                    model_tier=tier,  # type: ignore[arg-type]
                    locale=ctx.mandate.locale,
                    max_tokens=max_tokens_for(agent_id),
                    audit_user_id=ctx.user_id,
                    audit_agent_id=agent_id.value,
                    audit_flow="room",
                    meta=stream_meta,
                )),
                timeout=agent_timeout_s,
            )
            text = "".join(chunks).strip() or _scripted_for(agent_id, formatter)
            # CR106 B2: strip the stance envelope FIRST. It must come off before
            # the `[AMI …]` marks below — which would otherwise sit between the
            # prose and a trailing envelope and break its end-anchor — and before
            # the transcript commit, so no downstream agent ever reads a machine
            # channel as if it were another agent's argument (DEF095).
            text, envelope = parse_stance_envelope(text)
            # DEF147: with the envelope leading the turn, a generation that
            # stopped right after it leaves no prose at all. Same destination as
            # an empty stream two lines up, rather than a blank contribution.
            # The stance itself parsed and is kept — it is what the agent said.
            text = text or _scripted_for(agent_id, formatter)
            text = _mark_if_truncated(text, agent_id=agent_id, meta=stream_meta)
        except asyncio.TimeoutError:
            logger.warning(
                "room_agent_timeout",
                agent_id=agent_id.value,
                timeout_s=agent_timeout_s,
            )
            text = _scripted_for(agent_id, formatter)
        except Exception as exc:
            logger.warning(
                "room_agent_llm_failed",
                agent_id=agent_id.value,
                error=str(exc)[:200],
            )
            text = _scripted_for(agent_id, formatter)
    else:
        text = _scripted_for(agent_id, formatter)

    # DEF095: before this contribution is streamed or enters the transcript the rest
    # of the Room reasons from, AMI recomputes every derived ratio from the agent's
    # OWN stated levels and rewrites the text so both the user watching and every
    # downstream agent read AMI's figure, not the narration. Only a full level triple
    # triggers it; all other agents pass through untouched. Flag-only — never a veto
    # (DEF059 — the safety floor stays the sole vetoer).
    # DEF237: the run's own close is what makes a mis-parsed level detectable.
    # `_reference_close` is gated on `field_state["technicals"] == LIVE`, so a
    # run with no recorded technicals provenance passes None and the geometry
    # check degrades to its pre-DEF237 behaviour rather than comparing against a
    # number of unknown origin (CR104).
    text, geom_sig = _verify_and_annotate_geometry(
        text,
        size_pct=ctx.trader_size_pct,
        reference_close=_reference_close(ctx.profile),
    )
    return text, geom_sig, envelope


async def _stream_agent_text(
    *,
    agent_id: AgentId,
    run_id: UUID,
    run: RoomRun,
    text: str,
    geom_sig: dict[str, Any] | None,
    char_delay_min: float,
    char_delay_max: float,
    envelope: "_StanceEnvelope | None" = None,
) -> AsyncIterator[RoomEvent]:
    """Stream an already-computed contribution: typewriter tokens, commit it to
    `run.transcript`, then emit `agent_done`.

    Splitting this from `_compute_agent_text` is what lets a concurrent phase
    gather the slow LLM calls and STILL emit every agent's tokens (and commit
    them to the transcript) in a fixed, deterministic order regardless of which
    call finished first (CR077 §Build 3).
    """
    if geom_sig is not None:
        logger.warning(
            "room_agent_rr_incoherent",
            run_id=str(run_id),
            agent_id=agent_id.value,
            **geom_sig,
        )

    async for ev in _typewriter(run_id, agent_id, text, char_delay_min, char_delay_max):
        yield ev

    env = envelope or _StanceEnvelope()
    run.transcript.append(AgentMessage(
        agent_id=agent_id,
        role="agent",
        content=text,
        timestamp=datetime.now(timezone.utc),
        # CR106 B2 — carried on the transcript entry, so the Journal replay
        # renders the same comb the live Room did, from the frozen snapshot.
        stance=env.stance,  # type: ignore[arg-type]
        conviction=env.conviction,  # type: ignore[arg-type]
        headline=env.headline,
    ))
    _checkpoint_run(run)  # incremental snapshot — narrows data-loss window to ≤1 agent
    yield RoomEvent(
        kind="agent_done",
        run_id=run_id,
        agent_id=agent_id,
        stance=env.stance,
        conviction=env.conviction,
        headline=env.headline,
    )


async def _speak_one_agent(
    *,
    agent_id: AgentId,
    run_id: UUID,
    ctx: _RoomContext,
    profile: dict[str, Any],
    formatter: dict[str, Any],
    run: RoomRun,
    gateway: LLMGateway,
    live: bool,
    char_delay_min: float,
    char_delay_max: float,
    agent_timeout_s: float = _AGENT_LLM_TIMEOUT_S,
    portfolio_snapshot: str | None = None,
) -> AsyncIterator[RoomEvent]:
    """Sequential-phase path: compute one agent's text (reading the LIVE
    transcript, so it builds on everyone before it) then stream it.

    Every phase except the concurrent ANALYSTS phase runs through here, one
    agent fully awaited before the next — a debate where each turn answers the
    last. The ANALYSTS phase bypasses this and drives `_compute_agent_text` /
    `_stream_agent_text` directly so its four calls can be gathered.
    """
    text, geom_sig, envelope = await _compute_agent_text(
        agent_id=agent_id,
        ctx=ctx,
        profile=profile,
        formatter=formatter,
        transcript=run.transcript,
        gateway=gateway,
        live=live,
        agent_timeout_s=agent_timeout_s,
        portfolio_snapshot=portfolio_snapshot,
        parallel_phase=False,
    )
    async for ev in _stream_agent_text(
        agent_id=agent_id,
        run_id=run_id,
        run=run,
        text=text,
        geom_sig=geom_sig,
        char_delay_min=char_delay_min,
        char_delay_max=char_delay_max,
        envelope=envelope,
    ):
        yield ev


async def _stream_pm_response(
    *,
    run_id: UUID,
    ctx: _RoomContext,
    profile: dict[str, Any],
    formatter: dict[str, Any],
    run: RoomRun,
    gateway: LLMGateway,
    agent_timeout_s: float = _AGENT_LLM_TIMEOUT_S,
) -> str:
    """Buffer the PM's raw LLM response and return it verbatim (DEF056).

    Returns "" on timeout/exception — the caller fails SAFE to a PASS
    verdict with an honest outage reason in that case (DEF059; the scripted
    `_assemble_verdict` APPROVE is reserved for the non-live demo path). A
    non-empty return still needs parsing by `_parse_pm_verdict` — this
    function makes no attempt to interpret the response, it only fetches it.
    """
    # BL11 (AT:R33): effective_plan downgrades expired trials.
    plan = effective_plan_for_user(ctx.user_id)
    tier = pick_tier(plan, AgentId.PORTFOLIO_MANAGER)
    # Pass ctx.user_id so build_agent_prompt picks up the user's active
    # Brief overlay for the PM (was user_id=None — AT:R27 bugfix). Note:
    # PM safety_floor still appends LAST regardless of overlay content.
    system_prompt, messages = build_room_messages(
        agent_id=AgentId.PORTFOLIO_MANAGER,
        mandate=ctx.mandate,
        user_id=ctx.user_id,
        ticker=ctx.ticker,
        profile=profile,
        transcript=run.transcript,
        portfolio_snapshot=ctx.portfolio_snapshot,
        plan=plan,
        trade_proposal={
            "size_pct": ctx.trader_size_pct,
            "entry": ctx.trader_entry,
            "stop": ctx.trader_stop,
        },
        # CR069 — see the sibling call site: the PM narrates the same sourced verdict
        # its own safety floor enforces.
        halal_universe=ctx.halal_universe,
        classification_universe=ctx.classification_universe,
        # DEF238: this argument was missing for the entire life of CR026, and the
        # feature was PM-only, so it never worked ONCE in production. The line is
        # rendered only for the PORTFOLIO_MANAGER (`room_prompts.py`), and this is
        # the only call site that builds a live PM prompt — the sibling prose call
        # site passes it, where the PM-only gate makes it a no-op. So
        # `_format_sector_allocation(None)` took its empty branch and told the
        # concentration-reasoning agent "no open positions yet (0% in every
        # sector)" in 18 of 18 epoch prompts, 8 of which listed real holdings a
        # few lines above (up to `GME ×500`, 95.8% of portfolio). Not a silent
        # gap — a confident false statement, the CR040 class after DEF038/DEF063.
        # The floor was never affected: its sector cap reads
        # `ctx.sector_holdings/marks/map` directly, not this string.
        sector_weights=ctx.sector_weights,
        # CR153 B ≡ CR154 B ≡ CR155 C ≡ CR156 C (deduped per CR156's rule) —
        # the risk budget's CONSUMPTION, not just its limits. Threaded from
        # ctx so the prompt and the safety floor read the same values; the
        # CONTEXT_NOT_SUPPLIED sentinel survives the trip, because "could not
        # compute" and "zero" must not render identically (CR040).
        current_drawdown_pct=ctx.current_drawdown_pct,
        existing_open_risk_pct=_prompt_open_risk(ctx.risk_existing_open_risk_pct),
        last_loss_closed_at=ctx.risk_last_loss_closed_at,
        trade_open_timestamps=ctx.risk_trade_open_timestamps,
    )
    # DEF125 item 4: the PM's own budget was a separate hard-coded 600, one
    # line from the flat 400 — and DEF058 (verdict fails to parse in ~22% of
    # runs) suspected exactly that cap clipping the JSON's closing brace. Route
    # it through the same table so there is one place the Room's budgets live.
    pm_meta: dict[str, Any] = {}
    try:
        chunks = await asyncio.wait_for(
            _collect_agent_stream(gateway.stream_chat(
                system_prompt=system_prompt,
                messages=messages,
                model_tier=tier,  # type: ignore[arg-type]
                locale=ctx.mandate.locale,
                max_tokens=max_tokens_for(AgentId.PORTFOLIO_MANAGER),
                audit_user_id=ctx.user_id,
                audit_agent_id=AgentId.PORTFOLIO_MANAGER.value,
                audit_flow="room_pm",
                meta=pm_meta,
            )),
            timeout=agent_timeout_s,
        )
        # No `[AMI …]` mark here: this text is not a transcript turn, it is the
        # raw JSON `_parse_pm_verdict` reads. Appending prose to it would break
        # the parse this budget exists to protect — the warning is the whole
        # disclosure, and a truncated envelope still fails safe to PASS.
        if pm_meta.get("finish_reason") == "length":
            logger.warning(
                "room_pm_truncated",
                max_tokens=max_tokens_for(AgentId.PORTFOLIO_MANAGER),
            )
        return "".join(chunks).strip()
    except asyncio.TimeoutError:
        logger.warning("room_pm_timeout", timeout_s=agent_timeout_s)
        return ""
    except Exception as exc:
        logger.warning("room_pm_llm_failed", error=str(exc)[:200])
        return ""


# DEF058/DEF067: when the PM's reply slips past `_parse_pm_verdict` (genuinely
# unparseable prose, or malformed JSON), one cheap follow-up call asks the model
# to re-express the same decision as the parseable schema before failing safe to
# PASS. Post-DEF067 the common out-of-enum case ("MODIFY-AND-APPROVE" with a
# valid size) is handled by the parser directly, so this rarely fires. It only
# ever RECOVERS an APPROVE — a reformatter PASS is discarded by the caller (see
# the DEF067 note at the call site). Faithfulness rules: never change the
# decision, never invent numbers (null when unstated — `_parse_pm_verdict` then
# refuses APPROVE-without-size on its own).
_PM_REFORMAT_SYSTEM = (
    "You are a strict formatter for AMI's analyst room. The user message is a "
    "Portfolio Manager's final verdict. It may be prose, or JSON that uses an "
    "action value outside the allowed set (e.g. 'MODIFY-AND-APPROVE'). "
    "Re-express it as ONLY a single JSON object, no prose outside it, shaped "
    "exactly like:\n"
    '{"action": "APPROVE" | "PASS",\n'
    ' "size_pct": <number or null>,\n'
    ' "entry": <number or null>,\n'
    ' "stop": <number or null>,\n'
    ' "target": <number or null>,\n'
    ' "horizon_days": <integer or null>,\n'
    # DEF236 — "3-4 sentences, faithful summary" until 2026-08-11, which stopped
    # being faithful the moment the PM's own contract asked for a decision
    # sentence plus up to 6 bullets: a summary at the old length silently
    # RESHAPES a user-visible narration on the one path the user cannot see.
    # This is a formatter, so the rationale is carried, not re-authored.
    ' "narration": "<the rationale, carried across verbatim — do not shorten, '
    'summarise or re-shape it>"}\n'
    "There are exactly two action values: APPROVE and PASS. A modification is "
    "an approval — if the verdict enters or approves a position (including "
    "'MODIFY-AND-APPROVE', 'approve with a smaller size', or any affirmative "
    "wording), action is APPROVE and you carry its size/entry/stop across "
    "unchanged. If it waits, passes, rejects, or reaches no decision, action "
    "is PASS. Preserve the decision faithfully: never flip an approval to a "
    "pass, never change sizes or price levels, and if a number is not stated "
    "use null — never invent one. Do NOT comment on the input's format or "
    "validity; only translate it. Begin your response with '{'."
)


async def _reformat_pm_response(
    raw_text: str,
    *,
    ctx: _RoomContext,
    gateway: LLMGateway,
    agent_timeout_s: float = _AGENT_LLM_TIMEOUT_S,
) -> str:
    """One-shot DEF058 retry: ask the model to re-express the PM's prose
    verdict as the parseable JSON schema. Returns "" on timeout/exception —
    the caller then falls through to the fail-safe PASS."""
    plan = effective_plan_for_user(ctx.user_id)
    tier = pick_tier(plan, AgentId.PORTFOLIO_MANAGER)
    # DEF125 item 4: the reformatter re-emits the SAME JSON envelope the PM was
    # asked for, so a budget below the PM's guarantees the retry is clipped
    # whenever the original was — the recovery path failing for the very reason
    # it was invoked. It gets the PM's budget.
    reformat_meta: dict[str, Any] = {}
    try:
        chunks = await asyncio.wait_for(
            _collect_agent_stream(gateway.stream_chat(
                system_prompt=_PM_REFORMAT_SYSTEM,
                messages=[ChatMessage(role="user", content=raw_text)],
                model_tier=tier,  # type: ignore[arg-type]
                locale=ctx.mandate.locale,
                max_tokens=max_tokens_for(AgentId.PORTFOLIO_MANAGER),
                audit_user_id=ctx.user_id,
                audit_agent_id=AgentId.PORTFOLIO_MANAGER.value,
                audit_flow="room_pm_reformat",
                meta=reformat_meta,
            )),
            timeout=agent_timeout_s,
        )
        if reformat_meta.get("finish_reason") == "length":
            logger.warning(
                "room_pm_reformat_truncated",
                max_tokens=max_tokens_for(AgentId.PORTFOLIO_MANAGER),
            )
        return "".join(chunks).strip()
    except asyncio.TimeoutError:
        logger.warning("room_pm_reformat_timeout", timeout_s=agent_timeout_s)
        return ""
    except Exception as exc:
        logger.warning("room_pm_reformat_failed", error=str(exc)[:200])
        return ""


async def _restream_for_ui(
    run_id: UUID,
    agent_id: AgentId,
    text: str,
    delay_min: float,
    delay_max: float,
) -> AsyncIterator[RoomEvent]:
    """Alias for `_typewriter` used when restreaming buffered LLM text.

    Kept separate so the call sites read clearly — "this text was already
    buffered from the LLM; replay it at typewriter cadence for the UI".
    """
    async for ev in _typewriter(run_id, agent_id, text, delay_min, delay_max):
        yield ev


def _scripted_for(agent_id: AgentId, formatter: dict[str, Any]) -> str:
    """Render the legacy scripted text for an agent. Used as fallback when
    the LLM gateway has no real provider or when a live call fails.
    """
    tpl = _TEMPLATES[agent_id][0]
    # Some PM-only keys aren't in the formatter unless we pass them; for
    # the non-PM agents the template only references shared keys.
    return tpl.format(**formatter)


# ── CR077 second guard: prefix-cache observability ─────────────────────────
#
# Prefix caching is the free half of the Room-latency story (CR077 §Guard):
# concurrency (Phase 2 above) is the lever, but the KV-cache prefix reuse the
# GPU already does silently underpins the concurrency headroom. It is enabled
# on the serving host today — but "today" is the trap: nobody would notice if a
# serve-arg change on the (separately-owned) LLM host switched it off, exactly
# how it sat at 0% on Room traffic for months without anyone knowing. So at
# process startup we probe the host's /metrics once and log it LOUDLY — an
# ERROR if prefix caching is off, an info line with the measured hit rate if on
# (CR040 "degrade loudly": an invisible regression is the failure mode). The LLM
# host is not touched; this only reads its metrics.

_PREFIX_CACHE_STATUS_LOGGED = False


def parse_prefix_cache_metrics(metrics_text: str) -> dict[str, Any]:
    """Pull prefix-cache state out of a vLLM Prometheus /metrics dump.

    Pure + host-independent so the guard can unit-test it. Returns
    `{"enabled": bool | None, "hits": float | None, "queries": float | None,
      "hit_rate": float | None}` — `enabled` is None when the metrics carry no
    `cache_config_info` line at all (an unknown/old vLLM), which the caller
    treats as "cannot confirm", distinct from a confirmed-off False.
    """
    enabled: bool | None = None
    m = re.search(r'cache_config_info\{[^}]*enable_prefix_caching="(\w+)"', metrics_text)
    if m:
        enabled = m.group(1).strip().lower() == "true"

    def _sum_metric(name: str) -> float | None:
        total = 0.0
        found = False
        for line in metrics_text.splitlines():
            s = line.strip()
            if s.startswith("#") or name not in s:
                continue
            # A Prometheus sample line: `<name>{labels} <value>` or `<name> <value>`.
            mm = re.match(rf'{re.escape(name)}(?:\{{[^}}]*\}})?\s+([-+0-9.eE]+)$', s)
            if mm:
                try:
                    total += float(mm.group(1))
                    found = True
                except ValueError:
                    continue
        return total if found else None

    # vLLM has renamed these across versions (gpu_prefix_cache_* vs
    # prefix_cache_*); accept either, hits first non-None wins.
    hits = _sum_metric("vllm:prefix_cache_hits_total")
    if hits is None:
        hits = _sum_metric("vllm:gpu_prefix_cache_hits_total")
    queries = _sum_metric("vllm:prefix_cache_queries_total")
    if queries is None:
        queries = _sum_metric("vllm:gpu_prefix_cache_queries_total")

    hit_rate = (hits / queries) if (hits is not None and queries) else None
    return {"enabled": enabled, "hits": hits, "queries": queries, "hit_rate": hit_rate}


def log_prefix_cache_status() -> None:
    """Probe the vLLM host's /metrics once and log prefix-cache state loudly.

    Best-effort and guarded: no-ops when no vLLM host is configured (unit tests,
    mock provider) and swallows any network/parse failure into a single warning —
    an observability probe must never break a Room run. Fires once per process."""
    global _PREFIX_CACHE_STATUS_LOGGED
    if _PREFIX_CACHE_STATUS_LOGGED:
        return
    base = settings.vllm_base_url
    if not base:
        return  # no real LLM host (mock/anthropic) — nothing to probe
    _PREFIX_CACHE_STATUS_LOGGED = True
    try:
        import httpx

        url = base.rstrip("/").removesuffix("/v1") + "/metrics"
        resp = httpx.get(url, timeout=5.0)
        resp.raise_for_status()
        stats = parse_prefix_cache_metrics(resp.text)
        if stats["enabled"] is False:
            logger.error(
                "room_prefix_cache_DISABLED",
                url=url,
                detail="vLLM reports enable_prefix_caching=False — Room prefill "
                "reuse is OFF; CR077 assumed it on. Ask the LLM-host team.",
            )
        elif stats["enabled"] is None:
            logger.warning("room_prefix_cache_unconfirmed", url=url)
        else:
            logger.info(
                "room_prefix_cache_enabled",
                url=url,
                hit_rate=(round(stats["hit_rate"], 4) if stats["hit_rate"] is not None else None),
                hits=stats["hits"],
                queries=stats["queries"],
            )
    except Exception as exc:  # noqa: BLE001 — probe is best-effort, never fatal
        logger.warning("room_prefix_cache_probe_failed", error=str(exc)[:200])


_runner: RoomRunner | None = None


def get_room_runner() -> RoomRunner:
    global _runner
    if _runner is None:
        _runner = RoomRunner()
        # CR077 second guard: emit the prefix-cache state once at first wiring.
        log_prefix_cache_status()
    return _runner
