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

from app.api.dependencies import get_current_user
from app.db.models import User
from app.schemas.daily_challenge import (
    DailyChallenge,
    DailyChallengeListResponse,
    DailyChallengeResponse,
)
from app.schemas.journal import EntryType, JournalEntryCreate, Outcome
from app.services.daily_challenge_service import (
    DailyChallengeService,
    get_daily_challenge_service,
)
from app.services.journal_store import get_journal_store


router = APIRouter(prefix="/v1/daily_challenge", tags=["daily_challenge"])


@router.get("/today", response_model=DailyChallengeResponse)
async def today(
    svc: DailyChallengeService = Depends(get_daily_challenge_service),
) -> DailyChallengeResponse:
    ch, d = svc.today()
    if ch is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"no daily challenge for {d.isoformat()}",
        )
    return DailyChallengeResponse(challenge=ch, date=d.isoformat())


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


@router.post("/{cid}/attempt", response_model=DailyChallengeAttemptResponse)
async def attempt(
    cid: str,
    req: DailyChallengeAttemptRequest,
    current_user: User = Depends(get_current_user),
    svc: DailyChallengeService = Depends(get_daily_challenge_service),
) -> DailyChallengeAttemptResponse:
    """BL10: record a daily-challenge attempt and journal it. Returns the
    correct option + explanation + related-lesson/agent links so the mobile
    detail screen can render the result inline.
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
    )
