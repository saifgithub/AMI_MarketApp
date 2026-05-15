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
from app.core.config import settings
from app.core.logging import logger
from app.db import get_session, init_schema
from app.db.models import RoomRunRow
from app.schemas import AgentId, AgentMessage, Mandate
from app.schemas.mandate import Plan
from app.schemas.room import RoomRun, RoomStatus, Verdict, VerdictAction
from app.schemas.trade import OrderType, ProposedTrade, Side
from app.services.llm_gateway import LLMGateway, get_llm_gateway
from app.services.room_prompts import build_room_messages
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
    user_id: UUID | None = None
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


def _fetch_live_fundamentals(ticker: str) -> dict[str, Any] | None:
    """Fetch real fundamentals via yfinance. Returns None on any error.

    Only numeric fields the LLM is likely to misremember from training:
    P/E, revenue growth, FCF margin, net cash, 52-week range, price.
    Narrative fields (catalysts, sentiment) stay synthetic — yfinance
    doesn't have them and pretending it does would replace one lie with
    another. The prompt labels the data source so the LLM knows what's
    live vs scaffolded.
    """
    try:
        import yfinance as yf
        info = yf.Ticker(ticker.upper()).info
    except Exception:
        return None
    if not info:
        return None

    def _num(key: str) -> float | None:
        v = info.get(key)
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    price = _num("currentPrice") or _num("regularMarketPrice")
    pe = _num("trailingPE")
    # Anchor the result on real signals — if price + pe are both missing,
    # the ticker is unknown to yfinance and we should fall through to synthetic.
    if price is None and pe is None:
        return None

    out: dict[str, Any] = {}
    if price is not None:
        out["base_price"] = round(price, 2)
        out["low"] = round(price * 0.95, 2)
        out["high"] = round(price * 1.05, 2)
        out["support"] = round(price * 0.9, 2)
        out["breakout"] = round(price * 1.03, 2)
    fifty_two_low = _num("fiftyTwoWeekLow")
    fifty_two_high = _num("fiftyTwoWeekHigh")
    if fifty_two_low is not None and fifty_two_high is not None:
        out["low"] = round(fifty_two_low, 2)
        out["high"] = round(fifty_two_high, 2)
    if pe is not None:
        out["pe"] = f"{pe:.1f}"
    rev_growth = _num("revenueGrowth")
    if rev_growth is not None:
        # yfinance reports growth as a decimal (0.05 = 5%).
        out["rev_growth"] = round(rev_growth * 100)
    profit_margin = _num("profitMargins")
    if profit_margin is not None:
        out["fcf_margin"] = round(profit_margin * 100)
    # totalCash and totalDebt are in dollars; net cash in millions for the prompt
    total_cash = _num("totalCash")
    total_debt = _num("totalDebt")
    if total_cash is not None and total_debt is not None:
        out["net_cash"] = round((total_cash - total_debt) / 1_000_000)
    return out


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
        "sentiment_score": f"+{rng.uniform(0.3, 1.8):.1f}",
        "mention_trend": "up 40% week-over-week",
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
        live = _fetch_live_fundamentals(ticker)
        if live:
            profile.update(live)
            profile["data_source"] = "yfinance_live"

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

    def __init__(self, llm: LLMGateway | None = None) -> None:
        init_schema()
        # Late-bound so tests can pass a fake gateway via constructor.
        # In production, get_room_runner() wires get_llm_gateway() once.
        self._llm: LLMGateway | None = llm

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

        # Emit `started` first so clients have the run_id immediately —
        # critical for the "phone went to sleep, come back and see results"
        # recovery path. Without this, the run_id only landed on the final
        # `done` event, useless to a disconnected client.
        yield RoomEvent(kind="started", run_id=run_id)

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
            user_id=user_id,
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
) -> AsyncIterator[RoomEvent]:
    """Stream one agent's contribution; LLM when live, scripted otherwise.

    Appends the final text to `run.transcript` before yielding `agent_done`
    so the next agent sees this contribution in its prompt.
    """
    plan = ctx.mandate.plan if isinstance(ctx.mandate.plan, Plan) else Plan(ctx.mandate.plan)
    tier = pick_tier(plan, agent_id)

    text: str
    if live:
        system_prompt, messages = build_room_messages(
            agent_id=agent_id,
            mandate=ctx.mandate,
            user_id=None,
            ticker=ctx.ticker,
            profile=profile,
            transcript=run.transcript,
        )
        buf: list[str] = []
        try:
            async for chunk in gateway.stream_chat(
                system_prompt=system_prompt,
                messages=messages,
                model_tier=tier,  # type: ignore[arg-type]
                locale=ctx.mandate.locale,
                max_tokens=400,
                audit_user_id=ctx.user_id,
                audit_agent_id=agent_id.value,
                audit_flow="room",
            ):
                buf.append(chunk)
                yield RoomEvent(
                    kind="agent_token",
                    run_id=run_id,
                    agent_id=agent_id,
                    text=chunk,
                )
            text = "".join(buf).strip()
            if not text:
                # Defensive: an empty LLM response shouldn't blank the
                # transcript. Drop to the scripted template.
                text = _scripted_for(agent_id, formatter)
                async for ev in _typewriter(
                    run_id, agent_id, text, char_delay_min, char_delay_max,
                ):
                    yield ev
        except Exception as exc:  # pragma: no cover — defensive
            logger.warn(
                "room_agent_llm_failed",
                agent_id=agent_id.value,
                error=str(exc)[:200],
            )
            text = _scripted_for(agent_id, formatter)
            async for ev in _typewriter(
                run_id, agent_id, text, char_delay_min, char_delay_max,
            ):
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
) -> str:
    """Buffer the PM's LLM rationale, then return the full text.

    Buffered (not streamed inline as we go) because the caller restreams
    it through the UI typewriter so the rendering keeps a steady pace
    regardless of upstream LLM chunk cadence. Tests don't care about
    pacing; production keeps a uniform feel.
    """
    plan = ctx.mandate.plan if isinstance(ctx.mandate.plan, Plan) else Plan(ctx.mandate.plan)
    tier = pick_tier(plan, AgentId.PORTFOLIO_MANAGER)
    system_prompt, messages = build_room_messages(
        agent_id=AgentId.PORTFOLIO_MANAGER,
        mandate=ctx.mandate,
        user_id=None,
        ticker=ctx.ticker,
        profile=profile,
        transcript=run.transcript,
        pm_predetermined_action=predetermined,
    )
    buf: list[str] = []
    try:
        async for chunk in gateway.stream_chat(
            system_prompt=system_prompt,
            messages=messages,
            model_tier=tier,  # type: ignore[arg-type]
            locale=ctx.mandate.locale,
            max_tokens=500,
            audit_user_id=ctx.user_id,
            audit_agent_id=AgentId.PORTFOLIO_MANAGER.value,
            audit_flow="room_pm",
        ):
            buf.append(chunk)
        text = "".join(buf).strip()
    except Exception as exc:  # pragma: no cover — defensive
        logger.warn("room_pm_llm_failed", error=str(exc)[:200])
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
