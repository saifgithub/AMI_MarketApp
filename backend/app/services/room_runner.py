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

Spec: docs/02_agents/convene_the_room.md
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select

from app.agents.safety_floor import check_mandate_compliance, SINGLE_NAME_CAP_PCT
from app.core.logging import logger
from app.db import get_session, init_schema
from app.db.models import RoomRunRow
from app.schemas import AgentId, AgentMessage, Mandate
from app.schemas.mandate import Plan
from app.schemas.room import RoomRun, RoomStatus, Verdict, VerdictAction
from app.schemas.trade import OrderType, ProposedTrade, Side
from app.services.tier_policy import pick_tier


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
        "Retail sentiment on {ticker} is {sentiment_tone} (Stocktwits "
        "{sentiment_score}σ over the week). Reddit /r/investing mentions "
        "{mention_trend}. Influencer narrative: {influencer_take}. "
        "Pattern read: {pattern}.",
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
    """Deterministic-ish ticker-flavoured profile.

    Same ticker → same profile across runs, so the alpha demo feels
    consistent. A live data feed replaces this at W8+.
    """
    rng = random.Random(hash(ticker.upper()))
    base_price = 50 + rng.uniform(0, 400)
    pe = rng.uniform(12, 55)
    rev_growth = rng.randint(2, 40)
    fcf_margin = rng.randint(8, 35)
    sector_pe = rng.uniform(15, 25)
    is_growth = pe > 30 and rev_growth > 15
    return {
        "ticker": ticker.upper(),
        "base_price": round(base_price, 2),
        "pe": f"{pe:.1f}",
        "sector_pe": f"{sector_pe:.0f}",
        "rev_growth": rev_growth,
        "fcf_margin": fcf_margin,
        "net_cash": rng.randint(-5_000, 80_000),
        "valuation_tone": "fairly priced relative to growth"
            if is_growth else "trading at a discount to its peers",
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
        "sentiment_score": f"+{rng.uniform(0.3, 1.8):.1f}",
        "mention_trend": "up 40% week-over-week",
        "influencer_take": "broadly constructive, no euphoria",
        "pattern": "sentiment confirming price, not yet at exhaustion",
        "bull_thesis": (
            f"{ticker.upper()}'s revenue growth ({rev_growth}%) and FCF margin "
            f"({fcf_margin}%) justify a premium multiple"
        ),
        "bull_evidence": "consensus has under-modelled the next 4 quarters of guidance",
        "bull_missing": "supply-chain commentary that suggests upside to FY guide",
        "bull_size": 4,
        "bull_falsifier": "next quarter's guide is reset lower by 10%+",
        "bear_risk": f"multiple compression if growth decelerates — {pe:.0f}x is sensitive",
        "bear_quant": f"a 10-point multiple compression = ~{int(pe / (pe + 10) * 100 - 50)}% downside",
        "bear_catalyst": "any miss on forward guide, or sector-wide re-rating event",
        "bear_size": 2,
        "bear_invalidator": "next two quarters both beat AND raise",
        "upside": 28,
        "downside": 18,
        "synth_lean": "constructive bull",
        "is_growth": is_growth,
    }


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


@dataclass
class RoomEvent:
    """A single streamed event from the Room runner.

    The API layer (room.py) translates this into SSE.
    """
    kind: str  # 'phase' | 'agent_token' | 'agent_done' | 'verdict' | 'error'
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


class RoomRunner:
    """Orchestrates a Convene the Room session, streams events, persists runs."""

    def __init__(self) -> None:
        init_schema()

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

    async def run(
        self,
        *,
        user_id: UUID,
        ticker: str,
        mandate: Mandate,
        portfolio_value: float = 100_000.0,
        current_drawdown_pct: float = 0.0,
        halal_universe: set[str] | None = None,
        locale_allowed_universe: set[str] | None = None,
        char_delay_min: float = _CHAR_DELAY_MIN,
        char_delay_max: float = _CHAR_DELAY_MAX,
    ) -> AsyncIterator[RoomEvent]:
        """Run a Room session, yielding events as agents speak.

        The function returns an async generator. Callers consume it; the
        final event is a `verdict` with the assembled Verdict, after which
        the RoomRun is finalised and stored.
        """
        run_id = uuid4()
        now = datetime.now(timezone.utc)
        plan = mandate.plan if isinstance(mandate.plan, Plan) else Plan(mandate.plan)
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

        # Halal universe: tiny demo set. Real screen ships at W8+.
        halal = halal_universe or {"AAPL", "MSFT", "NVDA", "GOOGL", "META", "TSLA", "AMZN"}
        # None = no locale restriction (default for alpha). Explicit set ⇒ enforced.
        locale_allowed = locale_allowed_universe

        ctx = _RoomContext(
            ticker=ticker.upper(),
            mandate=mandate,
            portfolio_value=portfolio_value,
            current_drawdown_pct=current_drawdown_pct,
            halal_universe=halal,
            locale_allowed_universe=locale_allowed,
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

        try:
            for phase in PHASES:
                yield RoomEvent(kind="phase", phase=phase.label, run_id=run_id)
                if phase.label != "VERDICT":
                    for agent_id in phase.agents:
                        tpl = _TEMPLATES[agent_id][0]
                        text = tpl.format(**formatter)
                        run.transcript.append(AgentMessage(
                            agent_id=agent_id,
                            role="agent",
                            content=text,
                            timestamp=datetime.now(timezone.utc),
                        ))
                        async for ev in _typewriter(
                            run_id, agent_id, text, char_delay_min, char_delay_max
                        ):
                            yield ev
                        yield RoomEvent(
                            kind="agent_done", run_id=run_id, agent_id=agent_id,
                        )
                else:
                    # Phase 6 — PM: assemble verdict, then narrate.
                    verdict = _assemble_verdict(ctx, profile)
                    if verdict.action == VerdictAction.APPROVE:
                        mandate_check = "PASS"
                        verdict_rationale = (
                            f"Synthesis defended; sizing {ctx.trader_size_pct:.1f}% "
                            f"consistent with risk_score {mandate.risk_score}."
                        )
                    else:
                        mandate_check = f"FAIL — {', '.join(verdict.violations)}"
                        verdict_rationale = verdict.reason
                    pm_text = _TEMPLATES[AgentId.PORTFOLIO_MANAGER][0].format(
                        **formatter,
                        verdict_action=verdict.action,
                        verdict_rationale=verdict_rationale,
                        mandate_check=mandate_check,
                    )
                    run.transcript.append(AgentMessage(
                        agent_id=AgentId.PORTFOLIO_MANAGER,
                        role="agent",
                        content=pm_text,
                        timestamp=datetime.now(timezone.utc),
                    ))
                    async for ev in _typewriter(
                        run_id, AgentId.PORTFOLIO_MANAGER, pm_text,
                        char_delay_min, char_delay_max,
                    ):
                        yield ev
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


_runner: RoomRunner | None = None


def get_room_runner() -> RoomRunner:
    global _runner
    if _runner is None:
        _runner = RoomRunner()
    return _runner
