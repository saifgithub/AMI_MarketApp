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
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select

from app.agents.safety_floor import check_mandate_compliance, SINGLE_NAME_CAP_PCT
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
from app.services.news_context import fetch_live_news, format_headline
from app.services.llm_gateway import LLMGateway, get_llm_gateway
from app.services.room_prompts import build_room_messages
from app.services.entitlements import effective_plan_for_user
from app.services.tier_policy import pick_tier
from app.services.alpaca_service import snapshot_text as alpaca_snapshot_text


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


PHASES: tuple[_Phase, ...] = (
    _Phase("ANALYSTS", (
        AgentId.FUNDAMENTALS_ANALYST,
        AgentId.MARKET_ANALYST,
        AgentId.NEWS_ANALYST,
        AgentId.SOCIAL_MEDIA_ANALYST,
    )),
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
        "{ticker} trades at a trailing P/E of {pe}x, vs sector median ~{sector_pe}x. "
        "TTM revenue growth {rev_growth}%; FCF margin {fcf_margin}%. "
        "Balance sheet: net cash {net_cash}M. "
        "On the fundamentals alone, the name is {valuation_tone}.",
    ],
    AgentId.MARKET_ANALYST: [
        "Daily chart shows {ticker} {trend} above the 50-day MA, with the 200-day "
        "as longer-term support around ${support}. RSI({rsi}) — {rsi_tone}. "
        "Last week's range was ${low}–${high}, breakout level sits at ${breakout}. "
        "Volume {volume_tone}.",
    ],
    AgentId.NEWS_ANALYST: [
        "{ticker}'s last catalyst was {catalyst}. Forward catalysts: "
        "{forward_catalyst}. Macro backdrop is {macro_tone} — Fed path is "
        "{fed_tone}, which {fed_impact} multiples on growth names.",
    ],
    AgentId.SOCIAL_MEDIA_ANALYST: [
        "Retail sentiment on {ticker} reads as {sentiment_tone} in this "
        "illustrative scenario ({sentiment_score} — no live social feed "
        "connected). Hypothetical mention volume: {mention_trend}. "
        "Illustrative influencer narrative: {influencer_take}. Pattern read "
        "(for discussion, not measured): {pattern}.",
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
        "(below the {stop_basis}). Target ${target} (R:R = {rr}:1). "
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


@dataclass
class _RoomContext:
    ticker: str
    mandate: Mandate
    portfolio_value: float
    current_drawdown_pct: float
    halal_universe: set[str]
    locale_allowed_universe: set[str] | None
    user_id: UUID | None = None
    alpaca_snapshot: str | None = None  # AT:R45 — pre-fetched once per run
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


def _profile_for_ticker(ticker: str) -> dict[str, Any]:
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
    rng = random.Random(hash(ticker.upper()))
    base_price = 50 + rng.uniform(0, 400)
    pe = rng.uniform(12, 55)
    rev_growth = rng.randint(2, 40)
    fcf_margin = rng.randint(8, 35)
    sector_pe = rng.uniform(15, 25)
    profile: dict[str, Any] = {
        "ticker": ticker.upper(),
        "base_price": round(base_price, 2),
        "pe": f"{pe:.1f}",
        "sector_pe": f"{sector_pe:.0f}",
        "rev_growth": rev_growth,
        "fcf_margin": fcf_margin,
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
        "forward_catalyst": "FOMC decision in 11 days, sector earnings in 3 weeks",
        "macro_tone": "constructive but fragile",
        "fed_tone": "data-dependent with a dovish lean",
        "fed_impact": "is generally supportive of",
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

        # Overlay a real headline onto `catalyst` (CR023, AT:R57). Only the
        # top headline replaces `catalyst` — `forward_catalyst`/`macro_tone`/
        # `fed_tone`/`fed_impact` are left untouched, since no real macro-
        # calendar feed exists; fabricating a "fix" for those would be worse
        # than clearly-labeled synthetic scaffolding (see room_prompts.py).
        news_items = fetch_live_news(ticker)
        if news_items:
            profile["catalyst"] = format_headline(news_items[0])
            profile["news_headlines"] = news_items
            profile["news_source"] = "live"

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

    # Derive narrative strings from whatever numbers ended up in the
    # profile (real or synthetic) so the prose is consistent with the data.
    pe_val = float(profile["pe"]) if isinstance(profile["pe"], str) else float(profile["pe"])
    rev_growth_val = profile["rev_growth"]
    fcf_margin_val = profile["fcf_margin"]
    is_growth = pe_val > 30 and rev_growth_val > 15
    profile["is_growth"] = is_growth
    profile["valuation_tone"] = (
        "fairly priced relative to growth" if is_growth
        else "trading at a discount to its peers"
    )
    profile["bull_thesis"] = (
        f"{ticker.upper()}'s revenue growth ({rev_growth_val}%) and FCF margin "
        f"({fcf_margin_val}%) justify a premium multiple"
    )
    profile["bear_risk"] = (
        f"multiple compression if growth decelerates — {pe_val:.0f}x is sensitive"
    )
    profile["bear_quant"] = (
        f"a 10-point multiple compression = ~{int(pe_val / (pe_val + 10) * 100 - 50)}% downside"
    )
    return profile


# ── Verdict assembly ──────────────────────────────────────────────────────


def _assemble_verdict(ctx: _RoomContext, profile: dict[str, Any]) -> Verdict:
    proposed = ProposedTrade(
        ticker=ctx.ticker,
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        quantity=max(1, int((ctx.portfolio_value * ctx.trader_size_pct / 100) / ctx.trader_entry)),
        limit_price=ctx.trader_entry,
    )
    result = check_mandate_compliance(
        proposed,
        portfolio_value=ctx.portfolio_value,
        current_drawdown_pct=ctx.current_drawdown_pct,
        mandate=ctx.mandate,
        halal_universe=ctx.halal_universe,
        locale_allowed_universe=ctx.locale_allowed_universe,
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
    kind: str  # 'started' | 'phase' | 'agent_token' | 'agent_done' | 'verdict' | 'error'
    phase: str | None = None
    agent_id: AgentId | None = None
    text: str | None = None
    verdict: Verdict | None = None
    run_id: UUID | None = None


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
        locale_allowed_universe: set[str] | None = None,
        char_delay_min: float = _CHAR_DELAY_MIN,
        char_delay_max: float = _CHAR_DELAY_MAX,
        agent_timeout_s: float = _AGENT_LLM_TIMEOUT_S,
    ) -> AsyncIterator[RoomEvent]:
        """Run a Room session, yielding events as agents speak.

        The function returns an async generator. Callers consume it; the
        final event is a `verdict` with the assembled Verdict, after which
        the RoomRun is finalised and stored.

        `run_id` is optional — if provided (by start_run), the caller
        pre-allocated the ID so it can set up the event queue before the
        generator starts. If omitted, a fresh UUID is generated here.
        """
        run_id = run_id or uuid4()
        now = datetime.now(timezone.utc)
        # BL11 (AT:R33): effective_plan downgrades expired trials.
        plan = effective_plan_for_user(user_id)
        tier = pick_tier(plan, AgentId.PORTFOLIO_MANAGER)
        credit_cost = 25 if tier == "premium" else 8

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

        # Halal universe: tiny demo set. Real screen ships at W8+.
        halal = halal_universe or {"AAPL", "MSFT", "NVDA", "GOOGL", "META", "TSLA", "AMZN"}
        # None = no locale restriction (default for alpha). Explicit set ⇒ enforced.
        locale_allowed = locale_allowed_universe

        # AT:R45 — fetch Alpaca paper portfolio once per run; injected into
        # every agent's system prompt. Best-effort: None if unlinked or error.
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

        ctx = _RoomContext(
            ticker=ticker.upper(),
            mandate=mandate,
            portfolio_value=portfolio_value,
            current_drawdown_pct=current_drawdown_pct,
            halal_universe=halal,
            locale_allowed_universe=locale_allowed,
            user_id=user_id,
            alpaca_snapshot=alpaca_snap,
            profile=_profile_for_ticker(ticker),
        )

        profile = ctx.profile
        # Initialise trader prices off the profile
        base = profile["base_price"]
        ctx.trader_entry = round(base, 2)
        ctx.trader_stop = round(base * 0.94, 2)
        ctx.trader_target = round(base * 1.13, 2)
        ctx.trader_size_pct = (
            4.5 if int(mandate.risk_score) >= 4
            else 1.5 if int(mandate.risk_score) <= 2
            else 3.0
        )
        ctx.aggressive_size_pct = min(SINGLE_NAME_CAP_PCT, ctx.trader_size_pct + 2)
        ctx.conservative_size_pct = max(0.5, ctx.trader_size_pct - 1.5)
        ctx.neutral_size_pct = ctx.trader_size_pct

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
            "stop_basis": "20-day low",
            "rr": f"{(ctx.trader_target - ctx.trader_entry) / max(0.01, ctx.trader_entry - ctx.trader_stop):.1f}",
            "agg_size": f"{ctx.aggressive_size_pct:.1f}",
            "cons_size": f"{ctx.conservative_size_pct:.1f}",
            "neu_size": f"{ctx.neutral_size_pct:.1f}",
            "synth_size": f"{ctx.trader_size_pct:.1f}",
        })

        gateway = self._llm or get_llm_gateway()
        live = gateway.has_real_provider()

        try:
            for phase in PHASES:
                yield RoomEvent(kind="phase", phase=phase.label, run_id=run_id)
                if phase.label != "VERDICT":
                    for agent_id in phase.agents:
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
                            alpaca_snapshot=ctx.alpaca_snapshot,
                        ):
                            yield ev
                else:
                    # Phase 6 — PM: deterministic safety-floor first; LLM
                    # narrates the rationale around that fixed action.
                    verdict = _assemble_verdict(ctx, profile)
                    if verdict.action == VerdictAction.APPROVE:
                        mandate_check = "PASS"
                        verdict_rationale_fallback = (
                            f"Synthesis defended; sizing {ctx.trader_size_pct:.1f}% "
                            f"consistent with risk_score {mandate.risk_score}."
                        )
                        predetermined = "APPROVE"
                    else:
                        mandate_check = f"FAIL — {', '.join(verdict.violations)}"
                        verdict_rationale_fallback = verdict.reason
                        predetermined = f"REJECT ({'; '.join(verdict.violations)})"

                    if live:
                        pm_text = await _stream_pm_narration(
                            run_id=run_id,
                            ctx=ctx,
                            profile=profile,
                            formatter=formatter,
                            run=run,
                            gateway=gateway,
                            predetermined=predetermined,
                            mandate_check=mandate_check,
                            agent_timeout_s=agent_timeout_s,
                        )
                        async for ev in _restream_for_ui(
                            run_id, AgentId.PORTFOLIO_MANAGER, pm_text,
                            char_delay_min, char_delay_max,
                        ):
                            yield ev
                    else:
                        pm_text = _TEMPLATES[AgentId.PORTFOLIO_MANAGER][0].format(
                            **formatter,
                            verdict_action=verdict.action,
                            verdict_rationale=verdict_rationale_fallback,
                            mandate_check=mandate_check,
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
        except Exception as e:  # pragma: no cover
            run.status = RoomStatus.FAILED
            run.error_message = str(e)[:500]
            _persist_run(run)
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
    alpaca_snapshot: str | None = None,
) -> AsyncIterator[RoomEvent]:
    """Stream one agent's contribution; LLM when live, scripted otherwise.

    The live path buffers the full LLM response (with a per-agent timeout)
    before restreaming via the typewriter, matching the PM-narration pattern.
    If the upstream model hangs past `agent_timeout_s`, the agent falls back
    to its scripted template so the run can still finish.

    Appends the final text to `run.transcript` before yielding `agent_done`
    so the next agent sees this contribution in its prompt.
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
            transcript=run.transcript,
            alpaca_snapshot=alpaca_snapshot,
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
        async for ev in _typewriter(run_id, agent_id, text, char_delay_min, char_delay_max):
            yield ev
    else:
        text = _scripted_for(agent_id, formatter)
        async for ev in _typewriter(
            run_id, agent_id, text, char_delay_min, char_delay_max,
        ):
            yield ev

    run.transcript.append(AgentMessage(
        agent_id=agent_id,
        role="agent",
        content=text,
        timestamp=datetime.now(timezone.utc),
    ))
    _checkpoint_run(run)  # incremental snapshot — narrows data-loss window to ≤1 agent
    yield RoomEvent(kind="agent_done", run_id=run_id, agent_id=agent_id)


async def _stream_pm_narration(
    *,
    run_id: UUID,
    ctx: _RoomContext,
    profile: dict[str, Any],
    formatter: dict[str, Any],
    run: RoomRun,
    gateway: LLMGateway,
    predetermined: str,
    mandate_check: str,
    agent_timeout_s: float = _AGENT_LLM_TIMEOUT_S,
) -> str:
    """Buffer the PM's LLM rationale, then return the full text.

    Buffered (not streamed inline as we go) because the caller restreams
    it through the UI typewriter so the rendering keeps a steady pace
    regardless of upstream LLM chunk cadence. Tests don't care about
    pacing; production keeps a uniform feel.
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
        pm_predetermined_action=predetermined,
        alpaca_snapshot=ctx.alpaca_snapshot,
    )
    try:
        chunks = await asyncio.wait_for(
            _collect_agent_stream(gateway.stream_chat(
                system_prompt=system_prompt,
                messages=messages,
                model_tier=tier,  # type: ignore[arg-type]
                locale=ctx.mandate.locale,
                max_tokens=500,
                audit_user_id=ctx.user_id,
                audit_agent_id=AgentId.PORTFOLIO_MANAGER.value,
                audit_flow="room_pm",
            )),
            timeout=agent_timeout_s,
        )
        text = "".join(chunks).strip()
    except asyncio.TimeoutError:
        logger.warning("room_pm_timeout", timeout_s=agent_timeout_s)
        text = ""
    except Exception as exc:
        logger.warning("room_pm_llm_failed", error=str(exc)[:200])
        text = ""

    if not text:
        # Fall back to the scripted PM template.
        text = _TEMPLATES[AgentId.PORTFOLIO_MANAGER][0].format(
            **formatter,
            verdict_action=predetermined.split(" ", 1)[0],
            verdict_rationale="Synthesis defended; sizing consistent with mandate.",
            mandate_check=mandate_check,
        )

    return text


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


_runner: RoomRunner | None = None


def get_room_runner() -> RoomRunner:
    global _runner
    if _runner is None:
        _runner = RoomRunner()
    return _runner
