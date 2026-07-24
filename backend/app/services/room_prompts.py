"""Convene the Room — per-agent prompt composition.

Each agent in a Room run gets a system prompt that combines:
  1. The agent's base prompt (loaded from content/agents/<id>.md and
     wrapped with the user's mandate overlay + safety floor where
     applicable — handled by `agent_prompts.build_agent_prompt`).
  2. A "Room addition" block with the ticker profile, the running
     transcript so far, and a task framing for the current phase.

The user message is a short kickoff ("Convene on AAPL.") — all the real
context lives in the system prompt. This mirrors how `agent_runner`
streams 1-on-1: same gateway, same `ChatMessage` shape, drop-in.

When `gateway.has_real_provider()` is False, callers should fall back
to scripted text from `room_runner._TEMPLATES`. That path keeps the
demo working when the LAN vLLM box is unreachable.
"""

from __future__ import annotations

from typing import Any

from app.schemas import AgentId, AgentMessage, Mandate
from app.schemas.mandate import Plan
from app.services.agent_prompts import build_agent_prompt
from app.services.journal_context import build_journal_context_block
from app.services.llm_gateway import ChatMessage
from app.trading_math.risk import drawdown_contribution
from app.trading_math.valuation import net_position_phrase

# ── Phase framing ────────────────────────────────────────────────────────


_PHASE_FOR_AGENT: dict[AgentId, str] = {
    AgentId.FUNDAMENTALS_ANALYST: "ANALYSTS",
    AgentId.MARKET_ANALYST: "ANALYSTS",
    AgentId.NEWS_ANALYST: "ANALYSTS",
    AgentId.SOCIAL_MEDIA_ANALYST: "ANALYSTS",
    AgentId.BULL_RESEARCHER: "RESEARCHERS",
    AgentId.BEAR_RESEARCHER: "RESEARCHERS",
    AgentId.RESEARCH_MANAGER: "SYNTHESIS",
    AgentId.TRADER: "EXECUTION",
    AgentId.AGGRESSIVE_DEBATOR: "RISK",
    AgentId.CONSERVATIVE_DEBATOR: "RISK",
    AgentId.NEUTRAL_DEBATOR: "RISK",
    AgentId.PORTFOLIO_MANAGER: "VERDICT",
}


# Soft length budgets per phase (kept short — Matrix Console UI is
# token-paced and the user reads each agent's full contribution before
# the next speaks).
_LENGTH_GUIDE: dict[AgentId, str] = {
    AgentId.FUNDAMENTALS_ANALYST: "2–4 sentences",
    AgentId.MARKET_ANALYST: "2–4 sentences",
    AgentId.NEWS_ANALYST: "2–3 sentences",
    AgentId.SOCIAL_MEDIA_ANALYST: "2–3 sentences",
    AgentId.BULL_RESEARCHER: "3–5 sentences (thesis + evidence + falsifier)",
    AgentId.BEAR_RESEARCHER: "3–5 sentences (risk + quantification + invalidator)",
    AgentId.RESEARCH_MANAGER: "4–6 sentences (asymmetry numbers + lean + size implication)",
    AgentId.TRADER: "3–4 sentences (instrument + side + size + entry + stop + target + horizon)",
    AgentId.AGGRESSIVE_DEBATOR: "2 sentences (size push + one-line reason)",
    AgentId.CONSERVATIVE_DEBATOR: "2 sentences (size cap + one-line reason)",
    AgentId.NEUTRAL_DEBATOR: "2 sentences (middle size + one-line reason)",
    AgentId.PORTFOLIO_MANAGER: "3–4 sentences inside your JSON verdict's narration field — see the format instruction below",
}


# ── Public ───────────────────────────────────────────────────────────────


# PM speaks last and its output is the binding Verdict (DEF056) — it gets a
# structured JSON format instead of the free prose every other agent writes.
# `enforce_safety_floor()` (app/agents/safety_floor.py) re-checks whatever
# action the PM picks; this instruction just tells it the vocabulary and
# shape we can actually parse.
_PM_VERDICT_FORMAT = (
    "\nYou are the final decision-maker. Weigh everything above — every "
    "analyst, the Bull/Bear debate, the Trader's proposal, and the three "
    "Risk Debators — then decide for yourself. Do not just restate the "
    "Trader's numbers; agree or disagree based on the whole debate.\n"
    "This output format REPLACES the 'Verdict:' / 'Output format' block "
    "described earlier in your profile. In the Room you answer here, and only "
    "here.\n"
    "Your ENTIRE reply must be one single JSON object — begin with '{' and "
    "end with '}'. Do not write any prose outside the JSON (your reasoning "
    "belongs inside the narration field); anything outside it is discarded "
    "and your verdict is lost. Shape it exactly like:\n"
    '{"action": "APPROVE" | "PASS",\n'
    ' "size_pct": <number, required if APPROVE — position size as % of portfolio>,\n'
    ' "entry": <number, required if APPROVE>,\n'
    ' "stop": <number, required if APPROVE>,\n'
    ' "target": <number, required if APPROVE>,\n'
    ' "horizon_days": <integer, required if APPROVE>,\n'
    ' "narration": "<3-4 sentences, your rationale, written for the user>"}\n'
    "There are exactly two action values: APPROVE and PASS. A modification IS "
    "an approval — if you want to cut the Trader's size, tighten the stop, or "
    "shift the entry, use action APPROVE with your revised numbers in "
    "size_pct/entry/stop and explain the change in narration. Do NOT write "
    "'MODIFY', 'MODIFY-AND-APPROVE', or any other value — they are discarded "
    "and your verdict is lost.\n"
    "Use PASS when the debate does not support entering a position right now "
    "(e.g. the Trader recommended WAIT, or the risk/reward doesn't clear the "
    "bar) — PASS needs only narration, no size/entry/stop/target.\n"
    "The safety floor above still applies regardless of what you decide — "
    "if it detects a violation, output PASS and name the rule in narration."
)

_PROSE_FORMAT = (
    "\nFormat: lead with a one-sentence thesis, then short bullet "
    "points for supporting evidence. Use **bold** for key metrics "
    "(numbers, levels, deadlines). Plain text otherwise — no headings, "
    "no tables, no code fences. The Markdown is rendered live in the app."
)


def _drawdown_snapshot_line(mandate: Mandate, trade_proposal: dict[str, Any] | None) -> str:
    """The mandate-snapshot drawdown line (DEF066).

    Always states that the cap is portfolio-level, not a per-trade stop budget.
    When a concrete reference proposal is supplied (RISK / VERDICT phases), it also
    hands the agent the *derived* contribution figure so no agent has to do — or
    mis-do — the arithmetic that made 16 names un-buyable in the CR035 benchmark
    (a stop distance was compared directly against the cap, ~20x overstating the
    risk).

    Audit D-e: the numbers are a DETERMINISTIC reference position (the risk-tier
    ceiling at a reference entry/stop), computed before the debate — not the live
    Trader's exact words, which live only in the transcript. Labelled as a
    reference so the figure is honest rather than attributed to a proposal the
    Trader may not have made."""
    cap = mandate.max_drawdown_pct
    line = (
        f"- max_drawdown_pct: {cap} — PORTFOLIO-level cap on total drawdown, NOT a "
        f"per-trade stop budget. A position of size P% with a stop S% below entry "
        f"contributes about P×S/100 percentage points to portfolio drawdown."
    )
    if not trade_proposal:
        return line
    size = float(trade_proposal.get("size_pct") or 0)
    entry = float(trade_proposal.get("entry") or 0)
    stop = float(trade_proposal.get("stop") or 0)
    dc = drawdown_contribution(size, entry, stop)
    if dc:
        stop_dist = dc.stop_distance_pct
        contrib = dc.contribution_pts
        pct_of_cap = contrib / cap * 100 if cap else 0
        line += (
            f"\n  Reference position (risk-tier ceiling {size:.1f}% size, entry "
            f"{entry:.2f}, stop {stop:.2f}) → stop {stop_dist:.1f}% below entry → "
            f"portfolio-drawdown contribution ≈ {contrib:.2f} pt of the {cap:.0f} pt "
            f"cap (~{pct_of_cap:.0f}% of it). Size the actual trade against THIS "
            f"figure, not the raw stop distance."
        )
    return line


def build_room_messages(
    *,
    agent_id: AgentId,
    mandate: Mandate,
    user_id: Any = None,
    ticker: str,
    profile: dict[str, Any],
    transcript: list[AgentMessage],
    alpaca_snapshot: str | None = None,
    plan: Any = None,
    trade_proposal: dict[str, Any] | None = None,
    halal_universe: Any = None,
) -> tuple[str, list[ChatMessage]]:
    """Compose (system_prompt, [user_message]) for one agent's Room turn.

    The Portfolio Manager is the one agent whose output is parsed back into
    a structured `Verdict` (DEF056) — it gets `_PM_VERDICT_FORMAT` instead of
    `_PROSE_FORMAT` and no forced action; `enforce_safety_floor()` vetoes its
    decision afterward, it doesn't dictate it beforehand.

    `alpaca_snapshot` is a pre-formatted text block from
    alpaca_service.snapshot_text(); injected after user_overlay when set.

    `plan` gates the Decision Journal lookback window (DEF054/DEF055) for
    Bull/Bear Researcher — same retention-by-plan rule journal_store
    already applies everywhere else it's read.

    `halal_universe` is the run's `HalalUniverse` (`_RoomContext.halal_universe`) —
    the same object `enforce_safety_floor` decides against. Passing it here is what
    lets the agents narrate the sourced verdict for `ticker` instead of a bare flag
    (CR069); a Room turn that omits it makes the overlay say the screen could not be
    attached, which is the loud degrade, not a silent one.
    """
    base = build_agent_prompt(
        agent_id,
        mandate,
        user_id=user_id,
        alpaca_snapshot=alpaca_snapshot,
        halal_universe=halal_universe,
        ticker=ticker,
    )
    phase = _PHASE_FOR_AGENT[agent_id]
    length = _LENGTH_GUIDE[agent_id]
    transcript_text = _format_transcript(transcript)
    profile_block = _format_profile(profile)

    journal_note = ""
    if agent_id in (AgentId.BULL_RESEARCHER, AgentId.BEAR_RESEARCHER):
        journal_block = build_journal_context_block(user_id, ticker, plan or Plan.FLOOR_PASS)
        if journal_block:
            journal_note = f"\n\n{journal_block}\n"

    format_instruction = _PM_VERDICT_FORMAT if agent_id == AgentId.PORTFOLIO_MANAGER else _PROSE_FORMAT

    # DEF066: only agents that judge the proposed trade (RISK debators, the PM's
    # VERDICT) get the derived contribution figure; earlier phases have no
    # proposal yet, so they see the portfolio-cap clarification only.
    proposal = trade_proposal if phase in ("RISK", "VERDICT") else None
    drawdown_line = _drawdown_snapshot_line(mandate, proposal)

    room_addition = (
        f"\n\n─── CONVENE THE ROOM — {phase} PHASE ───\n"
        f"Ticker: {ticker}\n"
        f"{profile_block}\n"
        f"\n"
        f"User mandate snapshot:\n"
        f"- risk_score: {mandate.risk_score} (1=most conservative, 5=most aggressive)\n"
        f"{drawdown_line}\n"
        f"- locale: {mandate.locale}\n"
        f"\n"
        f"Transcript so far:\n{transcript_text}\n"
        f"{journal_note}"
        f"\nYour turn. Speak as the {agent_id.value.replace('_', ' ').title()}. "
        f"Write {length}. Use specific numbers wherever possible — but ONLY "
        f"numbers from the data block above. Do NOT cite figures (P/E, growth, "
        f"price targets, market cap) from training memory; if a number isn't "
        f"in the block above, qualify your claim or omit it. Build on the "
        f"transcript — do not repeat what's already been said. Do not preface "
        f"with 'As the X' or 'Speaking as'. Speak directly.\n"
        f"{format_instruction}"
    )

    system_prompt = base + room_addition
    user_message = ChatMessage(role="user", content=f"Convene on {ticker}.")
    return system_prompt, [user_message]


# ── Helpers ──────────────────────────────────────────────────────────────


def _format_profile(profile: dict[str, Any]) -> str:
    """A compact ticker fact-sheet the agent can quote from.

    The header labels which fields are live data vs alpha-synthetic so
    the LLM can be honest. Without this the model would quote synthetic
    P/E numbers as if they were fact, or quote stale training-memory
    facts when real numbers were available — both of which we've seen
    in bug reports.

    Granular by design (AT:R57, CR023/CR024): a single profile can now have
    live fundamentals AND live news AND live social sentiment (or any subset
    thereof) at once, so one binary flag can't describe it honestly anymore.
    Macro/Fed tone and the sector-earnings half of forward catalyst had no
    real source at all and were removed at source (CR038) rather than kept
    around with a disclosure the agents ignored 70% of the time — only the
    real FOMC-date half of forward catalyst remains.
    """
    fundamentals_live = profile.get("data_source") == "yfinance_live"
    technicals_live = profile.get("technicals_source") == "live"
    news_live = profile.get("news_source") == "live"
    social_live = profile.get("social_source") == "live"

    header_lines = ["Data source disclosure — some fields below are real, some are not:"]
    if fundamentals_live:
        header_lines.append(
            "- Numeric fundamentals (price, P/E, growth, FCF, range): LIVE "
            "from Yahoo Finance as of this call."
        )
    else:
        header_lines.append(
            "- Numeric fundamentals (price, P/E, growth, FCF, range): alpha "
            "simulation scaffolding — NOT live market data."
        )
    if technicals_live:
        header_lines.append(
            "- RSI, trend, volume, support/breakout: LIVE, computed from "
            "real yfinance price history as of this call. No MACD, "
            "moving-average crossover signal, or Bollinger Bands are "
            "computed — do not cite them."
        )
    else:
        header_lines.append(
            "- RSI, trend, volume, support/breakout: alpha simulation "
            "scaffolding — NOT computed from real price history."
        )
    if news_live:
        header_lines.append(
            "- Recent catalyst/headline: LIVE, real news as of this call "
            "(publisher + recency shown below). Some headlines may carry a "
            "sentiment tag; treat it as one input, not a verdict."
        )
    else:
        header_lines.append(
            "- Recent catalyst/headline: alpha simulation scaffolding — NOT "
            "a live news feed."
        )
    if social_live:
        header_lines.append(
            "- Retail sentiment/mention/community fields: LIVE, real Reddit "
            "aggregate data as of this call (Reddit only — no Twitter/X, "
            "StockTwits, Google Trends, or Discord data exists)."
        )
    else:
        header_lines.append(
            "- Retail sentiment/mention/influencer fields: alpha simulation "
            "scaffolding — NOT a live social feed."
        )
    header_lines.append(
        "- Forward catalyst: the FOMC decision countdown below is REAL, "
        "from the Fed's published calendar."
    )
    header = "\n".join(header_lines)

    lines = [
        header,
        "",
        f"Reference price: ${profile.get('base_price')}",
        f"P/E: {profile.get('pe')}",
        f"TTM revenue growth: {profile.get('rev_growth')}%, profit margin: {profile.get('profit_margin')}%",
        _net_position_line(profile),
        f"RSI: {profile.get('rsi')} ({profile.get('rsi_tone')}), trend: {profile.get('trend')}",
        # DEF074: the recent-range floor is the computed technical support
        # (profile['support'], the 50-day min that compute_technicals produced and
        # the 1-on-1 path already shows) — NOT the 52-week low, which was being
        # rendered here while `support` was computed and silently dropped. The
        # 52-week range stays as explicit context.
        f"Recent range: ${profile.get('support')}–${profile.get('breakout')} "
        f"(52-week: ${profile.get('low')}–${profile.get('high')})",
        f"Volume: {profile.get('volume_tone')}",
        _catalyst_line(profile),
        f"Retail sentiment: {profile.get('sentiment_tone')} ({profile.get('sentiment_score')})",
    ]
    lines += _social_detail_lines(profile)
    for extra in (_valuation_line(profile), _sector_line(profile),
                  _capital_allocation_line(profile), _analyst_line(profile)):
        if extra:
            lines.append(extra)
    if profile.get("next_earnings_date"):
        lines.append(
            f"Next earnings (LIVE): {profile['next_earnings_date']}"
            + (f" ({profile['next_earnings_quarter']})" if profile.get("next_earnings_quarter") else "")
            + (f", consensus EPS est. ${profile['next_earnings_eps_estimate']}"
               if profile.get("next_earnings_eps_estimate") is not None else "")
        )
    return "\n".join(lines)


def _social_detail_lines(profile: dict[str, Any]) -> list[str]:
    """The live-Reddit fields the Adanos pipeline computes and _format_profile used to
    DROP (DEF096): mention volume + trend, buzz score + numeric bullish/bearish split,
    and the most-active communities — the exact Inputs the Social Media Analyst's job
    names (content/agents/social_media_analyst.md:16,23). In the Room only tone + score
    were rendered, so the analyst reached for a price-volume figure it wasn't given.

    Rendered only when social is LIVE — the synthetic path surfaces nothing (the
    data-source disclosure header already declares social live/not-live, so no
    fabricated social numbers leak; CR040). These are pre-formatted upstream by the
    Adanos formatters (format_mention_trend / format_pattern / format_community_read) —
    rendered verbatim as indented detail under 'Retail sentiment:', never recomputed."""
    if profile.get("social_source") != "live":
        return []
    out: list[str] = []
    if profile.get("mention_trend"):
        out.append(f"  Mentions: {profile['mention_trend']}")
    if profile.get("pattern"):
        out.append(f"  {profile['pattern']}")
    if profile.get("influencer_take"):
        out.append(f"  Communities: {profile['influencer_take']}")
    return out


def _net_position_line(profile: dict[str, Any]) -> str:
    """Balance-sheet line, sign-aware: net cash vs net debt (never 'Net cash: $-42000M')."""
    phrase = net_position_phrase(profile.get("net_cash"))
    if phrase is None:
        return "Balance sheet: net cash not available"
    return phrase[:1].upper() + phrase[1:]


def _valuation_line(profile: dict[str, Any]) -> str | None:
    """Real valuation multiples beyond P/E (DEF053). None when nothing live —
    no fabricated peer/sector multiple is ever shown."""
    parts = []
    if profile.get("price_to_sales"):
        parts.append(f"P/S {profile['price_to_sales']}x")
    if profile.get("ev_to_ebitda"):
        parts.append(f"EV/EBITDA {profile['ev_to_ebitda']}x")
    if profile.get("peg_ratio"):
        parts.append(f"PEG {profile['peg_ratio']}")
    if profile.get("fcf_yield") is not None:
        parts.append(f"FCF yield {profile['fcf_yield']}%")
    if not parts:
        return None
    return "Valuation (LIVE): " + ", ".join(parts)


def _sector_line(profile: dict[str, Any]) -> str | None:
    """Real sector/industry classification (DEF053) — replaces the old
    always-fake numeric `sector_pe`; this is a category, not a fabricated
    peer-average P/E (yfinance has no peer-basket P/E to compute one from)."""
    if not profile.get("sector"):
        return None
    return f"Sector/industry (LIVE): {profile['sector']} / {profile.get('industry', '—')}"


def _capital_allocation_line(profile: dict[str, Any]) -> str | None:
    """Real dividend yield only (DEF053) — buybacks/M&A have no yfinance
    field and stay undisclosed rather than fabricated."""
    if profile.get("dividend_yield") is None:
        return None
    return f"Dividend yield (LIVE): {profile['dividend_yield']}% (buybacks/M&A: not available, not claimed)"


def _analyst_line(profile: dict[str, Any]) -> str | None:
    """Real analyst consensus (DEF053) — the closest honest proxy for
    'forward guidance' available. Explicitly labeled as the Street's view,
    not the company's own guidance (which yfinance doesn't expose)."""
    if not profile.get("analyst_target_price") and not profile.get("analyst_rating"):
        return None
    return (
        f"Analyst consensus (LIVE, Street view — NOT company guidance): "
        f"{profile.get('analyst_rating', '—')}, target ${profile.get('analyst_target_price', '—')}"
    )


def _catalyst_line(profile: dict[str, Any]) -> str:
    from app.services.news_context import format_headline

    line = f"Catalysts — recent: {profile.get('catalyst')}"
    extra_headlines = (profile.get("news_headlines") or [])[1:]
    if extra_headlines:
        extra = "; ".join(format_headline(h) for h in extra_headlines)
        line += f"; other recent coverage: {extra}"
    line += f"; forward (REAL, Fed's published calendar): {profile.get('forward_catalyst')}"
    return line


def _format_transcript(transcript: list[AgentMessage]) -> str:
    if not transcript:
        return "(You are first to speak.)"
    lines: list[str] = []
    for m in transcript:
        aid = m.agent_id.value if hasattr(m.agent_id, "value") else str(m.agent_id)
        lines.append(f"[{aid}] {m.content}")
    return "\n".join(lines)
