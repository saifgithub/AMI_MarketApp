"""Concierge conversation engine — drives the onboarding interview.

V0 (this file): deterministic, scripted Concierge. No LLM dependency.
   - Lets us ship the full UX flow before API keys are configured.
   - Every question, every response, every chip suggestion is hard-coded.
   - Mandate derivation is fully deterministic from the user's answers.

V1 (later, when LLM keys are wired): an LLM-driven Concierge that can:
   - Ask clarifying follow-ups
   - Detect hesitation and offer chips dynamically
   - Adapt tone to early signals (terse / exploratory)
   - Produce the natural-language readback

The state machine is the same; only the message-generation layer changes.
"""

from __future__ import annotations

from typing import Any

from app.core.time import now_utc
from app.schemas.mandate import (
    Compliance,
    Horizon,
    LearningStyle,
    Path,
    Plan,
    PrimaryGoal,
    RiskComponents,
)
from app.schemas.onboarding import (
    Author,
    ConversationStep,
    Message,
    OnboardingSession,
)


# ──────────────────────────────────────────────────────────────────────────
# Scripted prompts (V0)
# ──────────────────────────────────────────────────────────────────────────


WELCOME_TEXT = (
    "Hi, I'm your Concierge. I'll spend a few minutes getting to know you so your "
    "team of 12 analysts works the way you want. About 3 minutes. Ready?"
)
WELCOME_CHIPS = ["Yes, let's go", "Tell me more first"]


Q1_TEXT = "What's bringing you here?"
Q1_CHIPS = [
    "Save for retirement",
    "Build long-term wealth",
    "Generate income now",
    "Save for a specific goal",
    "Learn to trade short-term",
    "Just exploring",
]


Q2_TEXT = (
    "Roughly how far out are we looking? Weeks, months, years? "
    "Or pick one of these."
)
Q2_CHIPS = ["<1 year", "1–3 years", "3–10 years", "10+ years"]


Q3_TEXT = (
    "I'm going to walk you through three quick scenarios so I can calibrate your "
    "team's risk posture.\n\n"
    "Scenario one. Two months in, your $10K simulator has dropped to $7K because "
    "the whole market corrected. Walk me through what you'd actually do."
)
Q3_CHIPS = [
    "Sell everything",
    "Sell my worst performers",
    "Hold and wait",
    "Buy more cautiously",
    "Buy aggressively — it's on sale",
]


Q4_TEXT = (
    "Now the opposite. You stayed in cash. Over the next 6 months, the market "
    "rallied 25% and you missed it completely.\n\n"
    "Which one stings more — being in and losing, or being out and missing?"
)
Q4_CHIPS = ["Losing in feels worse", "Missing out feels worse", "About the same"]


Q5_TEXT = (
    "One more. You've got real conviction on a single stock — your homework is "
    "done, your team agrees.\n\n"
    "Would you put 10%, 30%, or 60% of your portfolio in it?"
)
Q5_CHIPS = ["10% (cautious)", "30% (balanced)", "60% (all-in)"]


def q6_text(risk_score: int) -> str:
    suggestion = {1: 10, 2: 20, 3: 30, 4: 40, 5: 50}[risk_score]
    return (
        "Last numbers question. What's the largest temporary loss you could "
        f"stomach before you'd lose sleep?\n\n"
        f"(Based on your scenarios, {suggestion}% sounds like a fit — but you choose.)"
    )


Q6_CHIPS = ["10%", "20%", "30%", "40%", "50%", "No cap"]


def _q6_clarify_text() -> str:
    return (
        "I didn't catch a number there — what percentage loss could you stomach "
        "before it costs you sleep? Give me a number like \"20%\", or pick a chip, "
        "or say \"no cap\" if there isn't one."
    )


# CR114: this used to ask only what you'd NEVER invest in, while five of its
# seven chips were inclusions ("Halal only", "ESG-leaning") or strategy and
# liquidity limits. Read literally, picking "Halal only" answered "I'd never
# want to invest in halal-only" — the inverse of the intent. The chips now say
# which direction each rule runs, and the question asks for both.
Q7_TEXT = (
    "Any hard rules I should hand your analysts? ONLY narrows where they can "
    "invest; NEVER puts something off the table entirely. Pick any that apply, "
    "or tell me freeform."
)
Q7_CHIPS = [
    "ONLY halal / Sharia-compliant",
    "ONLY ESG-leaning",
    "ONLY liquid names (no microcaps)",
    "ONLY long positions (no shorting)",
    "NEVER tobacco, alcohol or gambling",
    "NEVER fossil fuels",
    "No hard rules",
]


# ──────────────────────────────────────────────────────────────────────────
# State machine — given current step + answer, what's next?
# ──────────────────────────────────────────────────────────────────────────


_NEXT_STEP: dict[ConversationStep, ConversationStep] = {
    ConversationStep.WELCOME: ConversationStep.Q1_GOAL,
    ConversationStep.Q1_GOAL: ConversationStep.Q2_HORIZON,
    ConversationStep.Q2_HORIZON: ConversationStep.Q3_SCENARIO_DRAWDOWN,
    ConversationStep.Q3_SCENARIO_DRAWDOWN: ConversationStep.Q4_SCENARIO_REGRET,
    ConversationStep.Q4_SCENARIO_REGRET: ConversationStep.Q5_SCENARIO_CONCENTRATION,
    ConversationStep.Q5_SCENARIO_CONCENTRATION: ConversationStep.Q6_MAX_DRAWDOWN,
    ConversationStep.Q6_MAX_DRAWDOWN: ConversationStep.Q7_CONSTRAINTS,
    # DEF129: Q7 used to hand off to Q8_BRIEFING, which offered a 07:00 daily
    # briefing nothing in the backend can send. Q7 is now the last question.
    ConversationStep.Q7_CONSTRAINTS: ConversationStep.READBACK,
    ConversationStep.READBACK: ConversationStep.COMPLETE,
}


# ──────────────────────────────────────────────────────────────────────────
# Welcome + first question (returned together on /onboarding/start)
# ──────────────────────────────────────────────────────────────────────────


def make_welcome_messages() -> tuple[Message, Message]:
    welcome = Message(
        author=Author.CONCIERGE,
        content=WELCOME_TEXT,
        step=ConversationStep.WELCOME,
        chips=WELCOME_CHIPS,
    )
    first_q = Message(
        author=Author.CONCIERGE,
        content=Q1_TEXT,
        step=ConversationStep.Q1_GOAL,
        chips=Q1_CHIPS,
    )
    return welcome, first_q


# ──────────────────────────────────────────────────────────────────────────
# Process an answer — returns the next Concierge message (and possibly readback)
# ──────────────────────────────────────────────────────────────────────────


def process_answer(
    session: OnboardingSession,
    step: ConversationStep,
    answer: str,
) -> tuple[ConversationStep, Message, dict[str, Any] | None]:
    """Apply the answer to the session, return (next_step, next_message, readback_or_none).

    DEF428: Q6 ("largest temporary loss you could stomach") is the one free-text
    numeric question in the interview, and `_parse_drawdown_pct` used to fall
    back to a bare 30 for anything it couldn't read — "5%", "45%", "83", or
    garbage all silently became a 30% drawdown mandate with nothing disclosed
    to the user. There is no other unparseable-answer precedent in this state
    machine to follow (every other `_classify_*` has a "safe default" and
    always advances), so this is the first re-ask: on an unparseable Q6 answer,
    `current_step` does NOT advance — `session.answers["max_drawdown_pct"]` is
    left untouched and the Concierge re-asks Q6 with a clarifying prefix
    instead of moving to Q7. A parseable answer (an explicit 1-100 percentage,
    with or without "%"/"percent", or "no cap") behaves exactly as before.
    """

    if step == ConversationStep.Q6_MAX_DRAWDOWN and _parse_drawdown_pct(answer.strip().lower()) is None:
        session.updated_at = now_utc()
        message = Message(
            author=Author.CONCIERGE,
            content=_q6_clarify_text(),
            step=ConversationStep.Q6_MAX_DRAWDOWN,
            chips=Q6_CHIPS,
        )
        return ConversationStep.Q6_MAX_DRAWDOWN, message, None

    # Record the user's answer in session.answers
    _record_answer(session, step, answer)

    next_step = _NEXT_STEP.get(step, ConversationStep.COMPLETE)
    session.current_step = next_step
    session.updated_at = now_utc()

    if next_step == ConversationStep.READBACK:
        summary = _build_readback_summary(session)
        message = Message(
            author=Author.CONCIERGE,
            content=_readback_text(summary),
            step=ConversationStep.READBACK,
            chips=["Looks right", "Edit goal", "Edit risk", "Edit constraints"],
        )
        return next_step, message, summary

    if next_step == ConversationStep.COMPLETE:
        # Shouldn't be reached via process_answer — readback confirmation handles it.
        return next_step, _completion_message(), None

    return next_step, _question_message(next_step, session), None


def _question_message(step: ConversationStep, session: OnboardingSession) -> Message:
    if step == ConversationStep.Q1_GOAL:
        return Message(author=Author.CONCIERGE, content=Q1_TEXT, step=step, chips=Q1_CHIPS)
    if step == ConversationStep.Q2_HORIZON:
        return Message(author=Author.CONCIERGE, content=Q2_TEXT, step=step, chips=Q2_CHIPS)
    if step == ConversationStep.Q3_SCENARIO_DRAWDOWN:
        return Message(author=Author.CONCIERGE, content=Q3_TEXT, step=step, chips=Q3_CHIPS)
    if step == ConversationStep.Q4_SCENARIO_REGRET:
        return Message(author=Author.CONCIERGE, content=Q4_TEXT, step=step, chips=Q4_CHIPS)
    if step == ConversationStep.Q5_SCENARIO_CONCENTRATION:
        return Message(author=Author.CONCIERGE, content=Q5_TEXT, step=step, chips=Q5_CHIPS)
    if step == ConversationStep.Q6_MAX_DRAWDOWN:
        risk_score = _derive_risk_score(session)
        return Message(
            author=Author.CONCIERGE, content=q6_text(risk_score), step=step, chips=Q6_CHIPS
        )
    if step == ConversationStep.Q7_CONSTRAINTS:
        return Message(author=Author.CONCIERGE, content=Q7_TEXT, step=step, chips=Q7_CHIPS)
    raise ValueError(f"No question for step={step}")


def _completion_message() -> Message:
    return Message(
        author=Author.CONCIERGE,
        content=(
            "Your mandate is saved. Your 12 analysts are calibrating themselves to your "
            "answers now. Let me introduce you to them."
        ),
        step=ConversationStep.COMPLETE,
    )


# ──────────────────────────────────────────────────────────────────────────
# Answer recording — maps raw text → structured fields
# ──────────────────────────────────────────────────────────────────────────


def _record_answer(session: OnboardingSession, step: ConversationStep, answer: str) -> None:
    a = answer.strip().lower()

    if step == ConversationStep.WELCOME:
        session.answers["acknowledged_welcome"] = True

    elif step == ConversationStep.Q1_GOAL:
        session.answers["primary_goal_raw"] = answer
        session.answers["primary_goal"] = _classify_goal(a).value
        # Derive path
        if _classify_goal(a) in (PrimaryGoal.RETIREMENT, PrimaryGoal.LONG_TERM_WEALTH):
            session.answers["path"] = Path.LONG_HORIZON.value
        elif _classify_goal(a) == PrimaryGoal.LEARNING_TO_TRADE:
            session.answers["path"] = Path.ACTIVE.value
        else:
            session.answers["path"] = Path.LONG_HORIZON.value

    elif step == ConversationStep.Q2_HORIZON:
        session.answers["horizon_raw"] = answer
        session.answers["horizon"] = _classify_horizon(a).value

    elif step == ConversationStep.Q3_SCENARIO_DRAWDOWN:
        session.answers["q3_drawdown_quote"] = answer
        session.risk_components_partial["drawdown_response"] = _classify_drawdown_response(a)

    elif step == ConversationStep.Q4_SCENARIO_REGRET:
        session.answers["q4_regret_quote"] = answer
        session.risk_components_partial["regret_asymmetry"] = _classify_regret(a)

    elif step == ConversationStep.Q5_SCENARIO_CONCENTRATION:
        session.answers["q5_concentration_quote"] = answer
        session.risk_components_partial["concentration_tolerance"] = _classify_concentration(a)

    elif step == ConversationStep.Q6_MAX_DRAWDOWN:
        session.answers["max_drawdown_pct"] = _parse_drawdown_pct(a)

    elif step == ConversationStep.Q7_CONSTRAINTS:
        session.answers["compliance"] = _parse_constraints(a)


# ──────────────────────────────────────────────────────────────────────────
# Classifiers (V0 — keyword-based; V1 will use LLM)
# ──────────────────────────────────────────────────────────────────────────


def _classify_goal(text: str) -> PrimaryGoal:
    t = text.lower()
    if "retire" in t:
        return PrimaryGoal.RETIREMENT
    if "wealth" in t or "long-term" in t or "long term" in t:
        return PrimaryGoal.LONG_TERM_WEALTH
    if "income" in t:
        return PrimaryGoal.INCOME_NOW
    if "house" in t or "kids" in t or "specific" in t or "goal" in t:
        return PrimaryGoal.SPECIFIC_GOAL
    if "trade" in t or "short-term" in t or "active" in t or "trading" in t:
        return PrimaryGoal.LEARNING_TO_TRADE
    if "explor" in t or "curious" in t:
        return PrimaryGoal.EXPLORING
    return PrimaryGoal.LONG_TERM_WEALTH  # safe default


def _classify_horizon(text: str) -> Horizon:
    t = text.lower()
    if "<1" in t or "less than 1" in t or "weeks" in t or "months" in t:
        return Horizon.SHORT
    if "1–3" in t or "1-3" in t or "1 to 3" in t:
        return Horizon.MEDIUM
    if "3–10" in t or "3-10" in t or "3 to 10" in t:
        return Horizon.LONG
    if "10+" in t or "10 plus" in t or "long" in t or "decade" in t:
        return Horizon.VERY_LONG
    return Horizon.LONG  # safe default


def _classify_drawdown_response(text: str) -> int:
    t = text.lower()
    if "sell everything" in t or "panic" in t or "freak" in t:
        return 1
    if "sell" in t and ("worst" in t or "loser" in t):
        return 2
    if "hold" in t or "ride" in t or "wait" in t:
        return 3
    if "buy more" in t and ("cautious" in t or "carefully" in t):
        return 4
    if "buy" in t and ("aggressive" in t or "leverage" in t or "all in" in t or "sale" in t):
        return 5
    if "buy more" in t:
        return 4
    if "buy" in t:
        return 4
    return 3  # safe default


def _classify_regret(text: str) -> int:
    t = text.lower()
    if "missing" in t and ("worse" in t or "stings" in t):
        return 1  # asymmetric toward upside → bump risk up
    if "losing" in t and ("worse" in t or "stings" in t):
        return -1  # asymmetric toward loss → bump risk down
    if "same" in t or "equal" in t or "both" in t:
        return 0
    return 0


def _classify_concentration(text: str) -> int:
    t = text.lower()
    if "60" in t:
        return 5
    if "30" in t:
        return 3
    if "10" in t:
        return 1
    # freeform: look for numeric
    import re

    m = re.search(r"(\d+)\s*%", t)
    if m:
        pct = int(m.group(1))
        if pct >= 50:
            return 5
        if pct >= 25:
            return 3
        return 1
    return 3


def _parse_drawdown_pct(text: str) -> float | None:
    """Q6 free-text -> a 1-100 drawdown percentage, or None if unparseable.

    DEF428: this used to substring-match the six chip values only and default
    to 30 for anything else — "5%", "45%", "83", and plain garbage all became
    an undisclosed 30% mandate. It now reads ANY explicit number the user
    typed (with or without "%"/"percent", decimals allowed) in the 1-100
    range, so a free-text answer is honoured exactly rather than snapped to
    the nearest chip. Returns None (caller re-asks) rather than guessing when
    no such number is present — a fabricated mandate value is worse than
    asking again.
    """
    t = text.lower().strip()
    if "no cap" in t or "no limit" in t or "uncapped" in t:
        return 100

    import re

    m = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:%|percent)?", t)
    if not m:
        return None
    pct = float(m.group(1))
    if pct <= 0 or pct > 100:
        return None
    return int(pct) if pct == int(pct) else round(pct, 1)


def _parse_constraints(text: str) -> dict[str, Any]:
    """Q7 → the `Compliance` object.

    CR220: `long_only` and `liquid_only` are RESTRICTIONS that `Compliance`
    defaults to True, and this function used to return them as bare keyword
    hits — i.e. False for anyone who did not happen to type "long only" or
    "liquid". A user answering "no hard rules" therefore came out of the
    interview LESS constrained than one who never onboarded at all and got
    `get_or_default()`'s schema defaults. The `or Compliance().model_dump()`
    fallback at the call site could never repair it, because this dict is
    never falsy.

    So the two restriction flags are omitted unless the user's text asserts
    something about them, and the schema default stands.

    The two are NOT symmetric, and the docstring used to imply they were.
    `long_only` has an explicit opt-OUT branch, because the interview is the
    only place a user can loosen it and silently refusing to honour "I want to
    short" would be the mirror image of the bug being fixed. `liquid_only` has
    none — it can only ever be set True, and since "illiquid" contains
    "liquid", "I want to trade illiquid microcaps" restricts the user from
    exactly what they asked for. That direction is safe (it over-restricts, and
    Settings → Compliance corrects it in one tap) so it is left alone rather
    than fixed with more keyword surface — but it is a real limitation, not an
    omission, and the sentence should not claim otherwise.

    Precedence is the safety property here: restriction language beats opt-out
    language when a single answer contains both ("long only, though I want to
    short sometimes"). Pinned by
    `test_cr220_minor2_restriction_language_beats_opt_out_language`.

    The remaining flags are opt-IN (default False), so a bare keyword hit is
    the correct shape for them and they are always present.
    """
    t = text.lower()
    constraints: dict[str, Any] = {
        "halal": "halal" in t or "sharia" in t,
        "esg_lite": "esg" in t,
        "no_tobacco_alcohol_gambling": "tobacco" in t or "alcohol" in t or "gambling" in t,
        "no_fossil_fuels": "fossil" in t,
        "ticker_blocklist": [],
        "ticker_allowlist": None,
        "custom_constraints": [],
    }

    # Opt-out must be asserted, never inferred from the bare word "short":
    # the Q7 chip itself reads "ONLY long positions (no shorting)", and
    # freeform like "I don't want shorting" is a request FOR the restriction,
    # not against it. Guessing wrong here silently loosens a safety control,
    # which is the whole class of bug this function is being fixed for, so an
    # ambiguous answer leaves the schema default alone.
    if "long-only" in t or "long only" in t or "no short" in t:
        constraints["long_only"] = True
    elif "want to short" in t or "allow short" in t or "allow me to short" in t:
        constraints["long_only"] = False

    if "liquid" in t or "microcap" in t or "micro-cap" in t:
        constraints["liquid_only"] = True

    return constraints


# ──────────────────────────────────────────────────────────────────────────
# Risk score derivation (after Q5)
# ──────────────────────────────────────────────────────────────────────────


# CR228 step 2: `max_drawdown_pct` on a 1-5 scale, same tier boundaries as
# `q6_text`'s own suggestion table (:101) so the nudge and the suggestion the
# user was shown agree on what "high" means. DEF418: tiers 4 and 5 previously
# both mapped to 50%; widened to {10: 1, 20: 2, 30: 3, 40: 4, 50: 5} per Saiful
# 2026-09-24 ruling: "4→40%, 5→50%".
_DRAWDOWN_PCT_TO_TIER: dict[int, int] = {10: 1, 20: 2, 30: 3, 40: 4, 50: 5, 100: 5}
# `Horizon.SHORT` implies active/short-term trading (Q1's "learn to trade" path
# maps here too) — more risk tolerance is needed to accept the swings that
# horizon trades through, not less. `VERY_LONG` similarly has more room to
# recover a drawdown. Both nudge up; the middle two are neutral.
_HORIZON_TIER: dict[str, int] = {"short": 4, "medium": 3, "long": 3, "very_long": 4}
_GOAL_TIER: dict[str, int] = {
    "income_now": 2,  # capital preservation, income needs stability
    "retirement": 3,
    "long_term_wealth": 3,
    "specific_goal": 3,
    "exploring": 3,
    "learning_to_trade": 4,  # deliberately practicing active risk-taking
}


def _derive_risk_score(session: OnboardingSession) -> int:
    """The mandate's `risk_score` (1-5).

    Primary signal is the three Q3-Q5 scenario answers (`risk_components`) —
    deliberately weighted answers to specific loss/regret/concentration
    scenarios, the most direct risk-preference measurement the interview has.
    `max_drawdown_pct`, `horizon`, and `primary_goal` (CR228: previously
    dropped entirely, or — for max_drawdown_pct — only informing a *suggestion*
    the user could override with no path back into the score) each contribute a
    bounded nudge, so a user whose stated loss tolerance or goal disagrees with
    their scenario answers moves the score, while the scenario answers remain
    the dominant signal (the most extreme possible nudge cannot move a
    maximally-conservative or maximally-aggressive scenario base off the 1/5
    clamp — see test_cr228_scenario_answers_remain_the_dominant_signal).

    `max_drawdown_pct` and `horizon` are read from `session.answers`, which is
    empty for both at the Q6-suggestion call site (Q6 IS the drawdown
    question; `session.answers["horizon"]` is set at Q2 and normally present
    by then) — `.get` falls back to the scenario-only base, so the suggestion
    shown before Q6 is answered is unaffected. The readback/mandate call site
    (after Q7) always has all three.
    """
    rc = session.risk_components_partial
    a = rc.get("drawdown_response", 3)
    asym = rc.get("regret_asymmetry", 0)
    c = rc.get("concentration_tolerance", 3)
    # Same rounding order as pre-CR228 (round the midpoint, THEN add asym) —
    # audit round 1 MAJOR-1 found the add-then-round-last order this function
    # briefly used moved the scenario-only score for 10 of 45 reachable
    # (a, asym, c) combinations with zero nudge inputs present, undocumented,
    # including a loss-averse profile (regret_asymmetry=-1) landing a HIGHER
    # score. Change 2 is the nudges below; this base must stay identical to
    # what it was before them.
    base = round((a + c) / 2) + asym

    nudges: list[float] = []
    if (dd := session.answers.get("max_drawdown_pct")) is not None:
        nudges.append(_DRAWDOWN_PCT_TO_TIER.get(dd, 3) - 3)
    if (h := session.answers.get("horizon")) is not None:
        nudges.append(_HORIZON_TIER.get(h, 3) - 3)
    if (g := session.answers.get("primary_goal")) is not None:
        nudges.append(_GOAL_TIER.get(g, 3) - 3)

    # Each present nudge contributes at most +-1, averaged across however many
    # of the three are available — bounded total influence regardless of how
    # many inputs happen to agree, so the scenario base stays primary (dominance
    # is still enforced: the most conservative scenario base clamped against the
    # most aggressive possible nudge still rounds to 1, and the reverse to 5;
    # see test_cr228_scenario_answers_remain_the_dominant_signal).
    #
    # Audit round 2 MAJOR-2: this used to also divide by 2, which was fine
    # against round 1's half-integer base (`(a+c)/2 + asym`, no rounding) but
    # became silently too weak once MAJOR-1 restored the correct integer base
    # (`round((a+c)/2) + asym`) — `round(int +- 0.333)` can never cross an
    # integer, so with all three inputs present (the realistic Q1/Q2-already-
    # answered case at Q6/readback) NO drawdown answer could move the score at
    # all (0/45 reachable bases, was 16/45 at round 1's buggy formula) — the
    # exact backwards-causality bug this CR exists to fix, silently reintroduced
    # by fixing a different bug. Removing the /2 restores 43/45 while the
    # dominance property (above) still holds at both extremes.
    nudge_total = 0.0
    if nudges:
        nudge_total = sum(nudges) / len(nudges)

    return max(1, min(5, round(base + nudge_total)))


# ──────────────────────────────────────────────────────────────────────────
# Readback summary
# ──────────────────────────────────────────────────────────────────────────


def _build_readback_summary(session: OnboardingSession) -> dict[str, Any]:
    risk_score = _derive_risk_score(session)
    return {
        "primary_goal": session.answers.get("primary_goal", PrimaryGoal.EXPLORING.value),
        "horizon": session.answers.get("horizon", Horizon.LONG.value),
        "path": session.answers.get("path", Path.LONG_HORIZON.value),
        "risk_score": risk_score,
        "max_drawdown_pct": session.answers.get("max_drawdown_pct", 30),
        # CR220: resolve the PARTIAL dict `_parse_constraints` returns through
        # the schema, so both consumers of this summary — the readback text the
        # user confirms, and the mandate built at claim — see the same fully
        # populated object. `_parse_constraints` deliberately omits the two
        # restriction flags unless the user asserted something about them; if
        # that partial dict reached the readback directly, `long-only` would
        # silently drop out of the flags list while still being ENFORCED, which
        # is a promise-vs-mechanism gap of exactly the DEF158 shape.
        "compliance": Compliance(**session.answers.get("compliance", {})).model_dump(),
        "locale": session.locale,
        "timezone": session.timezone,
        "risk_quotes": [
            session.answers.get("q3_drawdown_quote", ""),
            session.answers.get("q4_regret_quote", ""),
            session.answers.get("q5_concentration_quote", ""),
        ],
    }


def _readback_text(summary: dict[str, Any]) -> str:
    goal = summary["primary_goal"].replace("_", " ").title()
    horizon = summary["horizon"].replace("_", " ").title()
    risk = summary["risk_score"]
    drawdown = summary["max_drawdown_pct"]
    compliance = summary["compliance"]

    flags: list[str] = []
    if compliance.get("halal"):
        flags.append("halal-compliant only")
    if compliance.get("esg_lite"):
        flags.append("ESG-leaning")
    if compliance.get("no_tobacco_alcohol_gambling"):
        flags.append("no tobacco/alcohol/gambling")
    if compliance.get("no_fossil_fuels"):
        flags.append("no fossil fuels")
    if compliance.get("long_only"):
        flags.append("long-only")
    if compliance.get("liquid_only"):
        flags.append("liquid only")
    flags_text = ", ".join(flags) if flags else "no special constraints"

    # DEF129: this used to close with "🎙️ Briefing: 07:00 daily briefing with
    # voice" — a time the user never chose and a voice mode that cannot exist —
    # in the very screen the user is asked to confirm as correct.
    return (
        f"Here's what I've got for your mandate. Read this and tell me if anything's off.\n\n"
        f"🎯 Goal: {goal}\n"
        f"📅 Horizon: {horizon}\n"
        f"⚖️ Risk: {risk}/5 — moderate.  Max drawdown {drawdown}%.\n"
        f"🛡️ Constraints: {flags_text}."
    )


# ──────────────────────────────────────────────────────────────────────────
# Convert session → Mandate-ready dict (consumed when user claims account)
# ──────────────────────────────────────────────────────────────────────────


def session_to_mandate_dict(session: OnboardingSession, user_id: Any) -> dict[str, Any]:
    """Build the dict suitable for constructing a Mandate from a completed session."""
    summary = _build_readback_summary(session)
    rc = session.risk_components_partial
    now = now_utc()
    return {
        "user_id": user_id,
        "version": 1,
        "display_name": session.detected_display_name or "Trader",
        "locale": session.locale,
        "timezone": session.timezone,
        "primary_goal": summary["primary_goal"],
        "horizon": summary["horizon"],
        "target_outcome": None,
        "path": summary["path"],
        "risk_score": summary["risk_score"],
        "risk_components": {
            "drawdown_response": rc.get("drawdown_response", 3),
            "regret_asymmetry": rc.get("regret_asymmetry", 0),
            "concentration_tolerance": rc.get("concentration_tolerance", 3),
        },
        "risk_quotes": summary["risk_quotes"],
        "max_drawdown_pct": summary["max_drawdown_pct"],
        # Already schema-resolved in `_build_readback_summary` (CR220), so the
        # old `or Compliance().model_dump()` fallback is gone: it could never
        # fire (the dict was never falsy) and it masked the real defect.
        "compliance": summary["compliance"],
        "learning_style": LearningStyle.QUICK.value,
        "plan": Plan.TRIAL_TRADER.value,
        "trial_expires_at": None,  # populated on claim
        "credit_balance": 75,
        "created_at": now,
        "updated_at": now,
    }
