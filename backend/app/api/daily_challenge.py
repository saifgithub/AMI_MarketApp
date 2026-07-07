"""Daily-challenge endpoints.

GET  /v1/daily_challenge/today              today's challenge (Asia/KL TZ)
GET  /v1/daily_challenge/by_date/YYYY-MM-DD specific date
GET  /v1/daily_challenge/by_id/{id}         specific challenge by id
GET  /v1/daily_challenge/all                full list (admin / debugging)
POST /v1/daily_challenge/{cid}/attempt      record an attempt + journal it (BL10)
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.dependencies import get_current_user, get_current_user_optional
from app.db import get_session
from app.db.models import DailyChallengeAttemptRow, User
from app.schemas.daily_challenge import (
    DailyChallenge,
    DailyChallengeListResponse,
    DailyChallengeResponse,
    MyAttempt,
)
from app.schemas.journal import EntryType, JournalEntryCreate, Outcome
from app.services.daily_challenge_service import (
    DailyChallengeService,
    get_daily_challenge_service,
)
from app.services.journal_store import get_journal_store
from app.services.reputation_service import get_reputation_service


router = APIRouter(prefix="/v1/daily_challenge", tags=["daily_challenge"])


def _stored_attempt(session, user_id, challenge_id) -> DailyChallengeAttemptRow | None:
    return session.execute(
        select(DailyChallengeAttemptRow).where(
            DailyChallengeAttemptRow.user_id == user_id,
            DailyChallengeAttemptRow.challenge_id == challenge_id,
        )
    ).scalar_one_or_none()


@router.get("/today", response_model=DailyChallengeResponse)
async def today(
    current_user: User | None = Depends(get_current_user_optional),
    svc: DailyChallengeService = Depends(get_daily_challenge_service),
) -> DailyChallengeResponse:
    ch, d = svc.today()
    if ch is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"no daily challenge for {d.isoformat()}",
        )
    my_attempt = None
    if current_user is not None:
        with get_session() as s:
            row = _stored_attempt(s, current_user.id, ch.id)
            if row is not None:
                my_attempt = MyAttempt(
                    selected_option=row.selected_option,
                    correct=row.correct,
                    attempted_at=row.created_at.isoformat(),
                )
    return DailyChallengeResponse(
        challenge=ch, date=d.isoformat(), my_attempt=my_attempt,
    )


@router.get("/by_date/{ymd}", response_model=DailyChallengeResponse)
async def by_date(
    ymd: str,
    svc: DailyChallengeService = Depends(get_daily_challenge_service),
) -> DailyChallengeResponse:
    try:
        d = datetime.strptime(ymd, "%Y-%m-%d").date()
    except ValueError as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"date must be YYYY-MM-DD: {e}",
        ) from e
    ch = svc.for_date(d)
    if ch is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"no daily challenge for {d.isoformat()}",
        )
    return DailyChallengeResponse(challenge=ch, date=d.isoformat())


@router.get("/by_id/{challenge_id}", response_model=DailyChallenge)
async def by_id(
    challenge_id: str,
    svc: DailyChallengeService = Depends(get_daily_challenge_service),
) -> DailyChallenge:
    ch = svc.get_by_id(challenge_id)
    if ch is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"daily challenge {challenge_id} not found",
        )
    return ch


@router.get("/all", response_model=DailyChallengeListResponse)
async def all_challenges(
    svc: DailyChallengeService = Depends(get_daily_challenge_service),
) -> DailyChallengeListResponse:
    items = svc.all_challenges()
    return DailyChallengeListResponse(items=items, total=len(items))


class DailyChallengeAttemptRequest(BaseModel):
    selected_option: int = Field(ge=0)


class DailyChallengeAttemptResponse(BaseModel):
    correct: bool
    correct_option: int
    explanation: str
    related_lesson: str | None = None
    related_agent: str | None = None
    # CR004: true when this challenge was already answered — the response
    # then carries the STORED result, not a re-grade of the new answer.
    already_attempted: bool = False
    selected_option: int = 0


@router.post("/{cid}/attempt", response_model=DailyChallengeAttemptResponse)
async def attempt(
    cid: str,
    req: DailyChallengeAttemptRequest,
    current_user: User = Depends(get_current_user),
    svc: DailyChallengeService = Depends(get_daily_challenge_service),
) -> DailyChallengeAttemptResponse:
    """BL10 + CR004: record a daily-challenge attempt (one per user per
    challenge — server truth), award reputation, and journal it. A repeat
    submission returns the stored result with already_attempted=true (the
    mobile card renders result-of-the-day; friendlier than a 409).
    """
    ch = svc.get_by_id(cid)
    if ch is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"daily challenge {cid} not found",
        )
    if req.selected_option >= len(ch.options):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"selected_option out of range (challenge has {len(ch.options)} options)",
        )

    correct = req.selected_option == ch.answer

    with get_session() as s:
        existing = _stored_attempt(s, current_user.id, cid)
        if existing is not None:
            return DailyChallengeAttemptResponse(
                correct=existing.correct,
                correct_option=ch.answer,
                explanation=ch.explanation,
                related_lesson=ch.related_lesson,
                related_agent=ch.related_agent,
                already_attempted=True,
                selected_option=existing.selected_option,
            )
        s.add(DailyChallengeAttemptRow(
            user_id=current_user.id,
            challenge_id=cid,
            selected_option=req.selected_option,
            correct=correct,
        ))
        rep = get_reputation_service()
        rep.award(
            s, user_id=current_user.id,
            event_type="challenge_attempted", ref_id=cid,
        )
        if correct:
            rep.award(
                s, user_id=current_user.id,
                event_type="challenge_correct", ref_id=cid,
            )

    # Journal capture — best-effort, never fail the request on a journal error.
    try:
        chosen = ch.options[req.selected_option]
        get_journal_store().append(JournalEntryCreate(
            user_id=current_user.id,
            entry_type=EntryType.DAILY_CHALLENGE,
            title=f"Daily Challenge — {ch.type.replace('_', ' ').title()}",
            summary=f"{'✓' if correct else '✗'} chose: {chosen}",
            tags=["daily_challenge", ch.type, "correct" if correct else "wrong"],
            outcome=Outcome.WIN if correct else Outcome.LOSS,
            payload={
                "challenge_id": ch.id,
                "selected_option": req.selected_option,
                "correct_option": ch.answer,
                "correct": correct,
                "type": ch.type,
                "difficulty": ch.difficulty,
            },
        ))
    except Exception:  # pragma: no cover
        pass

    return DailyChallengeAttemptResponse(
        correct=correct,
        correct_option=ch.answer,
        explanation=ch.explanation,
        related_lesson=ch.related_lesson,
        related_agent=ch.related_agent,
        selected_option=req.selected_option,
    )
