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
from app.trading_math.risk_limits import (
    resolved_max_open_positions,
    resolved_max_open_risk_pct,
    resolved_max_trades_per_day,
    resolved_max_trades_per_week,
    resolved_post_loss_cooldown_hours,
)
from app.trading_math.sizing import resolved_sector_cap_pct, resolved_single_name_cap_pct


def generate_overlay(
    agent_id: AgentId,
    mandate: Mandate,
    *,
    halal_universe: Any = None,
    ticker: str | None = None,
    classification_universe: Any = None,
    locale_allowed_universe: Any = None,
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

    base = _mandate_common_block(
        mandate, halal_universe=halal_universe, ticker=ticker,
        classification_universe=classification_universe,
        locale_allowed_universe=locale_allowed_universe,
    )
    role_specific = _role_specific_block(agent_id, mandate)
    return base + "\n\n" + role_specific


# ──────────────────────────────────────────────────────────────────────────────
# Common block (same for all 12 trading agents)
# ──────────────────────────────────────────────────────────────────────────────


def _mandate_common_block(
    mandate: Mandate,
    *,
    halal_universe: Any = None,
    ticker: str | None = None,
    classification_universe: Any = None,
    locale_allowed_universe: Any = None,
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
points to portfolio drawdown (e.g. 5% size, 20% stop → 1.0 pt, i.e. 1/{mandate.max_drawdown_pct} \
of your {mandate.max_drawdown_pct}% cap). Do not compare a stop's distance directly against this cap.
- Single-name position-size cap: {_max_position_pct(mandate)}% of portfolio in any \
one name — the SAME ceiling the Portfolio Manager clamps every trade to (CR101).
- Sector-concentration cap: {_sector_cap_pct(mandate)}% of portfolio in any one \
GICS sector — the SAME ceiling the safety floor blocks a proposed BUY against.
- Post-loss cooldown: {_cooldown_text(mandate)}
- Max open positions: {_max_open_positions_text(mandate)} — a ceiling on distinct \
tickers held concurrently; adding to an existing holding doesn't count against it.
- Trading pace cap: {_max_trades_per_day_text(mandate)} per day, \
{_max_trades_per_week_text(mandate)} per week (UTC calendar day / Monday-start ISO week).
- Total open-risk cap: {_max_open_risk_pct_text(mandate)} — the sum of (position \
size % × stop distance %)/100 across all open positions, including this one.

## Compliance constraints (HARD — cannot violate)
{_compliance_block(mandate.compliance, halal_universe=halal_universe, ticker=ticker, classification_universe=classification_universe, locale_allowed_universe=locale_allowed_universe, locale=mandate.locale)}

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
    c: Compliance,
    *,
    halal_universe: Any = None,
    ticker: str | None = None,
    classification_universe: Any = None,
    locale_allowed_universe: Any = None,
    locale: str = "en",
) -> str:
    flags: list[str] = []
    if c.halal:
        flags.append(_halal_narration(halal_universe, ticker))
    if c.esg_lite:
        flags.append(_exclusion_narration(
            classification_universe, ticker, "esg_lite",
            "ESG-lite screen", "a heavy polluter, a controversy name or a weapons maker",
        ))
    if c.no_tobacco_alcohol_gambling:
        flags.append(_exclusion_narration(
            classification_universe, ticker, "sin",
            "Exclude tobacco, alcohol, gambling", "a tobacco, alcohol or gambling name",
        ))
    if c.no_fossil_fuels:
        flags.append(_exclusion_narration(
            classification_universe, ticker, "fossil_fuels",
            "Exclude fossil fuels", "an oil & gas major or a coal name",
        ))
    if c.long_only:
        flags.append("- LONG-ONLY. No short recommendations. Frame negative views as 'avoid' / 'wait'.")
    if c.liquid_only:
        flags.append(f"- Liquid only. Avoid microcaps (< ${_MICROCAP_FLOOR_USD_M}M market cap) and illiquid names.")
    if c.ticker_blocklist:
        flags.append(f"- Ticker blocklist (NEVER advocate): {', '.join(c.ticker_blocklist)}")
    else:
        # CR149 Tier A.4 — state the empty case rather than omitting the line.
        # `_bull_block` tells 18/18 Bull prompts to "Respect ticker_blocklist
        # absolutely" while this branch rendered nothing when the list was empty,
        # and 0 of 216 epoch prompts carried one — so the agent could not tell
        # "there is no blocklist" from "the blocklist was not attached". Absence
        # rendered as silence is the CR040 shape; measured consequence 0/18, so
        # this is cheap correctness, not a fix for an observed failure.
        flags.append("- Ticker blocklist: (none declared)")
    if c.ticker_allowlist is not None:
        flags.append(
            f"- Ticker allowlist (ONLY consider these): {', '.join(c.ticker_allowlist) or '(empty)'}"
        )
    for custom in c.custom_constraints:
        flags.append(f"- Custom constraint: {custom}")
    flags.append(_locale_universe_narration(locale_allowed_universe, ticker, locale))
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


def _locale_universe_narration(
    locale_allowed_universe: Any, ticker: str | None, locale: str
) -> str:
    """CR152 D8 / CR179 Leg 3 — the locale universe, which can veto a trade in
    silence.

    `safety_floor.py:336` blocks any proposal whose ticker is outside this set
    with `blocked_by="locale"`. Twelve agents could argue a name to a sized
    APPROVE with no way to know it was not purchasable at all — the same
    unfollowable-by-construction shape as the microcap rule before CR145 Tier A
    supplied market cap.

    **The empty case is stated, not omitted** (CR149 A.4's rule). `None` means
    no restriction, which is the alpha default — but an agent reading silence
    cannot tell "no restriction" from "the restriction was not attached", and
    those call for different behaviour. Saying which costs one line.
    """
    if locale_allowed_universe is None:
        return (
            "- Tradable universe: no locale restriction is in force this session — "
            "every name AMI can price is available to this user."
        )
    try:
        allowed = {str(x).upper() for x in locale_allowed_universe}
    except TypeError:
        return (
            "- Tradable universe: a locale restriction applies but AMI could not read it. "
            "Do not tell the user a name is unavailable, and do not assume one is available."
        )
    t = (ticker or "").upper().strip()
    if t and t not in allowed:
        return (
            f"- Tradable universe — {t} is NOT available in this user's locale ({locale}), "
            f"out of {len(allowed)} names that are. Any trade in it will be BLOCKED before "
            f"execution. Say so plainly rather than sizing a position that cannot be taken."
        )
    if t:
        return (
            f"- Tradable universe: restricted to the {len(allowed)} names available in this "
            f"user's locale ({locale}). {t} is one of them."
        )
    return (
        f"- Tradable universe: restricted to the {len(allowed)} names available in this "
        f"user's locale ({locale})."
    )


def _exclusion_narration(
    classification_universe: Any,
    ticker: str | None,
    kind_value: str,
    label: str,
    what_it_catches: str,
) -> str:
    """CR179 Leg 3 / CR152 D7 — the sourced sector/industry exclusions, narrated.

    **The largest "we already have it" gap outside the fact sheet.** DEF061 built
    a four-state resolver (PERMITTED / EXCLUDED / UNKNOWN / UNAVAILABLE) over a
    sourced classification of the parent index. It is fetched on **every** run
    (`room_runner.py:3729`), it is **enforced** by the mandate check
    (`room_runner.py:2708`), and it was narrated to **nobody**: this block
    printed the boolean INTENT — *"Exclude fossil fuels (oil & gas majors,
    coal)"* — while the identically-shaped halal constraint two lines up got the
    full sourced three-state treatment.

    That asymmetry is the CR040 shape, and it bites in the same direction
    DEF084-ROOM did. An agent told only *"exclude fossil fuels"*, with no way to
    ask whether THIS name was screened, has two options: assume the screen
    cleared it (which is DEF084's failure exactly) or state a verdict it never
    received. Rendering the state removes the guess.

    Single-sourced from the same object the enforcement resolves against, so the
    narration cannot claim something the deterministic path did not decide —
    the constraint `_halal_narration` was written to satisfy.

    **UNKNOWN carries the heaviest wording, for the same reason it does there.**
    A name outside the parent index was never classified; that is not a ruling,
    not a failure, and not permission dressed up as one.
    """
    resolve = getattr(classification_universe, "resolve", None)
    if not callable(resolve):
        # Degrade loudly (CR040): silence here is what lets an agent assume a
        # screen ran. Same failure mode, same answer, as the halal branch.
        return (
            f"- {label}: the user's mandate requires this exclusion, but AMI's sourced "
            f"classification and its provenance were NOT attached to this briefing. Do not tell "
            f"the user this screen was applied, and do not treat any name as screened or as "
            f"cleared. Say the filter could not be confirmed for this session."
        )
    try:
        from app.schemas.classification import ClassificationKind, ClassificationStatus

        verdict = resolve(ticker or "", ClassificationKind(kind_value))
    except Exception:
        return (
            f"- {label}: AMI could not resolve this screen for this session. Do not tell the "
            f"user it was applied, and do not treat any name as screened."
        )

    as_of = verdict.as_of.isoformat() if getattr(verdict, "as_of", None) else "unknown"
    provenance = f"(source: {verdict.source}, as of {as_of})"
    status = verdict.status

    if status is ClassificationStatus.UNAVAILABLE:
        return (
            f"- {label} — PAUSED. AMI could not refresh the classification behind this screen "
            f"(last updated {as_of}). Tell the user this filter is paused; do NOT tell them it "
            f"was applied, and do not treat any name as screened or as excluded."
        )
    if status is ClassificationStatus.EXCLUDED:
        return (
            f"- {label} — {ticker or 'this name'} is SCREENED OUT {provenance}. AMI classified it "
            f"as {what_it_catches}. This mandate will not trade it; say so plainly and do not "
            f"argue the position."
        )
    if status is ClassificationStatus.PERMITTED:
        return (
            f"- {label} — {ticker or 'this name'} PASSES this screen {provenance}. It was "
            f"classified and is not {what_it_catches}."
        )
    return (
        f"- {label} — {ticker or 'this name'} was NOT REVIEWED against this screen: it sits "
        f"outside the classified parent set {provenance}, so AMI has never looked at it. That is "
        f"NOT a ruling either way and NOT a failure. It is permitted. Say plainly that AMI does "
        f"not know rather than implying it cleared — and equally never imply the trade is risky "
        f"because of it."
    )


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
        # CR179 Leg 1 — "tabular" contradicted the Room's own format block
        # ("Plain text otherwise — no headings, no tables", room_prompts.py:312)
        # in every Room prompt this tone reached. Every CR145–CR156 row declared
        # it out of scope as "CR145's", and CR145 Tier B shipped without it, so
        # it sat live and unowned. The intent — terse, declarative, minimal
        # prose — survives; only the format instruction the Room forbids is gone.
        LearningStyle.QUICK: "terse, declarative — short lines, minimise prose",
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
    # CR146 Tier A — four demands deleted here, each because the system cannot
    # honour it. Every one measured 0/18 or 1/18 on the 2026-08-07 epoch, so the
    # acceptance is that nothing else moves.
    #
    # 1. The ACTIVE branch asked for "short-timeframe signals (1H–weekly)" and
    #    "entry/exit/stop levels" six lines under a base prompt that says "No
    #    intraday (1H) timeframe — only the daily bars actually fetched", and
    #    `_HISTORY_PERIOD = "3m"` fetches daily bars only. Unexercised on that
    #    epoch (0/18 prompts — all 18 users were long_horizon), so this is a
    #    code-read finding, not a measured failure. Deleted anyway: it is a
    #    contradiction waiting for the first active-path user.
    # 2/3. The risk-tier R:R floors (0/18 and 1/18) go with the R:R demand
    #    itself, which Tier A removes from `market_analyst.md` — a floor on a
    #    ratio the agent is no longer asked to produce is orphaned instruction.
    # 4. The leverage line appeared in 18/18 prompts and **the simulator has no
    #    leverage or margin concept at all** — no match for leverage/margin/borrow
    #    in `sim_engine.py` or the models. An instruction about a capability the
    #    product does not have is prompt weight with a hallucination surface
    #    attached, and P2 applies with nothing to control.
    if m.path == Path.ACTIVE:
        parts.append("- Emphasise the shortest trend the daily bars can carry. Skip longer-horizon structure.")
    else:
        parts.append("- Emphasise monthly/quarterly trend. Skip noise-level intraday signals.")
    if m.risk_score <= 2:
        parts.append("- Prefer mean-reversion setups and clearly stated levels.")
    elif m.risk_score >= 4:
        parts.append("- Breakout/breakdown setups acceptable.")
    return "\n".join(parts)


def _news_block(m: Mandate) -> str:
    parts = [
        "## Role guidance — News Analyst",
        "You synthesise news impact. Given this mandate:",
        # CR147 Tier A.4 — the watchlist half is deleted, not softened: no
        # watchlist is injected into any prompt, so "filter to it" named a list
        # the agent has never been shown. Wiring it is Tier B.
        "- Filter headlines to the user's holdings, which are in the portfolio block above.",
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
        # CR147 Tier A.5 — softened to the macro that actually exists. This asked
        # the agent to WEIGHT the Fed cycle and fiscal policy against single
        # events, while the only forward macro datum in the whole prompt is an
        # FOMC countdown in days. Weighting something you were not given is an
        # invitation to supply it from training memory, three lines under a
        # notice that there is no macro feed.
        parts.append(
            "- Prefer structural reads over single events. The only forward macro "
            "datum you are given is the FOMC countdown; anything else about the "
            "cycle is your framing, not data, and must be said as such."
        )
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
        # CR150 Tier C — `long_only=False` does NOT make shorts executable. The
        # simulator rejects any sell beyond the held quantity unconditionally
        # (`sim_engine`, blocked_by="long_only"), and `concierge_engine.
        # _parse_constraints` leaves this flag false by OMISSION, so the branch
        # is reachable by a user who never asked to short. Telling the Bear it
        # may recommend one produces advice the engine will refuse — the
        # CR040 failure pointed at the user instead of the operator.
        parts.append(
            "- Shorting is not available in this simulator regardless of mandate "
            "flags — frame a negative view as 'avoid' or 'wait for better entry'."
        )
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
        # CR151 Tier B — this used to be an unconditional imperative sitting
        # ~50 lines closer to the data than `research_manager.md`'s correct
        # deferral ("In the Room, follow the format instruction appended at the
        # end of your prompt instead"). Proximity won: 13 of 18 Room turns came
        # back three-part, and 11 of 18 carried bold pseudo-headings against a
        # format block that says "no headings". Both external reviews blamed the
        # base prompt; cutting only that would have left THIS standing.
        "- In 1-on-1, use the 3-part output: (1) Points of agreement, "
        "(2) Points of dispute, (3) Recommended stance. In the Room, the format "
        "block appended at the end of your prompt replaces this — follow it instead.",
        "- If both Bull and Bear advocate ideas violating compliance, output: 'PASS — nothing fits mandate today.'",
        f"- Match learning_style tone: {_tone_for_learning_style(m.learning_style)}",
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
        # DEF241: this used to hand over the formula (`size% × stop-distance%`) and
        # leave the agent to apply it. The mandate snapshot now renders the computed
        # contribution for THIS role's own size, so the instruction points at that
        # figure instead of asking for arithmetic no one checks.
        f"- HARD CONSTRAINT: the drawdown contribution stated for YOUR position in "
        f"the mandate snapshot above, plus existing drawdown, cannot exceed "
        f"{m.max_drawdown_pct}%. Use that figure as written — do not recompute it.",
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
        # DEF241 — see `_aggressive_block`. Measured over the epoch, this agent
        # stated a cap-consumption figure in 9 of 18 turns and 4 were wrong, one
        # reproducing DEF066's own error with DEF066's warning in the same prompt.
        f"- {m.max_drawdown_pct}% portfolio drawdown is the ceiling. The mandate "
        f"snapshot above states YOUR position's contribution to it; argue from that "
        f"figure toward comfortable distance below the cap. Do not recompute it, and "
        f"never compare a raw stop distance against the cap.",
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
        # DEF241 — see `_aggressive_block`.
        f"- Propose a position respecting risk_score={m.risk_score} and the "
        f"portfolio-level max_drawdown_pct={m.max_drawdown_pct}%. The mandate "
        f"snapshot above states YOUR position's contribution to that cap — quote "
        f"it, do not recompute it.\n"
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
2. If any compliance violation: PASS, and name the rule that failed.
3. If passes compliance:
   - Weigh the debate
   - Consider risk_score={m.risk_score} and current drawdown
   - Issue: APPROVE or PASS — there is no third value. To change the Trader's
     numbers, APPROVE with your own and say what you changed.
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
- Route trading questions to the right of the 12 agents

## You DO NOT
- Give trading advice or speculate on tickers
- Predict markets
- Bypass the user's mandate
- Submit trades on the user's behalf
- Offer to mute or promote agents, or claim any agent-visibility/priority control exists —
  there is no such capability anywhere in the app
- Offer to schedule a morning briefing or any recurring delivery — there is no scheduler,
  no sender, and no such feature anywhere in the backend

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


# CR129: the five CR101-BE2 limits now follow the SAME settable-with-preset-
# fallback contract as `_max_position_pct`/`_sector_cap_pct` above — `None`
# resolves to the risk-tier preset (always shown/enforced) rather than
# narrating "not set". "Off" is still expressible (a `0` cooldown, a very high
# count, a `100%` open-risk cap) but is now an explicit override, not the
# unset-field state.
#
# DEF196: `0` does NOT mean the same thing on all seven of these settable caps.
# On single_name_cap_pct, sector_cap_pct, max_open_positions, max_trades_per_day,
# max_trades_per_week and max_open_risk_pct, `0` binds as "block everything" — the
# cap is a ceiling and zero leaves no room under it. `post_loss_cooldown_hours` is
# the one exception: `0` is a zero-HOUR wait, i.e. a no-op — the cooldown simply
# never engages. Do not read a `0` cooldown as "disabled vs. blocking"; it is
# neither, it is an instantaneous cooldown.


def _cooldown_text(m: Mandate) -> str:
    """DEF196: the "off" state and the "enforced as a hard block" mechanism
    sentence must never land in the same line — a static suffix that assumed the
    cooldown is always active read as a self-contradicting instruction on every
    `0`-hour override, which CR129 made an explicit, common state. The mechanism
    clause now lives ONLY on the branch where the cooldown actually runs."""
    hours = resolved_post_loss_cooldown_hours(m.risk_score, m.post_loss_cooldown_hours)
    if hours <= 0:
        return "off (no cooldown enforced) — 0 is a no-op here, not a block (unlike the other size/pace caps below)"
    return f"{hours}h after a stop-out — enforced as a hard block on the next BUY, not a suggestion."


def _max_open_positions_text(m: Mandate) -> str:
    return f"{resolved_max_open_positions(m.risk_score, m.max_open_positions)}"


def _max_trades_per_day_text(m: Mandate) -> str:
    return f"{resolved_max_trades_per_day(m.risk_score, m.max_trades_per_day)}"


def _max_trades_per_week_text(m: Mandate) -> str:
    return f"{resolved_max_trades_per_week(m.risk_score, m.max_trades_per_week)}"


def _max_open_risk_pct_text(m: Mandate) -> str:
    pct = resolved_max_open_risk_pct(m.risk_score, m.max_drawdown_pct, m.max_open_risk_pct)
    return f"{pct}%"


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
