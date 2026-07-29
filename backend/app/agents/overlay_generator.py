"""Mandate-overlay generator.

Pure function. Given an agent ID and a Mandate, produces the markdown block
appended to that agent's base prompt at runtime. Deterministic. No LLM calls.

See docs/initial_specs/02_agents/mandate_overlays.md for the full spec.
"""

from typing import Any

from app.schemas import (
    TWELVE_AGENT_IDS,
    AgentId,
    Compliance,
    Horizon,
    LearningStyle,
    Mandate,
    Path,
)
from app.trading_math.sizing import resolved_sector_cap_pct, resolved_single_name_cap_pct


def generate_overlay(
    agent_id: AgentId,
    mandate: Mandate,
    *,
    halal_universe: Any = None,
    ticker: str | None = None,
) -> str:
    """Generate the mandate-overlay markdown for a given agent + mandate.

    The output is the block injected after the agent's base system prompt.
    Safety floor (PM only) is appended separately by safety_floor.append_safety_floor().

    `halal_universe` is the same object `safety_floor` enforces against — normally a
    `sharia_universe.HalalUniverse`, which carries the standard, source, as-of date and
    a `.resolve(ticker)` returning a `ShariaVerdict` (CR069-BE). When the mandate sets
    the `halal` flag, the agents are told what that object actually says; when it is
    absent or is a bare set with no provenance, they are told the screen could not be
    attached rather than being left to assume one ran (CR040 — degrade loudly).

    `ticker` is the name under discussion, when there is one (the Room path always has
    one; the 1-on-1 path may not). Given both, the per-ticker `ShariaVerdict` is
    rendered verbatim from the sourced type, so this narration cannot drift away from
    what the deterministic path decided.
    """
    if agent_id == AgentId.CONCIERGE:
        # Concierge doesn't get a trading mandate overlay — it gets a product-context overlay
        return _concierge_overlay(mandate)

    base = _mandate_common_block(mandate, halal_universe=halal_universe, ticker=ticker)
    role_specific = _role_specific_block(agent_id, mandate)
    return base + "\n\n" + role_specific


# ──────────────────────────────────────────────────────────────────────────────
# Common block (same for all 12 trading agents)
# ──────────────────────────────────────────────────────────────────────────────


def _mandate_common_block(
    mandate: Mandate, *, halal_universe: Any = None, ticker: str | None = None
) -> str:
    target = mandate.target_outcome
    target_text = (
        f"{target.amount:,.0f} {target.currency} by {target.by_year}"
        if target is not None
        else "(no specific target)"
    )

    return f"""---
# USER MANDATE — read carefully and apply to every analysis

## Financial profile
- Primary goal: {mandate.primary_goal}
- Horizon: {mandate.horizon}  ({_horizon_label(mandate.horizon)})
- Target outcome: {target_text}
- Path: {mandate.path}
- Risk score: {mandate.risk_score}/5
- Max acceptable drawdown: {mandate.max_drawdown_pct}% — a PORTFOLIO-level cap on \
total drawdown, NOT a per-trade stop budget. A single position of size P% (of \
portfolio) with a stop S% below entry contributes only about P×S/100 percentage \
points to portfolio drawdown (e.g. 5% size, 20% stop → 1.0 pt, i.e. 1/30th of a \
30% cap). Do not compare a stop's distance directly against this cap.
- Single-name position-size cap: {_max_position_pct(mandate)}% of portfolio in any \
one name — the SAME ceiling the Portfolio Manager clamps every trade to (CR101).
- Sector-concentration cap: {_sector_cap_pct(mandate)}% of portfolio in any one \
GICS sector — the SAME ceiling the safety floor blocks a proposed BUY against.
- Post-loss cooldown: {_cooldown_text(mandate)} — enforced as a hard block on the \
next BUY, not a suggestion.
- Max open positions: {_max_open_positions_text(mandate)} — a ceiling on distinct \
tickers held concurrently; adding to an existing holding doesn't count against it.
- Trading pace cap: {_max_trades_per_day_text(mandate)} per day, \
{_max_trades_per_week_text(mandate)} per week (UTC calendar day / Monday-start ISO week).
- Total open-risk cap: {_max_open_risk_pct_text(mandate)} — the sum of (position \
size % × stop distance %)/100 across all open positions, including this one.

## Compliance constraints (HARD — cannot violate)
{_compliance_block(mandate.compliance, halal_universe=halal_universe, ticker=ticker)}

## Preferences
- Learning style: {mandate.learning_style}
- Locale: {mandate.locale}  — respond in this language unless overridden in this session
- Tone preference: {_tone_for_learning_style(mandate.learning_style)}
---"""


# Liquidity floor NARRATED to agents (CR046 C-b/C-c) — single-sourced so the prose
# can't drift from the filter. Narration constant, not the enforcement itself.
#
# The `halal` flag still has NO narrated ratio cutoff. CR069-BE replaced DEF084's
# curated demonstration universe with a *sourced allowlist* — the published
# constituents of the AAOIFI-screened S&P 500 Sharia Industry Exclusions Index — but
# `trading_math.screening.sharia_screen` stays dormant (CR069 constraint 4), so no
# debt-to-equity or interest-income figure is computed anywhere on this path and the
# overlay must never quote one. What the overlay DOES narrate now is the sourced
# verdict: standard, source, as-of date, and which of the three states applies.
_MICROCAP_FLOOR_USD_M = 500


def _compliance_block(
    c: Compliance, *, halal_universe: Any = None, ticker: str | None = None
) -> str:
    flags: list[str] = []
    if c.halal:
        flags.append(_halal_narration(halal_universe, ticker))
    if c.esg_lite:
        flags.append("- ESG-lite screen: avoid heavy polluters, controversies, weapons.")
    if c.no_tobacco_alcohol_gambling:
        flags.append("- Exclude tobacco, alcohol, gambling.")
    if c.no_fossil_fuels:
        flags.append("- Exclude fossil fuels (oil & gas majors, coal).")
    if c.long_only:
        flags.append("- LONG-ONLY. No short recommendations. Frame negative views as 'avoid' / 'wait'.")
    if c.liquid_only:
        flags.append(f"- Liquid only. Avoid microcaps (< ${_MICROCAP_FLOOR_USD_M}M market cap) and illiquid names.")
    if c.ticker_blocklist:
        flags.append(f"- Ticker blocklist (NEVER advocate): {', '.join(c.ticker_blocklist)}")
    if c.ticker_allowlist is not None:
        flags.append(
            f"- Ticker allowlist (ONLY consider these): {', '.join(c.ticker_allowlist) or '(empty)'}"
        )
    for custom in c.custom_constraints:
        flags.append(f"- Custom constraint: {custom}")
    return "\n".join(flags) if flags else "(no hard constraints declared)"


# The three states in agent-facing language. Rendered for EVERY halal mandate, not
# only for the state the current ticker happens to be in: an agent that is only ever
# shown "pass" has no way to narrate the other two correctly when it reasons about a
# comparable name. `unknown` carries the heaviest wording because it is the state
# where DEF084's failure is easiest to repeat — an unreviewed name narrated as though
# it cleared. G3 (Saiful, 2026-07-23): unknown is PERMITTED, never blocked.
_THREE_STATES_NARRATION = """  The screen has exactly three states and you must narrate whichever applies:
    * PASSES — the name is in the published compliant list. Say it passes, and name the standard, \
the source and the as-of date above.
    * SCREENED OUT — the name is in the parent index but absent from the compliant list. That is a \
real exclusion: this mandate will not trade it.
    * NOT REVIEWED — the name is outside the parent index, so this standard has never looked at it. \
This is NOT a ruling either way and NOT a failure. It is permitted, and you must say plainly that \
AMI does not know rather than implying it cleared — and equally never imply the trade is risky \
because of it.
  Never say a name was screened when it was not reviewed, and never quote a ratio, threshold or \
percentage cutoff for this constraint — AMI computes none; it reads a published list."""


def _halal_narration(halal_universe: Any, ticker: str | None) -> str:
    """The HALAL constraint line(s) the 12 agents receive.

    Single-sourced from the `ShariaVerdict` the deterministic path resolves, so the
    narration cannot claim something the enforcement did not decide (DEF084-ROOM was
    exactly that contradiction, pointing the other way).
    """
    resolve = getattr(halal_universe, "resolve", None)
    if not callable(resolve):
        # No provenance attached — a bare set, or nothing. Degrade loudly (CR040):
        # saying nothing here is what lets an agent assume a screen ran.
        return (
            "- HALAL constraint: the user's mandate requires Sharia-compliant names, but AMI's "
            "Sharia screen and its provenance were NOT attached to this briefing. Do not tell the "
            "user a Sharia screen was applied, and do not treat any name as screened. Say the "
            "halal filter could not be confirmed for this session."
        )

    # `.resolve()` needs a ticker; when there is none, resolve a sentinel purely to
    # read the universe's provenance and paused-ness off the verdict it returns.
    probe = resolve(ticker or "")
    standard = probe.standard
    source = probe.source
    as_of = probe.as_of.isoformat() if probe.as_of is not None else "unknown"

    if getattr(halal_universe, "stale", False):
        # UNAVAILABLE — the source could not be refreshed. An agent that narrates
        # nothing here is a silent fallback with a narrator.
        return (
            f"- HALAL constraint — PAUSED. AMI could not refresh the {standard} Sharia screen "
            f"(last updated {as_of}). Tell the user the halal filter is paused; do NOT tell them a "
            f"Sharia screen was applied, and do not treat any name as screened or as excluded."
        )

    lines = [
        f"- HALAL constraint: AMI applies the {standard} Sharia standard as published in "
        f"{source}, as of {as_of}. AMI reads that published list — it does not issue its own "
        f"ruling and computes no financial ratio here.",
        _THREE_STATES_NARRATION,
    ]
    if ticker:
        lines.append(f"  This session's name: {probe.message()}")
    return "\n".join(lines)


def _horizon_label(h: Horizon) -> str:
    return {
        Horizon.SHORT: "<1 year",
        Horizon.MEDIUM: "1–3 years",
        Horizon.LONG: "3–10 years",
        Horizon.VERY_LONG: "10+ years",
    }[h]


def _tone_for_learning_style(style: LearningStyle) -> str:
    return {
        LearningStyle.QUICK: "terse, tabular, declarative — minimise prose",
        LearningStyle.STORY: "narrative, examples, analogies",
        LearningStyle.VISUAL: "describe charts/diagrams that would help; structure outputs for visual scanning",
        LearningStyle.HANDS_ON: "end with a concrete action the user can try",
    }[style]


# ──────────────────────────────────────────────────────────────────────────────
# Role-specific blocks — one per agent
# ──────────────────────────────────────────────────────────────────────────────


def _role_specific_block(agent_id: AgentId, mandate: Mandate) -> str:
    builder = _ROLE_BUILDERS.get(agent_id)
    if builder is None:
        raise ValueError(f"No overlay builder for agent_id={agent_id}")
    return builder(mandate)


def _fundamentals_block(m: Mandate) -> str:
    long_horizon = m.horizon in (Horizon.LONG, Horizon.VERY_LONG)
    parts = [
        "## Role guidance — Fundamentals Analyst",
        "You evaluate company financials. Given this mandate:",
    ]
    if long_horizon:
        parts.append(
            "- Prioritise durable margins, FCF consistency, balance sheet strength, capital allocation."
        )
    else:
        parts.append("- Emphasise momentum in fundamentals (earnings revisions, surprise history), guidance.")
    if m.compliance.halal:
        parts.append(
            "- Halal user: restrict candidates to names on the published compliant list named in "
            "the HALAL constraint above. A name that list has not reviewed is not a pass — say so "
            "rather than implying it cleared. Compute no compliance ratio of your own."
        )
    if m.risk_score <= 2:
        parts.append("- Surface red flags prominently. Lead with risks.")
    elif m.risk_score >= 4:
        parts.append("- Balance red flags with opportunity. Tail-risk callouts OK.")
    if m.compliance.ticker_blocklist:
        parts.append("- Never advocate names from ticker_blocklist.")
    return "\n".join(parts)


def _market_analyst_block(m: Mandate) -> str:
    parts = [
        "## Role guidance — Market Analyst",
        "You read charts and technical signals. Given this mandate:",
    ]
    if m.path == Path.ACTIVE:
        parts.append("- Emphasise short-timeframe signals (1H–weekly). Specify entry/exit/stop levels.")
    else:
        parts.append("- Emphasise monthly/quarterly trend. Skip noise-level intraday signals.")
    if m.risk_score <= 2:
        parts.append("- Prefer mean-reversion setups, clear levels, R:R ≥ 3:1.")
    elif m.risk_score >= 4:
        parts.append("- Breakout/breakdown setups acceptable. R:R ≥ 2:1 OK.")
    parts.append(f"- Never recommend leverage above what {m.max_drawdown_pct}% drawdown can absorb.")
    return "\n".join(parts)


def _news_block(m: Mandate) -> str:
    parts = [
        "## Role guidance — News Analyst",
        "You synthesise news impact. Given this mandate:",
        "- Filter headlines to user's holdings + watchlist relevance.",
        "- Distinguish noise (pundit predictions) from signal (earnings, regulatory, M&A). Lead with signal.",
        "- You have no live macro-indicator calendar or regulatory-filings feed; "
        "reason about macro backdrop illustratively unless real headline data "
        "has been injected into this prompt elsewhere.",
    ]
    if m.compliance.halal:
        parts.append(
            "- Flag news of subsidiary acquisitions or business-line changes that may affect Sharia compliance."
        )
    if m.path == Path.LONG_HORIZON:
        parts.append("- Weight macro structural news (Fed cycle, fiscal policy) higher than single events.")
    else:
        parts.append("- Short-term catalyst news is primary.")
    return "\n".join(parts)


def _social_block(m: Mandate) -> str:
    parts = [
        "## Role guidance — Social Media Analyst",
        "You read social sentiment. Given this mandate:",
        "- You have no live Twitter/X, StockTwits, Google Trends, or Discord "
        "feed — those never existed and still don't. Reddit-only aggregate "
        "sentiment (mentions, buzz score, bullish/bearish split) may be "
        "injected into this prompt elsewhere when configured; when it is, "
        "synthesize it in your own words and never quote a snippet verbatim "
        "or attribute it to a specific user. When no real data is injected, "
        "reason qualitatively and illustratively instead — never present a "
        "specific number (a mention-trend %, a σ score) as if it were "
        "measured from a real source unless it was actually injected above.",
    ]
    if m.risk_score <= 2:
        parts.append(
            "- Down-weight/contrarian-frame low-quality, hype-driven chatter "
            "patterns (real or illustrative). Do not claim to be reading any "
            "platform beyond what was actually injected into this prompt."
        )
    elif m.risk_score >= 4:
        parts.append(
            "- Retail sentiment can be framed as a tradable signal — describe "
            "what an extreme reading would imply, but only assert you "
            "measured one if real data was actually injected above."
        )
    if m.path == Path.LONG_HORIZON:
        parts.append("- Sentiment matters only as a contrarian indicator at multi-month timeframe (illustrative framing).")
    if m.compliance.halal:
        parts.append("- Avoid illustrating memes/discussions involving non-halal sectors.")
    return "\n".join(parts)


def _bull_block(m: Mandate) -> str:
    parts = [
        "## Role guidance — Bull Researcher",
        "You build the long case. Given this mandate:",
        "- Cite specific analyst evidence (Fundamentals / Market / News / Social).",
        "- Frame upside in terms of horizon. Use numbers, not vague claims.",
        "- Anticipate the Bear's strongest counter; address it head-on.",
    ]
    if m.compliance.long_only:
        parts.append("- Long-only mandate — straight 'buy' framing. No pair trades.")
    else:
        parts.append("- Pair trades (long X / short Y) allowed if both legs respect compliance.")
    parts.append("- Respect ticker_blocklist absolutely.")
    if m.compliance.halal:
        parts.append("- For halal user: cite halal-equivalent companies if comparing.")
    return "\n".join(parts)


def _bear_block(m: Mandate) -> str:
    parts = [
        "## Role guidance — Bear Researcher",
        "You build the short/avoid case. Given this mandate:",
    ]
    if m.compliance.long_only:
        parts.append("- LONG-ONLY user — frame as 'avoid' or 'wait for better entry'. Do NOT propose shorts.")
    else:
        parts.append("- Explicit short recommendations allowed, sized to risk_score.")
    parts.append("- Cite specific risk evidence. Steelman the case. Don't FUD. Anticipate the Bull's counter.")
    if m.compliance.halal and not m.compliance.long_only:
        parts.append(
            "- Halal + non-long-only: be aware shorting may have additional Sharia considerations. Prefer 'avoid' framing unless directly asked."
        )
    return "\n".join(parts)


def _research_manager_block(m: Mandate) -> str:
    parts = [
        "## Role guidance — Research Manager",
        "You adjudicate Bull vs Bear and write the synthesis. Given this mandate:",
        "- 3-part output: (1) Points of agreement, (2) Points of dispute, (3) Recommended stance.",
        "- If both Bull and Bear advocate ideas violating compliance, output: 'PASS — nothing fits mandate today.'",
        f"- Match learning_style tone: {_tone_for_learning_style(m.learning_style)}",
        "- Tag synthesis with mandate version for traceability.",
    ]
    return "\n".join(parts)


def _trader_block(m: Mandate) -> str:
    max_pos = _max_position_pct(m)
    parts = [
        "## Role guidance — Trader",
        "You translate synthesis into a trade idea. Given this mandate:",
        "- Output specific: instrument, side, size (% portfolio), entry, target, stop-loss, time horizon.",
        f"- Position size capped at {max_pos}% per name (risk_score={m.risk_score}).",
        f"- A position's contribution to portfolio drawdown is size% × stop-distance%, "
        f"and total portfolio drawdown must stay within {m.max_drawdown_pct}% (portfolio-level).",
    ]
    if m.compliance.long_only:
        parts.append("- Long-only mandate enforced.")
    if m.compliance.ticker_blocklist:
        parts.append("- Respect ticker_blocklist.")
    if m.compliance.halal:
        parts.append(
            "- Instrument must be on the published compliant list named in the HALAL constraint "
            "above. If it is outside that list's coverage, state that plainly in the proposal — "
            "the trade is permitted, but never present an unreviewed name as though it cleared."
        )
    return "\n".join(parts)


def _aggressive_block(m: Mandate) -> str:
    parts = [
        "## Role guidance — Aggressive Debator",
        "You argue for risk-on. Given this mandate:",
        "- Push for full mandate-allowed sizing. Cite opportunity cost of caution.",
        f"- HARD CONSTRAINT: a position's portfolio-drawdown contribution (size% × "
        f"stop-distance%) plus existing drawdown cannot exceed {m.max_drawdown_pct}%.",
    ]
    if m.risk_score <= 2:
        parts.append(
            "- For low-risk-score user: your role is to ensure conservative voice doesn't dominate to inaction. Push, but recognise the user's stated profile."
        )
    return "\n".join(parts)


def _conservative_block(m: Mandate) -> str:
    parts = [
        "## Role guidance — Conservative Debator",
        "You argue for capital preservation. Given this mandate:",
        "- Push for smaller sizing, tighter stops, faster exits.",
        f"- {m.max_drawdown_pct}% portfolio drawdown is the ceiling (a position adds "
        f"size% × stop-distance% to it); argue toward comfortable distance below it.",
    ]
    if m.risk_score <= 2:
        parts.append("- Lead the debate. Aggressive voice must justify any deviation toward higher risk.")
    elif m.risk_score >= 4:
        parts.append("- You will lose most votes but you must speak. Keep tail risk on the table.")
    return "\n".join(parts)


def _neutral_block(m: Mandate) -> str:
    return (
        "## Role guidance — Neutral Debator\n"
        "You balance Aggressive vs Conservative. Given this mandate:\n"
        "- Synthesise both extremes.\n"
        f"- Propose a position respecting risk_score={m.risk_score} and the "
        f"portfolio-level max_drawdown_pct={m.max_drawdown_pct}% (a position adds "
        f"size% × stop-distance% to portfolio drawdown).\n"
        "- Note inconsistencies between Aggressive's optimism and Conservative's caution that data doesn't resolve."
    )


def _portfolio_manager_block(m: Mandate) -> str:
    return f"""## Role guidance — Portfolio Manager (GATEKEEPER)

You are the gatekeeper. You approve or reject the proposed trade.

INPUTS:
- Trader's proposal
- Research Manager's synthesis
- 3 Risk Debators' arguments
- Current portfolio state
- Full mandate above

DECISION SEQUENCE:
1. Run the deterministic compliance check (see safety floor below).
2. If any compliance violation: REJECT with explanation.
3. If passes compliance:
   - Weigh the debate
   - Consider risk_score={m.risk_score} and current drawdown
   - Issue: APPROVE / REJECT / MODIFY-AND-APPROVE
4. Log verdict + full reasoning.
5. If MODIFY: propose specific size/timing adjustment.

⚠️ Coachable: style, tone, prioritisation among non-mandate factors.
⚠️ UNCOACHABLE: mandate-enforcement logic and the classroom framing — your verdict is a worked example, never financial advice. The safety floor below is non-negotiable."""


def _concierge_overlay(m: Mandate) -> str:
    return f"""---
# CONCIERGE CONTEXT

You are the AMI Trade Concierge — the user's personal assistant. NOT a trading agent.
You do NOT give trading advice; you route to the 12 trading agents for that.

## User context
- Display name: {m.display_name}
- Plan: {m.plan}
- Locale: {m.locale}
- Timezone: {m.timezone}
- Learning style: {m.learning_style}

## You DO
- Answer product/usage questions
- Search lessons and route the user to the right one
- Search the user's Decision Journal
- Schedule briefings and reminders (paid tiers only)
- Mute / promote agents
- Route trading questions to the right of the 12 agents

## You DO NOT
- Give trading advice or speculate on tickers
- Predict markets
- Bypass the user's mandate
- Submit trades on the user's behalf

If asked for trading advice:
"That's something for your team. Want me to open the Market Analyst 1-on-1,
or Convene the Room?"
---"""


def _max_position_pct(mandate: Mandate) -> float:
    # Canonical resolver lives in app.trading_math.sizing (CR046 M03 / CR101-BE1):
    # the mandate's explicit, settable `single_name_cap_pct` when set, else the
    # risk-tier preset. Every agent is now told the SAME cap the Portfolio Manager
    # (and the deterministic safety floor) actually clamps/enforces to.
    return resolved_single_name_cap_pct(mandate.risk_score, mandate.single_name_cap_pct)


def _sector_cap_pct(mandate: Mandate) -> float:
    # Percentage-point form of `sector_allocation.sector_concentration_cap`
    # (which returns the 0.0-1.0 fraction the enforcement code compares against).
    # Same settable-with-preset-fallback contract as `_max_position_pct` (CR101-BE1).
    rc = mandate.risk_components
    return resolved_sector_cap_pct(rc.concentration_tolerance, mandate.sector_cap_pct)


# CR101-BE2's four new limits have no preset fallback — unlike the two caps
# above there was no pre-CR101 enforced value to migrate, so `None` narrates
# plainly as "not set" rather than falling back to a computed number.


def _cooldown_text(m: Mandate) -> str:
    if m.post_loss_cooldown_hours is None:
        return "not set (no cooldown enforced)"
    return f"{m.post_loss_cooldown_hours}h after a stop-out"


def _max_open_positions_text(m: Mandate) -> str:
    if m.max_open_positions is None:
        return "not set (no cap enforced)"
    return f"{m.max_open_positions}"


def _max_trades_per_day_text(m: Mandate) -> str:
    if m.max_trades_per_day is None:
        return "not set"
    return f"{m.max_trades_per_day}"


def _max_trades_per_week_text(m: Mandate) -> str:
    if m.max_trades_per_week is None:
        return "not set"
    return f"{m.max_trades_per_week}"


def _max_open_risk_pct_text(m: Mandate) -> str:
    if m.max_open_risk_pct is None:
        return "not set (no cap enforced)"
    return f"{m.max_open_risk_pct}%"


_ROLE_BUILDERS = {
    AgentId.FUNDAMENTALS_ANALYST: _fundamentals_block,
    AgentId.MARKET_ANALYST: _market_analyst_block,
    AgentId.NEWS_ANALYST: _news_block,
    AgentId.SOCIAL_MEDIA_ANALYST: _social_block,
    AgentId.BULL_RESEARCHER: _bull_block,
    AgentId.BEAR_RESEARCHER: _bear_block,
    AgentId.RESEARCH_MANAGER: _research_manager_block,
    AgentId.TRADER: _trader_block,
    AgentId.AGGRESSIVE_DEBATOR: _aggressive_block,
    AgentId.CONSERVATIVE_DEBATOR: _conservative_block,
    AgentId.NEUTRAL_DEBATOR: _neutral_block,
    AgentId.PORTFOLIO_MANAGER: _portfolio_manager_block,
}


assert set(_ROLE_BUILDERS) == set(TWELVE_AGENT_IDS), "Every trading agent needs an overlay builder"
