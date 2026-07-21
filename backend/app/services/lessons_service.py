"""Lessons + Agent Academy service.

Parses content/lessons/*.en.mdx on import; serves a catalogue, individual
lessons (with extracted quizzes), and per-user progress. Quiz pass on a
lesson that has `agent_callouts: [agent_id]` contributes toward the
Earn-Path activation of that agent.

Activation rule (MVP): an agent is earned when the user has passed the
quiz on EVERY lesson in the catalogue that lists that agent in
`agent_callouts`. (At v1.0 this becomes the full 4-part Agent Academy
module — see docs/initial_specs/04_education/agent_academy.md.)

Persistence: lesson content is loaded from disk into memory (immutable,
small). Per-user progress + activations live in Postgres so a user's
streak survives backend restarts.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import UUID

import yaml
from sqlalchemy import delete, select

from app.core.logging import logger
from app.db import get_session, init_schema
from app.db.models import AgentActivationRow, LessonProgressRow
from app.services.agent_gateways import AGENT_GATEWAYS, GATEWAY_SIZE
from app.schemas.lessons import (
    AgentActivationRecord,
    AgentUnlockRequirement,
    GatewayLessonStatus,
    Lesson,
    LessonBlock,
    LessonCatalogue,
    LessonMeta,
    LessonStatus,
    ProgressSummary,
    QuizQuestion,
    QuizSubmitRequest,
    QuizSubmitResponse,
    TrackCatalogue,
)


CONTENT_LESSONS_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "content" / "lessons"
)


# DEF068 — the earn-path gateway set is curated per agent in agent_gateways.py,
# not derived from `agent_callouts` by id sort. `GATEWAY_SIZE` (5) is re-exported
# here because callers historically imported the size from this module.
#
# Callouts and gateways are now different things: `agent_callouts` says "this
# lesson involves that agent" (drives the tile's hex avatars), `gates_agents`
# says "passing this lesson counts toward unlocking them". market_analyst has
# 71 of the former and 5 of the latter.


TRACK_TITLES = {
    "foundations": "Foundations",
    "fundamentals_analysis": "Fundamentals Analysis",
    "technical_analysis": "Technical Analysis",
    "news_macro": "News & Macro",
    "sentiment_behaviour": "Sentiment & Behaviour",
    "risk_portfolio": "Risk & Portfolio Construction",
    "edge_process": "Edge & Process",
    # CR054 Wave 0 — new BOK tracks. Empty at Wave 0; Wave 1 fills them.
    "asset_classes": "Asset Classes",
    "economics_macro": "Economics & Macro",
    "quant_methods": "Quantitative Methods",
    "ethics_integrity": "Ethics & Integrity",
    # CR059 — net-new facets 5/6 (locked 13-facet taxonomy). Empty at wiring
    # time; content lands via CR058 (islamic_finance) and a later lane
    # (decision_evaluation).
    "islamic_finance": "Islamic Finance",
    "decision_evaluation": "Evaluating Analysis",
}


# CR044 — the prefix each track contributes to a lesson's `code`. Lives beside
# TRACK_TITLES because it is a property of the same taxonomy; `scripts/
# assign_lesson_codes.py` and the corpus test both read it from here so the
# stamped content and the guard can't disagree about what TECH means.
#
# `foundations -> CORE`, deliberately not `FND`: these codes get spoken aloud and
# typed into a chat box, and FND/FUND are one letter apart.
TRACK_PREFIX = {
    "foundations": "CORE",
    "fundamentals_analysis": "FUND",
    "technical_analysis": "TECH",
    "news_macro": "N&M",
    "sentiment_behaviour": "SENT",
    "risk_portfolio": "RISK",
    "edge_process": "EDGE",
    # CR054 Wave 0 — CR044 prefixes for the new BOK tracks. Chosen per CR054
    # §4.2: spoken aloud, unambiguous, no collision with an existing prefix
    # ("MACRO" over "MAC" to avoid confusion with an OS name, "ETHIC" over
    # "ETH" to stay clear of ethereum ticker chatter). Frozen from this point.
    "asset_classes": "ASST",
    "economics_macro": "MACRO",
    "quant_methods": "QUANT",
    "ethics_integrity": "ETHIC",
    # CR059 — frozen from wiring (CR059 §1 note): SHARIA over HALAL/ISLAM,
    # EVAL confirmed over the portfolio_construction swap. No collision with
    # any prefix above.
    "islamic_finance": "SHARIA",
    "decision_evaluation": "EVAL",
}


QUIZ_PASS_THRESHOLD = 1.0  # MVP: must get all questions right to pass
# (post-MVP: lower threshold + remedial micro-lesson loop per spec)


# ── MDX parsing ────────────────────────────────────────────────────────


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n+(.*)$", re.DOTALL)

# <Quiz ... /> with JSX-style attributes. We support multi-line attrs.
_QUIZ_RE = re.compile(
    r"<Quiz\s+(?P<attrs>.*?)\s*/>",
    re.DOTALL,
)

_CHATWITH_RE = re.compile(r'<ChatWith\s+agent\s*=\s*"(?P<agent>[^"]+)"\s*/>')

# A21 — Animation MDX component. The client resolves `name` through
# `AnimationRegistry`; unknown names render the hex placeholder so a lesson
# referencing a not-yet-bundled animation still ships.
_ANIMATION_RE = re.compile(r'<Animation\s+name\s*=\s*"(?P<name>[^"]+)"\s*/>')

# <Term id="glossary_id" /> — inline glossary reference. Substituted to a
# `{{term:id}}` token inside the prose so the client can render it inline
# within the paragraph flow (Text.rich with WidgetSpan), rather than as a
# separate block that breaks the surrounding sentence into vertical chunks.
_TERM_RE = re.compile(r'<Term\s+id\s*=\s*"(?P<id>[^"]+)"\s*/>')


def _inline_term_tokens(body: str) -> str:
    """Replace `<Term id="X"/>` with `{{term:X}}` inline tokens."""
    return _TERM_RE.sub(lambda m: f"{{{{term:{m.group('id')}}}}}", body)


def _parse_jsx_attrs(text: str) -> dict[str, Any]:
    """Tolerant parser for the small subset of JSX attribute syntax we use.

    Supports:
      foo="bar"                — string
      foo={42}                 — int / float
      foo={["a","b"]}          — list of strings
      foo={true}               — bool
    """
    attrs: dict[str, Any] = {}
    pos = 0
    while pos < len(text):
        m = re.search(r"(\w+)\s*=\s*", text[pos:])
        if m is None:
            break
        key = m.group(1)
        start = pos + m.end()
        if text[start] == '"':
            end = text.index('"', start + 1)
            attrs[key] = text[start + 1 : end]
            pos = end + 1
        elif text[start] == "{":
            depth = 0
            i = start
            while i < len(text):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            raw = text[start + 1 : i].strip()
            attrs[key] = _coerce_jsx_value(raw)
            pos = i + 1
        else:
            pos = start + 1
    return attrs


def _coerce_jsx_value(raw: str) -> Any:
    if raw == "true":
        return True
    if raw == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        # comma-separated quoted strings, possibly multiline
        items = re.findall(r'"((?:[^"\\]|\\.)*)"', inner)
        return [s.replace('\\"', '"') for s in items]
    return raw.strip('"')


def lesson_number(lesson_id: str) -> int:
    """CR018 — the lesson's canonical reference number, i.e. the numeric prefix
    of its id ('023_support_and_resistance' -> 23). Stable per lesson; returns
    0 when the id has no numeric prefix."""
    head = lesson_id.split("_", 1)[0]
    return int(head) if head.isdigit() else 0


def gateways_for_lesson(lesson_id: str) -> list[str]:
    """DEF068 — which agents this lesson gates. The inverse of AGENT_GATEWAYS.

    A lesson can gate more than one agent: `014_position_sizing_basics` gates both
    `trader` and `portfolio_manager`, and `290_position_sizing_basics` gates all
    three debators.
    """
    return sorted(a for a, ids in AGENT_GATEWAYS.items() if lesson_id in ids)


def parse_mdx(path: Path) -> Lesson:
    raw = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(raw)
    if not m:
        raise ValueError(f"Missing frontmatter in {path.name}")
    fm_raw, body = m.group(1), m.group(2)
    # Inline-tokenize <Term/> tags before block extraction so they ride
    # inside prose blocks rather than getting promoted to standalone blocks.
    body = _inline_term_tokens(body)
    fm = yaml.safe_load(fm_raw) or {}

    level = int(fm.get("level", 1))
    meta = LessonMeta(
        id=fm["id"],
        number=lesson_number(fm["id"]),
        title=fm["title"],
        duration_min=int(fm.get("duration_min", 3)),
        level=level,
        track=fm.get("track", "foundations"),
        # CR044 — the group-scoped display code ("TECH 12"). Frozen in frontmatter,
        # never derived: a recomputed per-track rank would renumber a whole track on
        # mid-corpus insertion. Empty string when absent rather than a fabricated
        # code — test_lesson_corpus_integrity fails the build on a missing one, so a
        # blank badge can never quietly ship (CLAUDE.md: degrade loudly).
        code=str(fm.get("code", "")),
        topic=fm.get("topic", "general"),
        # Legacy frontmatter omits module/difficulty — default per W18 spec:
        # module=0 marks uncategorised, difficulty falls back to level so
        # ordering still works in the curriculum-map view.
        module=int(fm.get("module", 0)),
        difficulty=int(fm.get("difficulty", level)),
        prerequisites=list(fm.get("prerequisites") or []),
        tags=list(fm.get("tags") or []),
        agent_callouts=list(fm.get("agent_callouts") or []),
        gates_agents=gateways_for_lesson(fm["id"]),
        locale_versions=list(fm.get("locale_versions") or ["en"]),
    )

    # Walk the body splitting it into prose / <Quiz/> / <ChatWith/> blocks.
    blocks: list[LessonBlock] = []
    quizzes: list[QuizQuestion] = []
    cursor = 0
    quiz_idx = 0

    # Build a list of (start, end, kind, payload) for all custom components,
    # in order of appearance, so we can interleave with prose.
    components: list[tuple[int, int, str, Any]] = []
    for match in _QUIZ_RE.finditer(body):
        attrs = _parse_jsx_attrs(match.group("attrs"))
        q = QuizQuestion(
            id=f"{meta.id}__q{quiz_idx}",
            question=str(attrs.get("question", "")),
            options=list(attrs.get("options") or []),
            answer_index=int(attrs.get("answer", 0)),
            explanation=attrs.get("explanation"),
        )
        components.append((match.start(), match.end(), "quiz", q))
        quizzes.append(q)
        quiz_idx += 1
    for match in _CHATWITH_RE.finditer(body):
        components.append((match.start(), match.end(), "chat_with", match.group("agent")))
    for match in _ANIMATION_RE.finditer(body):
        components.append((match.start(), match.end(), "animation", match.group("name")))
    components.sort(key=lambda t: t[0])

    for start, end, kind, payload in components:
        if start > cursor:
            md = body[cursor:start].strip()
            if md:
                blocks.append(LessonBlock(kind="markdown", markdown=md))
        if kind == "quiz":
            blocks.append(LessonBlock(kind="quiz", quiz=payload))
        elif kind == "chat_with":
            blocks.append(LessonBlock(kind="chat_with", chat_with_agent=payload))
        elif kind == "animation":
            blocks.append(LessonBlock(kind="animation", animation_name=payload))
        cursor = end
    if cursor < len(body):
        tail = body[cursor:].strip()
        if tail:
            blocks.append(LessonBlock(kind="markdown", markdown=tail))

    return Lesson(meta=meta, blocks=blocks, quizzes=quizzes)


# ── Service ─────────────────────────────────────────────────────────────


class LessonsService:
    def __init__(self, content_dir: Path = CONTENT_LESSONS_DIR) -> None:
        self._content_dir = content_dir
        self._lessons: dict[str, Lesson] = {}
        self._lock = RLock()
        self._reload()
        init_schema()

    def _reload(self) -> None:
        with self._lock:
            self._lessons.clear()
            for path in sorted(self._content_dir.glob("*.en.mdx")):
                try:
                    lesson = parse_mdx(path)
                    self._lessons[lesson.meta.id] = lesson
                except Exception as e:
                    logger.error("lesson_parse_failed", path=str(path), error=str(e))
            logger.info("lessons_loaded", count=len(self._lessons))

    def catalogue(self, locale: str = "en") -> LessonCatalogue:
        with self._lock:
            by_track: dict[str, list[LessonMeta]] = defaultdict(list)
            for lesson in self._lessons.values():
                if locale in lesson.meta.locale_versions:
                    by_track[lesson.meta.track].append(lesson.meta)
            tracks: list[TrackCatalogue] = []
            # Stable track order: foundations first, then by spec ordering
            ordered_tracks = [t for t in TRACK_TITLES if t in by_track] + [
                t for t in by_track if t not in TRACK_TITLES
            ]
            for t in ordered_tracks:
                lessons = sorted(by_track[t], key=lambda m: m.id)
                tracks.append(TrackCatalogue(
                    track=t,
                    title=TRACK_TITLES.get(t, t.replace("_", " ").title()),
                    lessons=lessons,
                ))
            total = sum(len(t.lessons) for t in tracks)
            return LessonCatalogue(tracks=tracks, total_lessons=total)

    def get(self, lesson_id: str) -> Lesson | None:
        with self._lock:
            return self._lessons.get(lesson_id)

    def all_meta(self) -> list[LessonMeta]:
        with self._lock:
            return [l.meta for l in self._lessons.values()]

    # ── progress ──────────────────────────────────────────────────────

    def _row_to_status(self, row: LessonProgressRow) -> LessonStatus:
        return LessonStatus(
            user_id=row.user_id,
            lesson_id=row.lesson_id,
            started_at=row.started_at,
            completed_at=row.completed_at,
            quiz_attempts=row.quiz_attempts,
            quiz_passed=row.quiz_passed,
            last_quiz_score=row.last_quiz_score,
        )

    def get_status(self, user_id: UUID, lesson_id: str) -> LessonStatus | None:
        with get_session() as s:
            row = s.execute(
                select(LessonProgressRow).where(
                    LessonProgressRow.user_id == user_id,
                    LessonProgressRow.lesson_id == lesson_id,
                )
            ).scalar_one_or_none()
            return self._row_to_status(row) if row else None

    def list_status(self, user_id: UUID) -> list[LessonStatus]:
        with get_session() as s:
            rows = s.execute(
                select(LessonProgressRow).where(LessonProgressRow.user_id == user_id)
            ).scalars().all()
            return [self._row_to_status(r) for r in rows]

    def mark_started(self, user_id: UUID, lesson_id: str) -> LessonStatus:
        with get_session() as s:
            row = s.execute(
                select(LessonProgressRow).where(
                    LessonProgressRow.user_id == user_id,
                    LessonProgressRow.lesson_id == lesson_id,
                )
            ).scalar_one_or_none()
            if row is not None and row.started_at is not None:
                return self._row_to_status(row)
            now = datetime.now(timezone.utc)
            if row is None:
                row = LessonProgressRow(
                    user_id=user_id, lesson_id=lesson_id, started_at=now,
                )
                s.add(row)
            else:
                row.started_at = row.started_at or now
            s.flush()
            return self._row_to_status(row)

    def submit_quiz(self, req: QuizSubmitRequest) -> QuizSubmitResponse:
        lesson = self.get(req.lesson_id)
        if lesson is None:
            raise ValueError(f"unknown lesson: {req.lesson_id}")
        total = len(lesson.quizzes)
        if len(req.answers) < total:
            req.answers = req.answers + [-1] * (total - len(req.answers))

        per_question: list[dict] = []
        correct = 0
        for q, given in zip(lesson.quizzes, req.answers):
            is_correct = given == q.answer_index
            if is_correct:
                correct += 1
            per_question.append({
                "question_id": q.id,
                "correct": is_correct,
                "correct_index": q.answer_index,
                "given_index": given,
                "explanation": q.explanation,
            })

        score = correct / total if total > 0 else 1.0
        passed = score >= QUIZ_PASS_THRESHOLD

        with get_session() as s:
            row = s.execute(
                select(LessonProgressRow).where(
                    LessonProgressRow.user_id == req.user_id,
                    LessonProgressRow.lesson_id == req.lesson_id,
                )
            ).scalar_one_or_none()
            now = datetime.now(timezone.utc)
            if row is None:
                row = LessonProgressRow(
                    user_id=req.user_id,
                    lesson_id=req.lesson_id,
                    started_at=now,
                    quiz_attempts=1,
                    quiz_passed=passed,
                    last_quiz_score=score,
                    completed_at=now if passed else None,
                )
                s.add(row)
            else:
                row.started_at = row.started_at or now
                row.quiz_attempts = row.quiz_attempts + 1
                row.quiz_passed = row.quiz_passed or passed
                row.last_quiz_score = score
                if passed and row.completed_at is None:
                    row.completed_at = now
            s.flush()

        unlocked: list[str] = []
        if passed:
            unlocked = self._check_agent_unlocks(req.user_id, lesson)

        return QuizSubmitResponse(
            lesson_id=req.lesson_id,
            correct=correct,
            total=total,
            passed=passed,
            score=score,
            per_question=per_question,
            unlocked_agents=unlocked,
        )

    # ── activation ────────────────────────────────────────────────────

    def _gateway_lessons_for_agent(self, agent_id: str) -> list[str]:
        """Return the curated gateway lesson ids for an agent (DEF068).

        Was: the first 3 lessons by id sort that mentioned the agent — a set
        nobody picked, which put `aggressive_debator`'s third gate at lesson 225
        of 292 and left a 50-lesson user at 0/3 on three agents. Now explicit,
        five per agent, in `agent_gateways.AGENT_GATEWAYS`.
        """
        return list(AGENT_GATEWAYS.get(agent_id, ()))

    def _check_agent_unlocks(self, user_id: UUID, just_completed: Lesson) -> list[str]:
        """For each agent gated by the just-completed lesson, check whether the
        user has now passed that agent's full curated gateway set. If yes — and
        the agent is not already activated — record the activation and return
        the agent ids.

        A bounded gateway set matters because the W18 + magical-edison content
        drop scaled lesson count from 13 → 270, and the most-referenced agents
        (market_analyst, fundamentals_analyst) now appear in 70+ lessons each.
        Requiring all of them is unreachable in practice; the gateway model keeps
        unlock cost bounded and predictable while the broader corpus reinforces.

        Iterates `gates_agents`, not `agent_callouts`: a lesson merely naming an
        agent can't complete a gate it isn't part of, and walking the callouts
        also meant `concierge` — 26 callouts, never gated in the UI — earned an
        `earn_path` row, which is why the two "/ 12" counters could read 13 of 12.
        """
        newly_unlocked: list[str] = []
        with get_session() as s:
            existing_ids = set(s.execute(
                select(AgentActivationRow.agent_id).where(
                    AgentActivationRow.user_id == user_id,
                )
            ).scalars().all())
            for agent_id in just_completed.meta.gates_agents:
                if agent_id in existing_ids:
                    continue
                required = self._gateway_lessons_for_agent(agent_id)
                if not required:
                    continue
                passed_rows = s.execute(
                    select(LessonProgressRow.lesson_id).where(
                        LessonProgressRow.user_id == user_id,
                        LessonProgressRow.lesson_id.in_(required),
                        LessonProgressRow.quiz_passed.is_(True),
                    )
                ).scalars().all()
                if len(set(passed_rows)) < len(set(required)):
                    continue
                s.add(AgentActivationRow(
                    user_id=user_id,
                    agent_id=agent_id,
                    activation_method="earn_path",
                    triggering_lesson_id=just_completed.meta.id,
                ))
                newly_unlocked.append(agent_id)
                logger.info(
                    "agent_unlocked_via_earn_path",
                    user_id=str(user_id),
                    agent_id=agent_id,
                    lessons_required=len(required),
                )
            s.flush()
        return newly_unlocked

    def list_activations(self, user_id: UUID) -> list[AgentActivationRecord]:
        with get_session() as s:
            rows = s.execute(
                select(AgentActivationRow).where(AgentActivationRow.user_id == user_id)
            ).scalars().all()
            return [
                AgentActivationRecord(
                    id=r.id,
                    user_id=r.user_id,
                    agent_id=r.agent_id,
                    activation_method=r.activation_method,  # type: ignore[arg-type]
                    activated_at=r.activated_at,
                    triggering_lesson_id=r.triggering_lesson_id,
                )
                for r in rows
            ]

    def unlock_requirements(self, user_id: UUID) -> list[AgentUnlockRequirement]:
        """DEF068 — per agent, the gateway lessons and which of them this user has passed.

        One query for the whole set rather than per agent: the gateway lessons across
        all 12 agents are ~50 ids, and a locked-agent sheet that had to fan out 12
        requests to render would be worse than the client-side derivation it replaces.
        """
        required_ids = {i for ids in AGENT_GATEWAYS.values() for i in ids}
        with get_session() as s:
            passed = set(s.execute(
                select(LessonProgressRow.lesson_id).where(
                    LessonProgressRow.user_id == user_id,
                    LessonProgressRow.lesson_id.in_(required_ids),
                    LessonProgressRow.quiz_passed.is_(True),
                )
            ).scalars().all())
            unlocked = set(s.execute(
                select(AgentActivationRow.agent_id).where(
                    AgentActivationRow.user_id == user_id,
                )
            ).scalars().all())

        out: list[AgentUnlockRequirement] = []
        for agent_id, ids in AGENT_GATEWAYS.items():
            lessons: list[GatewayLessonStatus] = []
            for lesson_id in ids:
                lesson = self._lessons.get(lesson_id)
                if lesson is None:
                    # Guarded by test_lesson_corpus_integrity, so this is a
                    # can't-happen. Skipping silently would understate the gate and
                    # show the user a shorter checklist than they actually face.
                    logger.error(
                        "gateway_lesson_missing_from_corpus",
                        agent_id=agent_id,
                        lesson_id=lesson_id,
                    )
                    continue
                lessons.append(GatewayLessonStatus(
                    lesson_id=lesson_id,
                    code=lesson.meta.code,
                    title=lesson.meta.title,
                    track=lesson.meta.track,
                    passed=lesson_id in passed,
                ))
            done = sum(1 for l in lessons if l.passed)
            out.append(AgentUnlockRequirement(
                agent_id=agent_id,
                unlocked=agent_id in unlocked,
                required=lessons,
                passed_count=done,
                remaining_count=len(lessons) - done,
            ))
        return out

    def grant_activation(
        self,
        user_id: UUID,
        agent_id: str,
        method: str = "founder_grant",
    ) -> AgentActivationRecord:
        with get_session() as s:
            existing = s.execute(
                select(AgentActivationRow).where(
                    AgentActivationRow.user_id == user_id,
                    AgentActivationRow.agent_id == agent_id,
                )
            ).scalar_one_or_none()
            if existing is not None:
                return AgentActivationRecord(
                    id=existing.id,
                    user_id=existing.user_id,
                    agent_id=existing.agent_id,
                    activation_method=existing.activation_method,  # type: ignore[arg-type]
                    activated_at=existing.activated_at,
                    triggering_lesson_id=existing.triggering_lesson_id,
                )
            row = AgentActivationRow(
                user_id=user_id,
                agent_id=agent_id,
                activation_method=method,
            )
            s.add(row)
            s.flush()
            return AgentActivationRecord(
                id=row.id,
                user_id=row.user_id,
                agent_id=row.agent_id,
                activation_method=row.activation_method,  # type: ignore[arg-type]
                activated_at=row.activated_at,
                triggering_lesson_id=row.triggering_lesson_id,
            )

    # ── progress summary ──────────────────────────────────────────────

    def progress_summary(self, user_id: UUID) -> ProgressSummary:
        cat = self.catalogue()
        by_track: dict[str, dict[str, int]] = {}
        completed_total = 0
        all_total = 0
        first_incomplete: str | None = None
        for tc in cat.tracks:
            done_in_track = 0
            for meta in tc.lessons:
                all_total += 1
                status = self.get_status(user_id, meta.id)
                if status and status.quiz_passed:
                    done_in_track += 1
                elif first_incomplete is None:
                    # respect prerequisites
                    prereqs_ok = all(
                        (self.get_status(user_id, p) or LessonStatus(
                            user_id=user_id, lesson_id=p,
                        )).quiz_passed
                        for p in meta.prerequisites
                    )
                    if prereqs_ok:
                        first_incomplete = meta.id
            by_track[tc.track] = {"completed": done_in_track, "total": len(tc.lessons)}
            completed_total += done_in_track
        return ProgressSummary(
            user_id=user_id,
            lessons_completed=completed_total,
            lessons_total=all_total,
            by_track=by_track,
            agents_unlocked=[a.agent_id for a in self.list_activations(user_id)],
            next_recommended_lesson=first_incomplete,
        )

    # Test helper
    def clear(self) -> None:
        with get_session() as s:
            s.execute(delete(LessonProgressRow))
            s.execute(delete(AgentActivationRow))


_service: LessonsService | None = None


def get_lessons_service() -> LessonsService:
    global _service
    if _service is None:
        _service = LessonsService()
    return _service
