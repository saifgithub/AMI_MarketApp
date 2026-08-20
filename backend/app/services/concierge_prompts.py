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

from app.core.config import settings
from app.core.logging import logger
from app.schemas import (
    AGENT_DISPLAY_NAMES,
    TWELVE_AGENT_IDS,
    AgentId,
    Mandate,
    agent_display_name,
)
from app.schemas.journal import JournalEntry
from app.schemas.lessons import LessonMeta
from app.services.agent_prompts import build_agent_prompt
from app.services.llm_gateway import ChatMessage


# ── CR021 concierge context router ───────────────────────────────────────
# The Floor Concierge's lesson knowledge is pluggable via the
# CONCIERGE_CONTEXT_MODE flag (app/core/config.py). `saver` is today's
# 25-lesson truncation; `full_context` (default, CR020) drops a compact
# index of the WHOLE catalogue into the prompt; `embedding` (CR019) is a
# future semantic-retrieval mode that, until it exists, degrades to
# `full_context`. Unknown/empty → full_context.
_VALID_CONTEXT_MODES = frozenset({"saver", "full_context", "embedding"})
# Soft cap for the lesson-context block (chars/4 token estimate). The
# corpus is 334 lessons and growing (CR054 later waves + CR058); the
# on-prem vLLM `ami-llm` has a 262k context window, so a ~13-20k index
# is a non-issue. `embedding` mode (CR019) remains the escape hatch once
# the catalogue reaches many hundreds and full_context stops being the
# right strategy.
_CONTEXT_TOKEN_BUDGET = 20_000
# Log the embedding→full_context degradation once per process, not per turn.
_embedding_fallback_logged = False


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
    unlock_requirements: list[Any] | None = None,
    context_mode: str | None = None,
) -> tuple[str, list[ChatMessage]]:
    """Compose (system_prompt, [chat_history + user_message]) for the Concierge.

    CR077 Phase 0 — the prompt is a **static head** followed by a **per-user
    tail**, in that order, so the head lands as a whole-block prefix-cache
    hit on the serving vLLM host (block size 2,096 tokens; caching is
    whole-block only, so anything user-specific this early costs the
    entire reuse). The head is the 342-lesson catalogue — byte-identical
    for every user, changing only when a lesson is added. Everything
    derived from `mandate`, `user_id`, or `recent_journal` (the base
    prompt's mandate overlay, the mandate one-liner, the journal, the
    unlocked-agent set, and the per-user unlock paths — DEF068 confirmed
    `unlock_requirements` is queried per-`user_id`, not global, so it
    cannot sit in the head) goes in the tail, with the closing
    instructions last — they only hold ("name ONLY the lessons in that
    agent's list above") because the catalogue precedes them.

    `context_mode` (CR021) selects how the lesson catalogue is presented.
    When None it resolves from `settings.concierge_context_mode`
    (default `full_context`), so the live runner needs no change.
    """
    mode_in = context_mode if context_mode is not None else settings.concierge_context_mode
    lesson_block, resolved_mode = _lesson_context_block(available_lessons, mode_in)
    est_tokens = len(lesson_block) // 4
    logger.info(
        "concierge_context",
        mode=resolved_mode,
        lessons=len(available_lessons),
        est_tokens=est_tokens,
    )
    if est_tokens > _CONTEXT_TOKEN_BUDGET:
        logger.warn(
            "concierge_context_over_budget",
            mode=resolved_mode,
            est_tokens=est_tokens,
            budget=_CONTEXT_TOKEN_BUDGET,
        )

    static_head = (
        "─── FLOOR CONCIERGE — LESSON CATALOGUE (static; identical for every user) ───\n"
        "Available lessons you can recommend by code, ID + title:\n"
        f"{lesson_block}\n"
    )

    base = build_agent_prompt(AgentId.CONCIERGE, mandate, user_id=user_id)

    per_user_tail = (
        "\n\n─── FLOOR CONCIERGE CONTEXT ───\n"
        f"{_mandate_one_liner(mandate)}\n"
        f"\n"
        f"Recent decisions (most recent first):\n{_format_journal(recent_journal)}\n"
        f"\n"
        f"Currently unlocked trading agents (you can route the user to any of these):\n"
        f"{_format_unlocked(unlocked_agents)}\n"
        f"\n"
        f"How the user unlocks each agent they don't have yet — these lists are "
        f"exhaustive and authoritative:\n"
        f"{_format_unlock_paths(unlock_requirements)}\n"
        f"\n"
        "Speak in 1–4 short sentences. Be specific — name the lesson by its "
        "code (\"TECH 12\", \"N&M 22\"), "
        "name the agent, name the journal entry by title or ticker. If the "
        "user wants trading advice on a ticker, do NOT speculate; route them "
        "to the right Analyst or to Convene the Room. If the user wants to "
        "edit a mandate field, walk them to Settings → Mandate. Never "
        "invent a lesson, agent, or journal entry that isn't listed above. "
        "When asked how to unlock an agent, name ONLY the lessons in that "
        "agent's list above — the unlock rule is exactly those lessons, not "
        "every lesson that mentions the agent."
    )

    system_prompt = static_head + "\n\n" + base + per_user_tail
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
        pretty = agent_display_name(matched_agent)
        return (
            f"You've unlocked {pretty} — tap them on the Floor to open a 1-on-1. "
            "When AMI is back online I'll be able to brief you on what they're "
            "watching right now."
        )

    if _matches(msg, _TRADING_KEYWORDS):
        return (
            "That's a question for your team, not me — I don't speculate on "
            "tickers. Open the Technical Strategist or the Fundamentals Analyst "
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
    pretty = sorted(agent_display_name(a) for a in agent_ids)
    return ", ".join(pretty)


def _format_unlock_paths(requirements: list[Any] | None) -> str:
    """DEF068 — the gateway lessons still owed, per locked agent.

    Without this the Concierge had the lesson catalogue and the unlocked-agent
    set but no mapping between them, so every specific answer to "what do I read
    to unlock the Execution Desk?" was a guess. Only locked agents are listed: an unlocked
    one has no path left, and spending prompt on it invites the model to tell a
    user to go earn something they already have.
    """
    if not requirements:
        return "(Unlock paths unavailable — do not guess; tell the user to open the agent on the Floor to see them.)"
    lines: list[str] = []
    for req in requirements:
        if req.unlocked:
            continue
        pretty = agent_display_name(req.agent_id)
        done = [l for l in req.required if l.passed]
        todo = [l for l in req.required if not l.passed]
        remaining = ", ".join(f"{l.code} ({l.title})" for l in todo)
        lines.append(
            f"- {pretty}: {len(done)}/{len(req.required)} done. "
            f"Still needs: {remaining}"
        )
    if not lines:
        return "(All 12 agents already unlocked.)"
    return "\n".join(lines)


def _resolve_context_mode(mode: str | None) -> str:
    """Normalise the flag value; unknown/empty → the default `full_context`."""
    m = (mode or "").strip().lower()
    return m if m in _VALID_CONTEXT_MODES else "full_context"


def _lesson_context_block(
    lessons: list[LessonMeta], mode: str | None
) -> tuple[str, str]:
    """Return (lesson_context_text, resolved_mode) for the Concierge prompt.

    CR021 router seam. `embedding` (CR019) has no retriever yet, so it
    degrades to `full_context` (logged once). `full_context` is always
    available with zero infra, so it is the terminal safe mode.
    """
    resolved = _resolve_context_mode(mode)
    if resolved == "embedding":
        global _embedding_fallback_logged
        if not _embedding_fallback_logged:
            logger.info(
                "concierge_context_fallback",
                requested="embedding",
                used="full_context",
                reason="lesson_retriever_not_built",
            )
            _embedding_fallback_logged = True
        resolved = "full_context"

    if resolved == "saver":
        return _format_lessons(lessons), "saver"
    return _full_context_index(lessons), "full_context"


def _format_lessons(lessons: list[LessonMeta]) -> str:
    """`saver` mode — the legacy first-25 truncation (id/title/track/level)."""
    if not lessons:
        return "(Lesson catalogue empty.)"
    lines: list[str] = []
    for m in lessons[:25]:
        lines.append(f"- {m.code}: {m.title} (id={m.id}, level={m.level})")
    if len(lessons) > 25:
        lines.append(f"- … and {len(lessons) - 25} more")
    return "\n".join(lines)


def _full_context_index(lessons: list[LessonMeta]) -> str:
    """`full_context` mode (CR020) — a compact index of EVERY lesson.

    One line per lesson (`CODE · id · title · topic · tags`), grouped by
    track for readability. Surfaces `topic` + `tags` — parsed today but
    read nowhere — so the LLM can pick the right lesson anywhere in the
    catalogue instead of being blind past the 25th.

    CR044 — the line leads with the group-scoped code ("TECH 12") rather than
    the bare number, because that is the identifier the user sees on the badge
    and can repeat back. The raw `id` stays on the line so a code the model
    garbles is still recoverable.
    """
    if not lessons:
        return "(Lesson catalogue empty.)"

    # Lazy import to keep the existing no-top-level-lessons_service_import
    # convention of this module (avoids any import-order coupling).
    from app.services.lessons_service import TRACK_TITLES

    by_track: dict[str, list[LessonMeta]] = {}
    for m in lessons:
        by_track.setdefault(m.track, []).append(m)

    # Known tracks first, in the taxonomy's own order; any unexpected
    # track slug trails after, alphabetically, so nothing is dropped.
    ordered = [t for t in TRACK_TITLES if t in by_track]
    ordered += sorted(t for t in by_track if t not in TRACK_TITLES)

    lines: list[str] = []
    for track in ordered:
        title = TRACK_TITLES.get(track, track.replace("_", " ").title())
        lines.append(f"[{title}]")
        for m in sorted(by_track[track], key=lambda x: (x.number, x.id)):
            tags = ", ".join(m.tags) if m.tags else "—"
            lines.append(f"{m.code} · {m.id} · {m.title} · {m.topic} · {tags}")
        lines.append("")  # blank line between track groups

    return "\n".join(lines).rstrip("\n")


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

    Matches against every DISPLAY agent, not just unlocked ones, so we can tell
    the user "X is still locked" instead of pretending it doesn't exist.
    Iterates TWELVE_AGENT_IDS rather than the enum: the enum also carries
    internal compute identities with no display name (CR201's RISK_OFFICER, the
    CONCIERGE itself), which are not agents a user can be routed to — and
    `AGENT_DISPLAY_NAMES[a]` on one of them is a KeyError, by design.
    Returns the agent_id string if mentioned and unlocked; None otherwise.
    """
    for a in TWELVE_AGENT_IDS:
        phrase = a.value.replace("_", " ")
        display = AGENT_DISPLAY_NAMES[a].lower()
        if (phrase in message or display in message) and a.value in unlocked:
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
            "briefing update, and lesson pass lands there automatically. "
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
) -> tuple[list[JournalEntry], set[str], list[LessonMeta], list[Any]]:
    """Pull (recent_journal, unlocked_agents, available_lessons, unlock_requirements).

    Best-effort: any data-layer failure returns empty collections rather
    than killing the chat stream. Anonymous (no user_id) users get an
    empty journal + activations but still see the lesson catalogue.
    """
    journal: list[JournalEntry] = []
    activations: set[str] = set()
    lessons: list[LessonMeta] = []
    requirements: list[Any] = []

    try:
        from app.services.lessons_service import get_lessons_service

        lessons_service = get_lessons_service()
        lessons = lessons_service.all_meta()
        if user_id is not None:
            activations = {a.agent_id for a in lessons_service.list_activations(user_id)}
            # DEF068 — anonymous users get no requirements block rather than one
            # computed against a nonexistent progress row: _format_unlock_paths
            # renders an explicit "unavailable, don't guess" line for the empty
            # case, which is the honest answer for a user with no account.
            requirements = lessons_service.unlock_requirements(user_id)
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

    return journal, activations, lessons, requirements
