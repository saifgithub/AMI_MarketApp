"""Lessons + Agent Academy endpoints.

GET   /v1/lessons                                catalogue (all tracks)
GET   /v1/lessons/{lesson_id}                    full lesson with blocks + quiz
POST  /v1/lessons/start                          mark started
POST  /v1/lessons/quiz                           submit answers; returns score + any unlocks
GET   /v1/lessons/progress/{user_id}             whole-app progress summary
GET   /v1/lessons/activations/{user_id}          unlocked-agent records
POST  /v1/lessons/activations/grant              founder grant (skip path testing)
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.schemas import AgentId
from app.schemas.journal import EntryType, JournalEntryCreate
from app.schemas.lessons import (
    AgentActivationRecord,
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
    svc: LessonsService = Depends(get_lessons_service),
) -> ProgressSummary:
    return svc.progress_summary(user_id)


@router.get("/activations/{user_id}", response_model=list[AgentActivationRecord])
async def activations(
    user_id: UUID,
    svc: LessonsService = Depends(get_lessons_service),
) -> list[AgentActivationRecord]:
    return svc.list_activations(user_id)


class GrantRequest(BaseModel):
    user_id: UUID
    agent_id: AgentId
    method: str = "founder_grant"


@router.post("/activations/grant", response_model=AgentActivationRecord)
async def grant_activation(
    req: GrantRequest,
    svc: LessonsService = Depends(get_lessons_service),
) -> AgentActivationRecord:
    return svc.grant_activation(req.user_id, req.agent_id.value, method=req.method)


@router.post("/start", response_model=LessonStatus)
async def start_lesson(
    req: StartLessonRequest,
    svc: LessonsService = Depends(get_lessons_service),
) -> LessonStatus:
    if svc.get(req.lesson_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"lesson {req.lesson_id} not found")
    return svc.mark_started(req.user_id, req.lesson_id)


@router.post("/quiz", response_model=QuizSubmitResponse)
async def submit_quiz(
    req: QuizSubmitRequest,
    svc: LessonsService = Depends(get_lessons_service),
) -> QuizSubmitResponse:
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
