"""Lessons + Agent Academy endpoints.

GET   /v1/lessons                                catalogue (all tracks)
GET   /v1/lessons/{lesson_id}                    full lesson with blocks + quiz
POST  /v1/lessons/start                          mark started
POST  /v1/lessons/quiz                           submit answers; returns score + any unlocks
GET   /v1/lessons/progress/{user_id}             whole-app progress summary
GET   /v1/lessons/progress/{user_id}/by_lesson   per-lesson status list (for three-tier sort)
GET   /v1/lessons/activations/{user_id}          unlocked-agent records
POST  /v1/lessons/activations/grant              founder grant (skip path testing)
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.journal import EntryType, JournalEntryCreate
from app.schemas.lessons import (
    AgentActivationRecord,
    AgentUnlockRequirement,
    Lesson,
    LessonCatalogue,
    LessonStatus,
    ProgressSummary,
    QuizSubmitRequest,
    QuizSubmitResponse,
    StartLessonRequest,
)
from app.services.journal_store import get_journal_store
from app.services.lessons_service import LessonsService, get_lessons_service
from app.services.reputation_service import get_reputation_service
from app.api.dependencies import get_current_user
from app.db import get_session
from app.db.models import User


router = APIRouter(prefix="/v1/lessons", tags=["lessons"])


@router.get("", response_model=LessonCatalogue)
async def catalogue(
    locale: str = "en",
    svc: LessonsService = Depends(get_lessons_service),
) -> LessonCatalogue:
    return svc.catalogue(locale=locale)


@router.get("/progress/{user_id}", response_model=ProgressSummary)
async def progress(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    svc: LessonsService = Depends(get_lessons_service),
) -> ProgressSummary:
    if current_user.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")
    return svc.progress_summary(user_id)


@router.get("/progress/{user_id}/by_lesson", response_model=list[LessonStatus])
async def progress_by_lesson(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    svc: LessonsService = Depends(get_lessons_service),
) -> list[LessonStatus]:
    if current_user.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")
    return svc.list_status(user_id)


@router.get("/requirements/{user_id}", response_model=list[AgentUnlockRequirement])
async def unlock_requirements(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    svc: LessonsService = Depends(get_lessons_service),
) -> list[AgentUnlockRequirement]:
    """DEF068 — the authoritative "what do I still need to unlock each agent".

    The locked-agent sheet used to answer this itself, by filtering the catalogue
    on `agent_callouts` and taking the first N behind a hardcoded copy of the
    gateway size. That derivation is gone; this is the only source now.
    """
    if current_user.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")
    return svc.unlock_requirements(user_id)


@router.get("/activations/{user_id}", response_model=list[AgentActivationRecord])
async def activations(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    svc: LessonsService = Depends(get_lessons_service),
) -> list[AgentActivationRecord]:
    if current_user.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")
    return svc.list_activations(user_id)


# Adversarial audit (2026-05-18) finding A5: `POST /v1/lessons/activations/grant`
# was unauthenticated and accepted any user_id, letting anyone unlock any agent
# for any user. The route is removed; founder grants happen via psql when needed:
#   INSERT INTO agent_activations (user_id, agent_id, method, granted_at)
#   VALUES ('<uuid>', '<agent_id>', 'founder_grant', NOW());


@router.post("/start", response_model=LessonStatus)
async def start_lesson(
    req: StartLessonRequest,
    current_user: User = Depends(get_current_user),
    svc: LessonsService = Depends(get_lessons_service),
) -> LessonStatus:
    if current_user.id != req.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")
    if svc.get(req.lesson_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"lesson {req.lesson_id} not found")
    return svc.mark_started(req.user_id, req.lesson_id)


@router.post("/quiz", response_model=QuizSubmitResponse)
async def submit_quiz(
    req: QuizSubmitRequest,
    current_user: User = Depends(get_current_user),
    svc: LessonsService = Depends(get_lessons_service),
) -> QuizSubmitResponse:
    if current_user.id != req.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")
    try:
        result = svc.submit_quiz(req)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))

    if result.passed:
        # Capture lesson completion to the journal
        lesson = svc.get(req.lesson_id)
        title = lesson.meta.title if lesson else req.lesson_id
        try:
            get_journal_store().append(JournalEntryCreate(
                user_id=req.user_id,
                entry_type=EntryType.LESSON_COMPLETE,
                reference_id=None,
                title=f"Completed lesson — {title}",
                summary=f"Score {int(result.score * 100)}%. "
                        f"{'Unlocked: ' + ', '.join(result.unlocked_agents) if result.unlocked_agents else ''}",
                tags=["lesson", lesson.meta.track if lesson else "general"],
                payload={"score": result.score},
            ))
        except Exception:  # pragma: no cover
            pass
        for agent_id in result.unlocked_agents:
            try:
                get_journal_store().append(JournalEntryCreate(
                    user_id=req.user_id,
                    entry_type=EntryType.AGENT_UNLOCK,
                    title=f"Unlocked {agent_id.replace('_', ' ').title()}",
                    summary=f"Earned via {title}.",
                    agents_involved=[agent_id],
                    tags=["unlock", "earn_path"],
                ))
            except Exception:  # pragma: no cover
                pass
        # Reputation (CR004): ref dedup makes re-passes free — only the
        # first pass of a lesson / first unlock of an agent grants.
        try:
            with get_session() as s:
                rep = get_reputation_service()
                rep.award(
                    s, user_id=req.user_id,
                    event_type="lesson_passed", ref_id=req.lesson_id,
                )
                for agent_id in result.unlocked_agents:
                    rep.award(
                        s, user_id=req.user_id,
                        event_type="agent_unlocked", ref_id=agent_id,
                    )
        except Exception:  # pragma: no cover
            pass
    return result


@router.get("/{lesson_id}", response_model=Lesson)
async def get_lesson(
    lesson_id: str,
    svc: LessonsService = Depends(get_lessons_service),
) -> Lesson:
    lesson = svc.get(lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"lesson {lesson_id} not found")
    return lesson
