"""Convene the Room — the multi-agent debate orchestrator.

A Room run is a 6-phase, 12-agent sequence that produces a single Verdict
on a ticker. The phases:

  Phase 1 — 4 Analysts run in parallel.
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
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select

from app.agents.safety_floor import check_mandate_compliance, enforce_safety_floor
from app.core.config import settings
from app.core.logging import logger
from app.db import get_session, init_schema
from app.db.models import RoomRunRow
from app.schemas import AgentId, AgentMessage, Mandate
from app.schemas.journal import EntryType, JournalEntryCreate, Outcome
from app.schemas.mandate import Plan
from app.schemas.room import RoomRun, RoomStatus, Verdict, VerdictAction
from app.schemas.trade import OrderType, ProposedTrade, Side
from app.services.fundamentals import fetch_live_fundamentals
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
    format_mention_trend,
    format_pattern,
    format_sentiment_score,
    format_sentiment_tone,
    resolve_social_feed,
)
from app.services.llm_gateway import ChatMessage, LLMGateway, get_llm_gateway
from app.services.llm_json import extract_json_object
from app.services.room_prompts import build_room_messages
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
from app.trading_math.sizing import risk_debator_sizes, risk_tier_cap
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
        "{ticker} trades at a trailing P/E of {pe}x. "
        "TTM revenue growth {rev_growth}%; profit margin {profit_margin}%. "
        "Balance sheet: {net_cash_phrase}. "
        "On the fundamentals alone, the name is {valuation_tone}.",
    ],
    AgentId.MARKET_ANALYST: [
        # Neutral on the 20/50-day relationship's direction ("{trend}" is
        # "trading" or "consolidating", not "up"/"down") — same discipline as
        # SOCIAL_MEDIA_ANALYST above. Support/breakout described as a recent
        # range, not tied to a specific MA window this template doesn't
        # actually compute (DEF052, AT:R58 — was previously "the 200-day",
        # a claim the real computation never backed).
        "Daily chart shows {ticker} {trend} around its 20/50-day moving "
        "averages, with recent support around ${support}. RSI({rsi}) — "
        "{rsi_tone}. 52-week range ${low}–${high}, breakout level "
        "sits at ${breakout}. Volume {volume_tone}.",
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


def _profile_for_ticker(
    ticker: str,
    *,
    news_feed: NewsFeed | None = None,
    social_feed: SocialFeed | None = None,
    withheld: frozenset[AgentId] = frozenset(),
) -> dict[str, Any]:
    """Ticker-flavoured profile for the Room.

    Builds a deterministic synthetic baseline (so tests stay reproducible
    and Yahoo outages don't break a run), then — when the backend has
    real market data enabled — overlays live yfinance fundamentals on top.
    Narrative fields (catalysts, sentiment, debate framing) remain
    synthetic; numeric fields the LLM would otherwise hallucinate from
    training memory (P/E, growth, FCF, range) become live when possible.

    The returned profile carries a `data_source` field so the prompt
    layer can be honest with the LLM about what's live vs scaffolded.
    """
    # zlib.crc32, not the builtin hash() — str hashing is randomized per
    # process (PYTHONHASHSEED) unless pinned, so hash() broke the
    # "deterministic synthetic baseline" this docstring promises: same
    # ticker, different process, different synthetic profile (DEF057).
    rng = random.Random(zlib.crc32(ticker.upper().encode()))
    base_price = 50 + rng.uniform(0, 400)
    pe = rng.uniform(12, 55)
    rev_growth = rng.randint(2, 40)
    profit_margin = rng.randint(8, 35)
    profile: dict[str, Any] = {
        "ticker": ticker.upper(),
        "base_price": round(base_price, 2),
        "pe": f"{pe:.1f}",
        "rev_growth": rev_growth,
        "profit_margin": profit_margin,
        "net_cash": rng.randint(-5_000, 80_000),
        "trend": "trading" if rng.random() > 0.5 else "consolidating",
        "support": round(base_price * 0.9, 2),
        "rsi": rng.randint(35, 75),
        "rsi_tone": "neither overbought nor oversold",
        "low": round(base_price * 0.95, 2),
        "high": round(base_price * 1.05, 2),
        "breakout": round(base_price * 1.03, 2),
        "volume_tone": "above 20-day average — real participation"
            if rng.random() > 0.5 else "in-line with 20-day average",
        "catalyst": "Q3 earnings (beat by ~4%)",
        "forward_catalyst": _forward_catalyst_text(),
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
        "data_source": "synthetic",
    }

    # Overlay real fundamentals when configured + reachable.
    if settings.use_real_market_data:
        live = fetch_live_fundamentals(ticker)
        if live:
            profile.update(live)
            profile["data_source"] = "yfinance_live"

        # Overlay real technicals (DEF052, AT:R58) — RSI/trend/volume/
        # support-breakout computed from real yfinance OHLCV, replacing the
        # rng-based synthetic block. MACD/moving-average-crossover/Bollinger
        # Bands are deliberately not computed (see technicals.py) — the
        # prompt no longer claims them.
        #
        # CR098 — Market withheld (roster pull-back): skip the fetch (bank the
        # yfinance OHLCV pull, scope item 4) and leave the honest synthetic
        # scaffolding in place; _format_profile (Amendment 1) reads
        # technicals_state to strip the fact-sheet lines instead of rendering
        # a fabricated RSI/range/volume.
        if AgentId.MARKET_ANALYST in withheld:
            profile["technicals_state"] = LiveDataState.WITHHELD_TENURE.value
        else:
            technicals = compute_technicals(ticker)
            if technicals:
                profile["rsi"] = technicals.rsi
                profile["rsi_tone"] = technicals.rsi_tone
                profile["trend"] = technicals.trend
                profile["volume_tone"] = technicals.volume_tone
                profile["support"] = technicals.support
                profile["breakout"] = technicals.breakout
                profile["technicals_source"] = "live"

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
            # Real forward consensus EPS for the upcoming report (DEF053,
            # AT:R58) — was already fetched here, just never surfaced. A
            # genuine "forward guidance" data point, distinct from the
            # backward-looking rev_growth/profit_margin fields above.
            if earnings.eps_estimate is not None:
                profile["next_earnings_eps_estimate"] = earnings.eps_estimate

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
        profile["news_source"] = "live"
    profile["news_state"] = nf.state.value

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
        profile["social_source"] = "live"
    profile["social_state"] = sf.state.value

    # Derive narrative strings from whatever numbers ended up in the
    # profile (real or synthetic) so the prose is consistent with the data.
    pe_val = float(profile["pe"]) if isinstance(profile["pe"], str) else float(profile["pe"])
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
    return profile


# ── Verdict assembly ──────────────────────────────────────────────────────


def _risk_tier_size_ceiling(risk_score: int) -> float:
    """Max position size (%) for a mandate's risk tier — a ceiling the PM's
    LLM-decided size gets clamped to (DEF056), and the default cosmetic size
    for the pre-debate aggressive/conservative/neutral display values.

    Canonical values live in app.trading_math.sizing (CR046 M03) — the same
    table the Trader's prompt narration now reads, so shown == enforced."""
    return risk_tier_cap(risk_score)


# ── Portfolio holdings block (CR055) ──────────────────────────────────────

_SIM_PORTFOLIO_HEADER = (
    "─── YOUR SIMULATED PORTFOLIO (AMI's portfolio of record — simulation-only) ───"
)


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
        for t in open_trades:
            sym = t.ticker.upper()
            row = agg.setdefault(sym, [0.0, 0.0])  # [qty, cost_basis]
            row[0] += t.quantity
            row[1] += t.quantity * t.entry_price
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
                f"unrealised {unrealised:+,.2f})"
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
        holdings = list(sim.ensure_portfolio(user_id).holdings)
        marks = sim.current_marks([h.ticker for h in holdings]) if holdings else {}
        smap = default_sector_map()
        weights = allocate_by_sector(holdings, marks, sector_of=smap.sector)
        return holdings, marks, smap, weights
    except Exception as exc:  # noqa: BLE001 — degrade, never sink the run
        logger.warning("room_sector_context_failed", user_id=str(user_id), error=str(exc)[:200])
        return [], {}, None, {}


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


def _parse_pm_verdict(text: str, ctx: _RoomContext) -> tuple[str, Verdict | None]:
    """Extract the PM's display narration + intended decision from its raw
    LLM response (DEF056). Returns (display_text, llm_verdict); llm_verdict
    is None when the response couldn't be trusted as a real decision — the
    caller fails safe to PASS in that case rather than fabricating APPROVE.
    """
    parsed = extract_json_object(text)
    if parsed is None:
        return text.strip(), None

    narration = str(parsed.get("narration") or "").strip()
    action = _normalize_pm_action(parsed.get("action"))
    if action is None:
        return narration or text.strip(), None

    if action == "PASS":
        return narration, Verdict(
            action=VerdictAction.PASS,
            reason=narration or "No trade — debate did not support entry.",
        )

    size_pct = _safe_float(parsed.get("size_pct"))
    if size_pct is None:
        # No size the PM is willing to stand behind — don't invent one.
        return narration or text.strip(), None

    entry = _safe_float(parsed.get("entry")) or ctx.trader_entry
    # Explicit None-checks (not `or`): a real level is used as-is; only a genuinely
    # missing stop/target is defaulted, and that default is disclosed (audit F6) so
    # a minted ~6%/13% protective level is never shown as a PM-chosen price.
    stop_raw = _safe_float(parsed.get("stop"))
    target_raw = _safe_float(parsed.get("target"))
    stop = stop_raw if stop_raw is not None else round(entry * 0.94, 2)
    target = target_raw if target_raw is not None else round(entry * 1.13, 2)
    try:
        horizon_days = int(parsed.get("horizon_days"))
    except (TypeError, ValueError):
        horizon_days = ctx.trader_horizon_weeks * 7

    ceiling = _risk_tier_size_ceiling(ctx.mandate.risk_score)
    reason = narration or "Synthesis defended."
    if size_pct > ceiling:
        size_pct = ceiling
        reason += f" (sized down to {ceiling:.1f}% — mandate risk-tier ceiling.)"
    _defaulted = [n for n, raw in (("stop", stop_raw), ("target", target_raw)) if raw is None]
    if _defaulted:
        reason += (
            f" ({'/'.join(_defaulted)} not stated by the PM — defaulted to a "
            f"~6%/13%-from-entry protective level, not a PM-chosen price.)"
        )

    return narration, Verdict(
        action=VerdictAction.APPROVE,
        size_pct=size_pct,
        entry=entry,
        stop=stop,
        target=target,
        time_horizon_days=horizon_days,
        reason=reason,
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
_LEVEL_PATTERNS: dict[str, re.Pattern[str]] = {
    "entry": re.compile(r"\bentry\b[^\n$0-9]{0,15}\$?\s*(\d+(?:\.\d+)?)", re.IGNORECASE),
    "stop": re.compile(r"\bstop(?:[\s-]*loss)?\b[^\n$0-9]{0,15}\$?\s*(\d+(?:\.\d+)?)", re.IGNORECASE),
    "target": re.compile(r"\btarget\b[^\n$0-9]{0,15}\$?\s*(\d+(?:\.\d+)?)", re.IGNORECASE),
    "size": re.compile(r"\bsize\b[^\n$0-9]{0,15}\$?\s*(\d+(?:\.\d+)?)\s*%?", re.IGNORECASE),
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
        return float(m.group(1))
    except (TypeError, ValueError):
        return None


def _annotate_rr_against_levels(
    text: str,
    entry: float | None,
    stop: float | None,
    target: float | None,
    size: float | None,
) -> tuple[str, dict[str, Any] | None]:
    """Rewrite any narrated R:R in `text` to the one `entry/stop/target` imply, and —
    on a genuine discrepancy or a ratio the levels imply but the agent omitted —
    append a loud AMI verification note carrying the computed R:R / asymmetry /
    drawdown contribution. Returns (annotated_text, signal); `signal` is a telemetry
    payload when the narration contradicted the levels (or none was rendered though
    the levels imply one), else None. Flag-only (DEF059)."""
    implied = risk_reward(entry, stop, target)
    stated = _extract_stated_rr(text)
    if implied is None:
        # The levels form no valid long setup — AMI can't render a ratio. If the
        # agent narrated one regardless, strike it loudly rather than let an
        # unverifiable figure enter the transcript unmarked.
        if stated is None:
            return text, None
        annotated = _RR_CLAIM_RE.sub(
            lambda m: f"{m.group(1)}[AMI: unverifiable — the stated levels form no valid long setup]",
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
    dd = drawdown_contribution(size, entry, stop) if size is not None else None
    if dd is not None:
        parts.append(f"drawdown contribution ≈ {dd.contribution_pts:.2f} pt")
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


def _verify_and_annotate_geometry(text: str) -> tuple[str, dict[str, Any] | None]:
    """Verify a level-proposing agent's OWN narrated derived figures against AMI's
    trading_math (DEF095). An agent has "proposed levels" only when it states a full
    long-setup triple (entry + stop + target); anything less isn't a level claim and
    passes through untouched. Generalises the PM-only coherence check to any agent —
    principally the Trader, whose narrated ratio drives the whole downstream debate."""
    if not text:
        return text, None
    entry = _match_level(text, "entry")
    stop = _match_level(text, "stop")
    target = _match_level(text, "target")
    if entry is None or stop is None or target is None:
        return text, None
    size = _match_level(text, "size")
    return _annotate_rr_against_levels(text, entry, stop, target, size)


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
        summary=summary[:240],
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
    ) -> UUID:
        """Start a room run as a detached background task. Returns run_id immediately.

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
        if news_feed is None:
            news_feed = (
                resolve_news_feed(ticker, entitled=True)
                if settings.use_real_market_data
                else NewsFeed(LiveDataState.UNAVAILABLE, ())
            )
        if social_feed is None:
            social_feed = (
                resolve_social_feed(ticker, entitled=True)
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
        sim_block = _build_sim_holdings_block(user_id, ticker)
        portfolio_snapshot = _compose_portfolio_block(sim_block, alpaca_snap)

        # CR026: sector-concentration inputs (holdings + marks + resolver + weights),
        # built once per run off the request path.
        sector_holdings, sector_marks, sector_map, sector_weights = (
            _build_room_sector_context(user_id)
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
            withheld=roster.withheld,
            roster_next_step=roster.next_step,
            profile=_profile_for_ticker(
                ticker, news_feed=news_feed, social_feed=social_feed,
                withheld=frozenset(roster.withheld),
            ),
        )

        profile = ctx.profile
        # Initialise trader prices off the profile
        base = profile["base_price"]
        ctx.trader_entry = round(base, 2)
        ctx.trader_stop = round(base * 0.94, 2)
        ctx.trader_target = round(base * 1.13, 2)
        ctx.trader_size_pct = _risk_tier_size_ceiling(mandate.risk_score)
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
        formatter.update({
            "ticker": ctx.ticker,
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
                        for agent_id, (text, geom_sig) in zip(phase_agents, results):
                            async for ev in _stream_agent_text(
                                agent_id=agent_id,
                                run_id=run_id,
                                run=run,
                                text=text,
                                geom_sig=geom_sig,
                                char_delay_min=char_delay_min,
                                char_delay_max=char_delay_max,
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
) -> tuple[str, dict[str, Any] | None]:
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
            # CR077 §Build 5: a concurrent analyst has no transcript to build on —
            # rescope the "do not repeat" line so it sharpens the own-domain lens
            # instead of pointing at an empty transcript.
            parallel_phase=parallel_phase,
            # CR026: the PM sees the real sector allocation it gatekeeps against.
            sector_weights=ctx.sector_weights,
        )
        try:
            chunks = await asyncio.wait_for(
                _collect_agent_stream(gateway.stream_chat(
                    system_prompt=system_prompt,
                    messages=messages,
                    model_tier=tier,  # type: ignore[arg-type]
                    locale=ctx.mandate.locale,
                    max_tokens=400,
                    audit_user_id=ctx.user_id,
                    audit_agent_id=agent_id.value,
                    audit_flow="room",
                )),
                timeout=agent_timeout_s,
            )
            text = "".join(chunks).strip() or _scripted_for(agent_id, formatter)
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
    text, geom_sig = _verify_and_annotate_geometry(text)
    return text, geom_sig


async def _stream_agent_text(
    *,
    agent_id: AgentId,
    run_id: UUID,
    run: RoomRun,
    text: str,
    geom_sig: dict[str, Any] | None,
    char_delay_min: float,
    char_delay_max: float,
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

    run.transcript.append(AgentMessage(
        agent_id=agent_id,
        role="agent",
        content=text,
        timestamp=datetime.now(timezone.utc),
    ))
    _checkpoint_run(run)  # incremental snapshot — narrows data-loss window to ≤1 agent
    yield RoomEvent(kind="agent_done", run_id=run_id, agent_id=agent_id)


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
    text, geom_sig = await _compute_agent_text(
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
    )
    try:
        chunks = await asyncio.wait_for(
            _collect_agent_stream(gateway.stream_chat(
                system_prompt=system_prompt,
                messages=messages,
                model_tier=tier,  # type: ignore[arg-type]
                locale=ctx.mandate.locale,
                max_tokens=600,
                audit_user_id=ctx.user_id,
                audit_agent_id=AgentId.PORTFOLIO_MANAGER.value,
                audit_flow="room_pm",
            )),
            timeout=agent_timeout_s,
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
    ' "narration": "<3-4 sentences, faithful summary of the rationale>"}\n'
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
    try:
        chunks = await asyncio.wait_for(
            _collect_agent_stream(gateway.stream_chat(
                system_prompt=_PM_REFORMAT_SYSTEM,
                messages=[ChatMessage(role="user", content=raw_text)],
                model_tier=tier,  # type: ignore[arg-type]
                locale=ctx.mandate.locale,
                max_tokens=400,
                audit_user_id=ctx.user_id,
                audit_agent_id=AgentId.PORTFOLIO_MANAGER.value,
                audit_flow="room_pm_reformat",
            )),
            timeout=agent_timeout_s,
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
