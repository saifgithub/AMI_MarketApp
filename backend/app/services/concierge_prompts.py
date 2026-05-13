"""Post-onboarding Concierge — prompt composition + scripted fallback.

Mirrors `room_prompts.py` for the 13th agent. When a real LLM provider
is registered (`gateway.has_real_provider()`), `build_concierge_messages`
returns the (system_prompt, messages) that the Concierge needs to
actually answer the user and route them — it stuffs the bare
`build_agent_prompt(CONCIERGE, …)` with a compact context block that
lists the user's recent Decision Journal entries, currently unlocked
agents, available lessons, and a one-line mandate snapshot. Without
that context, the LLM hallucinates lesson titles and can't route the
user to specific agents/lessons.

When no real provider is registered, `scripted_reply` returns a
deterministic, route-aware response using keyword intent classification.
That keeps the Floor-tab Concierge useful (instead of falling back to
MockProvider's "I'm offline" canned text) during dev / vLLM outages.

The onboarding state machine in `concierge_engine.py` stays deterministic
and untouched — that's a different surface (the welcome interview),
and we keep it scripted on purpose so the mandate readback is
reproducible.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.schemas import AgentId, Mandate
from app.schemas.journal import JournalEntry
from app.schemas.lessons import LessonMeta
from app.services.agent_prompts import build_agent_prompt
from app.services.llm_gateway import ChatMessage


# ── Public: prompt composition for the live path ─────────────────────────


def build_concierge_messages(
    *,
    mandate: Mandate,
    user_id: UUID | None,
    user_message: str,
    history: list[ChatMessage],
    recent_journal: list[JournalEntry],
    unlocked_agents: set[str],
    available_lessons: list[LessonMeta],
) -> tuple[str, list[ChatMessage]]:
    """Compose (system_prompt, [chat_history + user_message]) for the Concierge.

    The base prompt already contains the role + DO/DO-NOT rules from
    `content/agents/concierge.md` plus the mandate overlay. The Floor
    addition gives the LLM concrete pointers so it stops speaking in
    abstractions ("I could open a lesson…") and starts naming specifics
    ("Lesson 003 — Mandate Basics; want me to open it?").
    """
    base = build_agent_prompt(AgentId.CONCIERGE, mandate, user_id=user_id)

    floor_addition = (
        "\n\n─── FLOOR CONCIERGE CONTEXT ───\n"
        f"{_mandate_one_liner(mandate)}\n"
        f"\n"
        f"Recent decisions (most recent first):\n{_format_journal(recent_journal)}\n"
        f"\n"
        f"Currently unlocked trading agents (you can route the user to any of these):\n"
        f"{_format_unlocked(unlocked_agents)}\n"
        f"\n"
        f"Available lessons you can recommend by ID + title:\n"
        f"{_format_lessons(available_lessons)}\n"
        f"\n"
        "Speak in 1–4 short sentences. Be specific — name the lesson ID, "
        "name the agent, name the journal entry by title or ticker. If the "
        "user wants trading advice on a ticker, do NOT speculate; route them "
        "to the right Analyst or to Convene the Room. If the user wants to "
        "edit a mandate field, walk them to Settings → Mandate. Never "
        "invent a lesson, agent, or journal entry that isn't listed above."
    )

    system_prompt = base + floor_addition
    messages = [ChatMessage(role=h.role, content=h.content) for h in history]
    messages.append(ChatMessage(role="user", content=user_message))
    return system_prompt, messages


# ── Public: deterministic scripted fallback ──────────────────────────────


def scripted_reply(
    *,
    user_message: str,
    mandate: Mandate,
    recent_journal: list[JournalEntry],
    unlocked_agents: set[str],
    available_lessons: list[LessonMeta],
) -> str:
    """Best-effort keyword-routed Concierge reply when the LLM is offline.

    Picks the closest intent (lesson / journal / agent route / mandate /
    Convene the Room) and emits a useful answer that names a real
    lesson ID, real agent, or real journal entry from the supplied
    context. Falls through to a soft default if nothing matches.
    """
    msg = user_message.lower().strip()

    if _matches(msg, _LESSON_KEYWORDS):
        return _scripted_lesson_reply(available_lessons)

    if _matches(msg, _JOURNAL_KEYWORDS):
        return _scripted_journal_reply(recent_journal)

    if _matches(msg, _MANDATE_KEYWORDS):
        return _scripted_mandate_reply(mandate)

    if _matches(msg, _ROOM_KEYWORDS):
        return (
            "Convene the Room runs all 12 agents on a single ticker and lands "
            "a verdict that respects your mandate. Tap CONVENE THE ROOM on "
            "the Floor and pick a ticker — I'll watch the run from there."
        )

    matched_agent = _match_agent_by_name(msg, unlocked_agents)
    if matched_agent is not None:
        pretty = matched_agent.replace("_", " ").title()
        return (
            f"You've unlocked {pretty} — tap them on the Floor to open a 1-on-1. "
            "When AMI is back online I'll be able to brief you on what they're "
            "watching right now."
        )

    if _matches(msg, _TRADING_KEYWORDS):
        return (
            "That's a question for your team, not me — I don't speculate on "
            "tickers. Open the Market Analyst or the Fundamentals Analyst "
            "from the Floor, or convene the Room if you want all 12 weighing "
            "in. AMI is in fallback mode for analysis right now."
        )

    # Last-resort retrieval over the AI Coach Q&A library. A confident
    # match (>=2 overlapping tokens with the question/tags) surfaces the
    # short_answer as a useful canned reply. Weak matches drop through to
    # the generic fallback so a single-keyword query doesn't dredge up
    # an unrelated FAQ.
    try:
        from app.services.ai_coach_service import get_ai_coach_service
        hit = get_ai_coach_service().top_hit(user_message, min_score=2)
        if hit is not None:
            return hit.short_answer
    except Exception:
        pass

    return (
        "AMI is in fallback mode right now — the on-prem AMI server isn't "
        "answering, so I can't route freely. You can still browse Lessons, "
        "review your Journal, and edit your Mandate in Settings."
    )


# ── Helpers — formatting blocks for the live prompt ──────────────────────


def _mandate_one_liner(m: Mandate) -> str:
    halal = "halal-only" if getattr(m.compliance, "halal", False) else None
    long_only = "long-only" if getattr(m.compliance, "long_only", False) else None
    flags = [s for s in (halal, long_only) if s]
    flags_text = (", " + ", ".join(flags)) if flags else ""
    plan = m.plan.value if hasattr(m.plan, "value") else str(m.plan)
    return (
        f"Mandate snapshot: plan={plan}, risk_score={m.risk_score}/5, "
        f"max_drawdown={m.max_drawdown_pct}%{flags_text}."
    )


def _format_journal(entries: list[JournalEntry]) -> str:
    if not entries:
        return "(No entries yet — user hasn't taken any logged actions.)"
    lines: list[str] = []
    for e in entries[:6]:
        et = e.entry_type.value if hasattr(e.entry_type, "value") else str(e.entry_type)
        ticker = f" [{e.ticker}]" if e.ticker else ""
        title = e.title or et
        lines.append(f"- {et}{ticker}: {title}")
    return "\n".join(lines)


def _format_unlocked(agent_ids: set[str]) -> str:
    if not agent_ids:
        return "(None yet — user is on Floor Pass and hasn't earned any of the 12.)"
    pretty = sorted(a.replace("_", " ").title() for a in agent_ids)
    return ", ".join(pretty)


def _format_lessons(lessons: list[LessonMeta]) -> str:
    if not lessons:
        return "(Lesson catalogue empty.)"
    lines: list[str] = []
    for m in lessons[:25]:
        lines.append(f"- {m.id}: {m.title} (track={m.track}, level={m.level})")
    if len(lessons) > 25:
        lines.append(f"- … and {len(lessons) - 25} more")
    return "\n".join(lines)


# ── Scripted-path intent matching ────────────────────────────────────────


_LESSON_KEYWORDS = (
    "lesson", "learn", "teach me", "tutorial", "explain", "study", "course",
    "what is ", "what's a ", "what's an ",
)
_JOURNAL_KEYWORDS = (
    "journal", "history", "past", "previous", "what did i", "recent",
    "what have i", "decisions",
)
_MANDATE_KEYWORDS = (
    "mandate", "risk score", "drawdown", "compliance", "halal",
    "constraints", "limit", "settings",
)
_ROOM_KEYWORDS = (
    "convene", "the room", "convene the room", "12 agents", "all agents",
    "full team",
)
_TRADING_KEYWORDS = (
    "buy", "sell", "should i", "good time", "outlook", "price target",
    "go long", "go short", "is it a buy", "bullish on", "bearish on",
)


def _matches(message: str, keywords: tuple[str, ...]) -> bool:
    return any(k in message for k in keywords)


def _match_agent_by_name(message: str, unlocked: set[str]) -> str | None:
    """Look for an agent display-name phrase in the message.

    Matches against every AgentId, not just unlocked ones, so we can tell
    the user "X is still locked" instead of pretending it doesn't exist.
    Returns the agent_id string if mentioned and unlocked; None otherwise.
    """
    for a in AgentId:
        if a == AgentId.CONCIERGE:
            continue
        phrase = a.value.replace("_", " ")
        if phrase in message and a.value in unlocked:
            return a.value
    return None


def _scripted_lesson_reply(lessons: list[LessonMeta]) -> str:
    if not lessons:
        return (
            "I'd point you at a lesson but the catalogue isn't loaded right "
            "now. AMI is in fallback mode."
        )
    first = lessons[0]
    if len(lessons) >= 3:
        sample = ", ".join(f"{m.id} ({m.title})" for m in lessons[:3])
        return (
            f"Browse Lessons — a few starting points: {sample}. "
            f"Start with {first.id} if you're not sure. AMI is in fallback "
            "mode so I can't run a personalised pick right now."
        )
    return (
        f"Try lesson {first.id} — {first.title}. AMI is in fallback mode so "
        "I can't run a personalised recommendation right now."
    )


def _scripted_journal_reply(entries: list[JournalEntry]) -> str:
    if not entries:
        return (
            "Your Journal is empty so far — every Room run, sim trade, "
            "coach update, and lesson pass lands there automatically. "
            "Make a move and it'll show up."
        )
    titles = [e.title for e in entries[:3] if e.title]
    if not titles:
        return f"Your last {len(entries)} decisions are on the Journal tab."
    summary = "; ".join(titles)
    return (
        f"Your most recent decisions: {summary}. Open the Journal tab to "
        "see the full list — every entry has the transcript or diff."
    )


def _scripted_mandate_reply(m: Mandate) -> str:
    bits = [
        f"risk score {m.risk_score}/5",
        f"max drawdown {m.max_drawdown_pct}%",
    ]
    if getattr(m.compliance, "halal", False):
        bits.append("halal-only")
    if getattr(m.compliance, "long_only", False):
        bits.append("long-only")
    snapshot = ", ".join(bits)
    return (
        f"Your mandate right now: {snapshot}. To edit any of it, head to "
        "Settings → Mandate — every change versions the mandate and is "
        "logged in your Journal."
    )


# ── Context loader used by the runner — best-effort ──────────────────────


def load_concierge_context(
    *,
    user_id: UUID | None,
    plan: Any,
) -> tuple[list[JournalEntry], set[str], list[LessonMeta]]:
    """Pull (recent_journal, unlocked_agents, available_lessons) for one call.

    Best-effort: any data-layer failure returns empty collections rather
    than killing the chat stream. Anonymous (no user_id) users get an
    empty journal + activations but still see the lesson catalogue.
    """
    journal: list[JournalEntry] = []
    activations: set[str] = set()
    lessons: list[LessonMeta] = []

    try:
        from app.services.lessons_service import get_lessons_service

        lessons_service = get_lessons_service()
        lessons = lessons_service.all_meta()
        if user_id is not None:
            activations = {a.agent_id for a in lessons_service.list_activations(user_id)}
    except Exception:  # pragma: no cover — defensive
        pass

    if user_id is not None:
        try:
            from app.services.journal_store import get_journal_store

            entries, _, _ = get_journal_store().list_for_user(
                user_id, plan=plan, limit=8,
            )
            journal = entries
        except Exception:  # pragma: no cover — defensive
            pass

    return journal, activations, lessons
