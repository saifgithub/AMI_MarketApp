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
  - docs/initial_specs/04_education/lessons.md
  - docs/initial_specs/04_education/agent_academy.md
  - docs/initial_specs/04_education/dual_gating.md
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Track(str, Enum):
    """Canonical curriculum-track ids.

    Single source of truth for the set of valid tracks. `TRACK_TITLES` and
    `TRACK_PREFIX` in `lessons_service.py` extend each value with its display
    name and its frozen CR044 spoken-code prefix; a value here without an
    entry in those maps is caught by `test_lesson_corpus_integrity`.

    `LessonMeta.track` stays typed as `str` so already-authored MDX frontmatter
    loads unchanged — this enum names the tracks, it does not (yet) validate
    the field on parse.
    """

    foundations = "foundations"
    fundamentals_analysis = "fundamentals_analysis"
    technical_analysis = "technical_analysis"
    news_macro = "news_macro"
    sentiment_behaviour = "sentiment_behaviour"
    risk_portfolio = "risk_portfolio"
    edge_process = "edge_process"
    # CR054 Wave 0 — new BOK tracks. Empty at Wave 0 (0 lessons each); filled
    # by Wave 1 content lanes owned by noncoder.edu. Additive only: existing
    # tracks and CR044 codes are untouched.
    asset_classes = "asset_classes"
    economics_macro = "economics_macro"
    quant_methods = "quant_methods"
    ethics_integrity = "ethics_integrity"


class QuizQuestion(BaseModel):
    id: str
    question: str
    options: list[str]
    answer_index: int
    explanation: str | None = None


class LessonBlock(BaseModel):
    """A single block of rendered content — prose, quiz, ChatWith, Animation, or Term.

    `animation_name` is the registry key the client uses to look up a Lottie
    asset. Missing names render the AmiHexPlaceholder so lessons referencing
    not-yet-bundled animations still display (A21 decouples content delivery
    from animation production).

    `term_id` is the glossary id from `<Term id="…"/>`. The client resolves
    it through its bundled TermRegistry; unknown ids fall back to plain
    bold text so a typo never crashes the reader.
    """

    kind: Literal["markdown", "quiz", "chat_with", "animation", "term"]
    markdown: str | None = None  # for kind == markdown
    quiz: QuizQuestion | None = None  # for kind == quiz
    chat_with_agent: str | None = None  # for kind == chat_with
    animation_name: str | None = None  # for kind == animation
    term_id: str | None = None  # for kind == term


class LessonMeta(BaseModel):
    id: str
    # CR018: the lesson's canonical reference number = the numeric prefix of
    # its `id` (e.g. "023_support_and_resistance" -> 23). Derived at load time
    # from the id, so no content/frontmatter change. Stable per lesson (a
    # recomputed sequence would drift as lessons are added/removed). 0 when the
    # id has no numeric prefix.
    number: int = 0
    title: str
    duration_min: int
    level: int
    track: str
    # CR044: the group-scoped code the user actually says out loud — "TECH 12",
    # "N&M 22". `<track prefix> <n>` with n contiguous 1..N inside the track,
    # authored into frontmatter and frozen there. Distinct from `number`, which
    # stays the id-derived identity + sort key: swapping the catalogue's sort to
    # code order would reorder the curriculum away from its journey sequence.
    code: str = ""
    topic: str
    # CR044/DEF068: the agents this lesson gates, derived at load from
    # AGENT_GATEWAYS. Display metadata so the lesson list can mark the 5 that
    # unlock an agent — before this, a gateway lesson was visually identical to
    # the dozens that merely name the agent in `agent_callouts`.
    gates_agents: list[str] = Field(default_factory=list)
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


class GatewayLessonStatus(BaseModel):
    """One lesson in an agent's gateway set, with this user's progress on it."""

    lesson_id: str
    code: str
    title: str
    track: str
    passed: bool


class AgentUnlockRequirement(BaseModel):
    """DEF068 — what this user still has to pass to unlock one agent.

    Exists because nothing used to answer this. `progress` returned only
    `agents_unlocked`, `activations` only unlocked agents, and `QuizSubmitResponse`
    only what a single submit unlocked — so the client re-derived the gateway set
    itself behind a hardcoded copy of the gateway size. It is authoritative now;
    the client renders it rather than computing it.
    """

    agent_id: str
    unlocked: bool
    required: list[GatewayLessonStatus]
    passed_count: int
    remaining_count: int


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
