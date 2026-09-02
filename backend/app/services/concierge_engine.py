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
    suggestion = {1: 10, 2: 20, 3: 30, 4: 50, 5: 50}[risk_score]
    return (
        "Last numbers question. What's the largest temporary loss you could "
        f"stomach before you'd lose sleep?\n\n"
        f"(Based on your scenarios, {suggestion}% sounds like a fit — but you choose.)"
    )


Q6_CHIPS = ["10%", "20%", "30%", "50%", "No cap"]


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
    """Apply the answer to the session, return (next_step, next_message, readback_or_none)."""

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


def _parse_drawdown_pct(text: str) -> int:
    t = text.lower()
    if "no cap" in t or "no limit" in t or "100" in t:
        return 100
    if "50" in t:
        return 50
    if "30" in t:
        return 30
    if "20" in t:
        return 20
    if "10" in t:
        return 10
    return 30


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
    something about them, and the schema default stands. The opt-OUT phrasings
    are matched explicitly: the interview is the only place a user can loosen
    them, and silently refusing to honour "I want to short" would be the
    mirror image of the bug being fixed.

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


def _derive_risk_score(session: OnboardingSession) -> int:
    rc = session.risk_components_partial
    a = rc.get("drawdown_response", 3)
    asym = rc.get("regret_asymmetry", 0)
    c = rc.get("concentration_tolerance", 3)
    base = round((a + c) / 2)
    return max(1, min(5, base + asym))


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
