"""Lessons + Agent Academy schemas.

Lessons are MDX files in content/lessons/ with YAML frontmatter. The backend
parses them on startup, exposes a catalogue, a per-lesson reader, and tracks
per-user progress in memory (Postgres at W7).

Each lesson ends with one or more <Quiz> components — we extract them
server-side and serve them as structured questions so the Flutter client
doesn't need an MDX parser.

Agent Academy modules are the Earn-Path unlock path: passing every quiz in
a track of lessons tied to an `agent_callouts` agent activates that agent.

Spec:
  - docs/04_education/lessons.md
  - docs/04_education/agent_academy.md
  - docs/04_education/dual_gating.md
"""

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class QuizQuestion(BaseModel):
    id: str
    question: str
    options: list[str]
    answer_index: int
    explanation: str | None = None


class LessonBlock(BaseModel):
    """A single block of rendered content — prose, quiz, ChatWith, or Animation.

    `animation_name` is the registry key the client uses to look up a Lottie
    asset. Missing names render the AmiHexPlaceholder so lessons referencing
    not-yet-bundled animations still display (A21 decouples content delivery
    from animation production).
    """

    kind: Literal["markdown", "quiz", "chat_with", "animation"]
    markdown: str | None = None  # for kind == markdown
    quiz: QuizQuestion | None = None  # for kind == quiz
    chat_with_agent: str | None = None  # for kind == chat_with
    animation_name: str | None = None  # for kind == animation


class LessonMeta(BaseModel):
    id: str
    title: str
    duration_min: int
    level: int
    track: str
    topic: str
    # `module` and `difficulty` are introduced by the W18 curriculum_map. Legacy
    # lessons authored pre-W18 don't declare them; the loader defaults module=0
    # ("uncategorised / legacy") and difficulty=<level> so the catalogue stays
    # backward-compatible while new lessons populate both explicitly.
    module: int = 0
    difficulty: int = 0
    prerequisites: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    agent_callouts: list[str] = Field(default_factory=list)
    locale_versions: list[str] = Field(default_factory=lambda: ["en"])


class Lesson(BaseModel):
    """Full lesson, ready for the reader UI."""

    meta: LessonMeta
    blocks: list[LessonBlock]
    quizzes: list[QuizQuestion]


class TrackCatalogue(BaseModel):
    track: str
    title: str
    lessons: list[LessonMeta]


class LessonCatalogue(BaseModel):
    tracks: list[TrackCatalogue]
    total_lessons: int


# ── Progress ────────────────────────────────────────────────────────────


class LessonStatus(BaseModel):
    """Per-user, per-lesson status."""

    model_config = ConfigDict(use_enum_values=True)

    user_id: UUID
    lesson_id: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    quiz_attempts: int = 0
    quiz_passed: bool = False
    last_quiz_score: float | None = None  # 0.0..1.0


class QuizSubmitRequest(BaseModel):
    user_id: UUID
    lesson_id: str
    # answers[i] is the chosen option_index for question i
    answers: list[int]


class QuizSubmitResponse(BaseModel):
    lesson_id: str
    correct: int
    total: int
    passed: bool
    score: float  # 0.0..1.0
    per_question: list[dict]  # [{"correct": True, "explanation": "..."}]
    unlocked_agents: list[str] = Field(default_factory=list)  # any agents activated as a side effect


class StartLessonRequest(BaseModel):
    user_id: UUID
    lesson_id: str


class ProgressSummary(BaseModel):
    """Whole-app progress for the user dashboard."""

    user_id: UUID
    lessons_completed: int
    lessons_total: int
    by_track: dict[str, dict[str, int]]  # track -> {"completed": N, "total": M}
    agents_unlocked: list[str]
    next_recommended_lesson: str | None = None


# ── Agent activation (Earn Path) ────────────────────────────────────────


class AgentActivationRecord(BaseModel):
    """Concrete activation record kept in memory.

    A user 'earns' an agent when they pass the quiz in EVERY lesson whose
    `agent_callouts` includes that agent's id. This is the MVP rule; v1.0
    introduces the full 4-part Agent Academy module flow.
    """

    model_config = ConfigDict(use_enum_values=True)

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    agent_id: str
    activation_method: Literal["earn_path", "skip_path", "trial", "founder_grant"]
    activated_at: datetime = Field(default_factory=_utcnow)
    triggering_lesson_id: str | None = None
