"""Lessons + Agent Academy service.

Parses content/lessons/*.en.mdx on import; serves a catalogue, individual
lessons (with extracted quizzes), and per-user progress. Quiz pass on a
lesson that has `agent_callouts: [agent_id]` contributes toward the
Earn-Path activation of that agent.

Activation rule (MVP): an agent is earned when the user has passed the
quiz on EVERY lesson in the catalogue that lists that agent in
`agent_callouts`. (At v1.0 this becomes the full 4-part Agent Academy
module — see docs/04_education/agent_academy.md.)
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

from app.core.logging import logger
from app.schemas.lessons import (
    AgentActivationRecord,
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


TRACK_TITLES = {
    "foundations": "Foundations",
    "fundamentals_analysis": "Fundamentals Analysis",
    "technical_analysis": "Technical Analysis",
    "news_macro": "News & Macro",
    "sentiment_behaviour": "Sentiment & Behaviour",
    "risk_portfolio": "Risk & Portfolio Construction",
    "edge_process": "Edge & Process",
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


def parse_mdx(path: Path) -> Lesson:
    raw = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(raw)
    if not m:
        raise ValueError(f"Missing frontmatter in {path.name}")
    fm_raw, body = m.group(1), m.group(2)
    fm = yaml.safe_load(fm_raw) or {}

    meta = LessonMeta(
        id=fm["id"],
        title=fm["title"],
        duration_min=int(fm.get("duration_min", 3)),
        level=int(fm.get("level", 1)),
        track=fm.get("track", "foundations"),
        topic=fm.get("topic", "general"),
        prerequisites=list(fm.get("prerequisites") or []),
        tags=list(fm.get("tags") or []),
        agent_callouts=list(fm.get("agent_callouts") or []),
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
        # progress[(user_id, lesson_id)] = LessonStatus
        self._progress: dict[tuple[UUID, str], LessonStatus] = {}
        # activations[user_id] = {agent_id: AgentActivationRecord}
        self._activations: dict[UUID, dict[str, AgentActivationRecord]] = defaultdict(dict)
        self._reload()

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

    def get_status(self, user_id: UUID, lesson_id: str) -> LessonStatus | None:
        with self._lock:
            return self._progress.get((user_id, lesson_id))

    def list_status(self, user_id: UUID) -> list[LessonStatus]:
        with self._lock:
            return [s for (uid, _), s in self._progress.items() if uid == user_id]

    def mark_started(self, user_id: UUID, lesson_id: str) -> LessonStatus:
        with self._lock:
            key = (user_id, lesson_id)
            existing = self._progress.get(key)
            if existing is not None and existing.started_at is not None:
                return existing
            status = existing or LessonStatus(user_id=user_id, lesson_id=lesson_id)
            self._progress[key] = status.model_copy(update={
                "started_at": status.started_at or datetime.now(timezone.utc),
            })
            return self._progress[key]

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

        with self._lock:
            key = (req.user_id, req.lesson_id)
            prev = self._progress.get(key) or LessonStatus(
                user_id=req.user_id, lesson_id=req.lesson_id
            )
            updated = prev.model_copy(update={
                "quiz_attempts": prev.quiz_attempts + 1,
                "quiz_passed": prev.quiz_passed or passed,
                "last_quiz_score": score,
                "completed_at": (
                    prev.completed_at
                    or (datetime.now(timezone.utc) if passed else None)
                ),
                "started_at": prev.started_at or datetime.now(timezone.utc),
            })
            self._progress[key] = updated

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

    def _check_agent_unlocks(self, user_id: UUID, just_completed: Lesson) -> list[str]:
        """For each agent referenced by the just-completed lesson, check
        whether the user has now passed EVERY lesson that calls out that
        agent. If yes — and the agent is not already activated — record
        the activation and return the agent ids.
        """
        newly_unlocked: list[str] = []
        for agent_id in just_completed.meta.agent_callouts:
            if agent_id in self._activations[user_id]:
                continue
            required = [
                l.meta.id
                for l in self._lessons.values()
                if agent_id in l.meta.agent_callouts
            ]
            done = [
                lid for lid in required
                if (self._progress.get((user_id, lid)) or LessonStatus(
                    user_id=user_id, lesson_id=lid
                )).quiz_passed
            ]
            if len(done) >= len(required) and required:
                rec = AgentActivationRecord(
                    user_id=user_id,
                    agent_id=agent_id,
                    activation_method="earn_path",
                    triggering_lesson_id=just_completed.meta.id,
                )
                self._activations[user_id][agent_id] = rec
                newly_unlocked.append(agent_id)
                logger.info(
                    "agent_unlocked_via_earn_path",
                    user_id=str(user_id),
                    agent_id=agent_id,
                    lessons_required=len(required),
                )
        return newly_unlocked

    def list_activations(self, user_id: UUID) -> list[AgentActivationRecord]:
        with self._lock:
            return list(self._activations.get(user_id, {}).values())

    def grant_activation(
        self,
        user_id: UUID,
        agent_id: str,
        method: str = "founder_grant",
    ) -> AgentActivationRecord:
        with self._lock:
            rec = AgentActivationRecord(
                user_id=user_id,
                agent_id=agent_id,
                activation_method=method,  # type: ignore[arg-type]
            )
            self._activations[user_id][agent_id] = rec
            return rec

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
        with self._lock:
            self._progress.clear()
            self._activations.clear()


_service: LessonsService | None = None


def get_lessons_service() -> LessonsService:
    global _service
    if _service is None:
        _service = LessonsService()
    return _service
