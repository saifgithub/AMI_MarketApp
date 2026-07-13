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
    "Respond with ONLY a single JSON object, no prose outside it and no "
    "code fence needed, shaped exactly like:\n"
    '{"action": "APPROVE" | "PASS",\n'
    ' "size_pct": <number, required if APPROVE — position size as % of portfolio>,\n'
    ' "entry": <number, required if APPROVE>,\n'
    ' "stop": <number, required if APPROVE>,\n'
    ' "target": <number, required if APPROVE>,\n'
    ' "horizon_days": <integer, required if APPROVE>,\n'
    ' "narration": "<3-4 sentences, your rationale, written for the user>"}\n'
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
    """
    base = build_agent_prompt(agent_id, mandate, user_id=user_id, alpaca_snapshot=alpaca_snapshot)
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

    room_addition = (
        f"\n\n─── CONVENE THE ROOM — {phase} PHASE ───\n"
        f"Ticker: {ticker}\n"
        f"{profile_block}\n"
        f"\n"
        f"User mandate snapshot:\n"
        f"- risk_score: {mandate.risk_score} (1=most conservative, 5=most aggressive)\n"
        f"- max_drawdown_pct: {mandate.max_drawdown_pct}\n"
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
    Forward catalyst / macro / Fed tone are the one subset with no real
    source at all (no macro-calendar feed exists) — those stay unconditionally
    synthetic regardless of what else is live.
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
        "- Forward catalyst, macro/Fed tone: ALWAYS alpha simulation "
        "scaffolding. No real macro-calendar feed is connected in this app. "
        "Treat these as a deterministic scenario for educational debate — "
        "never present them as real."
    )
    header = "\n".join(header_lines)

    lines = [
        header,
        "",
        f"Reference price: ${profile.get('base_price')}",
        f"P/E: {profile.get('pe')}",
        f"TTM revenue growth: {profile.get('rev_growth')}%, FCF margin: {profile.get('fcf_margin')}%",
        f"Net cash: {profile.get('net_cash')}M",
        f"RSI: {profile.get('rsi')} ({profile.get('rsi_tone')}), trend: {profile.get('trend')}",
        f"Recent range: ${profile.get('low')}–${profile.get('high')}, "
        f"breakout level: ${profile.get('breakout')}",
        f"Volume: {profile.get('volume_tone')}",
        _catalyst_line(profile),
        f"Macro (synthetic, illustrative): {profile.get('macro_tone')}; "
        f"Fed (synthetic, illustrative): {profile.get('fed_tone')}",
        f"Retail sentiment: {profile.get('sentiment_tone')} ({profile.get('sentiment_score')})",
    ]
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
    line += (
        f"; forward (synthetic, illustrative — no real macro/earnings-"
        f"calendar feed): {profile.get('forward_catalyst')}"
    )
    return line


def _format_transcript(transcript: list[AgentMessage]) -> str:
    if not transcript:
        return "(You are first to speak.)"
    lines: list[str] = []
    for m in transcript:
        aid = m.agent_id.value if hasattr(m.agent_id, "value") else str(m.agent_id)
        lines.append(f"[{aid}] {m.content}")
    return "\n".join(lines)
