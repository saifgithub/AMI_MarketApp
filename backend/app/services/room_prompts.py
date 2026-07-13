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
from app.services.agent_prompts import build_agent_prompt
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
    AgentId.PORTFOLIO_MANAGER: "3–4 sentences (verdict rationale; the action itself comes from the deterministic safety-floor check, not from you)",
}


# ── Public ───────────────────────────────────────────────────────────────


def build_room_messages(
    *,
    agent_id: AgentId,
    mandate: Mandate,
    user_id: Any = None,
    ticker: str,
    profile: dict[str, Any],
    transcript: list[AgentMessage],
    pm_predetermined_action: str | None = None,
    alpaca_snapshot: str | None = None,
) -> tuple[str, list[ChatMessage]]:
    """Compose (system_prompt, [user_message]) for one agent's Room turn.

    `pm_predetermined_action` is set only when this agent is the PM and
    the deterministic safety floor has already produced an APPROVE or
    REJECT decision. The PM's LLM call writes the *prose rationale*
    around that action — it cannot override it.

    `alpaca_snapshot` is a pre-formatted text block from
    alpaca_service.snapshot_text(); injected after user_overlay when set.
    """
    base = build_agent_prompt(agent_id, mandate, user_id=user_id, alpaca_snapshot=alpaca_snapshot)
    phase = _PHASE_FOR_AGENT[agent_id]
    length = _LENGTH_GUIDE[agent_id]
    transcript_text = _format_transcript(transcript)
    profile_block = _format_profile(profile)

    pm_note = ""
    if agent_id == AgentId.PORTFOLIO_MANAGER and pm_predetermined_action is not None:
        pm_note = (
            f"\n\nDETERMINISTIC SAFETY-FLOOR RESULT: {pm_predetermined_action}.\n"
            "Your job is to write the rationale prose explaining this verdict. "
            "Do NOT contradict the action above. If APPROVE, explain why the "
            "synthesis defends the position size. If REJECT, name the specific "
            "mandate rule that was violated (already enumerated in the verdict "
            "object you will see surfaced to the user).\n"
        )

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
        f"{pm_note}"
        f"\nYour turn. Speak as the {agent_id.value.replace('_', ' ').title()}. "
        f"Write {length}. Use specific numbers wherever possible — but ONLY "
        f"numbers from the data block above. Do NOT cite figures (P/E, growth, "
        f"price targets, market cap) from training memory; if a number isn't "
        f"in the block above, qualify your claim or omit it. Build on the "
        f"transcript — do not repeat what's already been said. Do not preface "
        f"with 'As the X' or 'Speaking as'. Speak directly.\n"
        f"\nFormat: lead with a one-sentence thesis, then short bullet "
        f"points for supporting evidence. Use **bold** for key metrics "
        f"(numbers, levels, deadlines). Plain text otherwise — no headings, "
        f"no tables, no code fences. The Markdown is rendered live in the app."
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
        f"P/E: {profile.get('pe')} (sector ~{profile.get('sector_pe')})",
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
    if profile.get("next_earnings_date"):
        lines.append(
            f"Next earnings (LIVE): {profile['next_earnings_date']}"
            + (f" ({profile['next_earnings_quarter']})" if profile.get("next_earnings_quarter") else "")
        )
    return "\n".join(lines)


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
