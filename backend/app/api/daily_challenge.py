"""Daily-challenge endpoints.

GET  /v1/daily_challenge/today              today's challenge (Asia/KL TZ)
GET  /v1/daily_challenge/by_date/YYYY-MM-DD specific date
GET  /v1/daily_challenge/by_id/{id}         specific challenge by id
GET  /v1/daily_challenge/all                full list (admin / debugging)
POST /v1/daily_challenge/{cid}/attempt      record an attempt + journal it (BL10)
PUT  /v1/daily_challenge/reminder           set the daily-reminder hour + timezone (CR095)
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import get_current_user, get_current_user_optional
from app.db import get_session
from app.db.models import DailyChallengeAttemptRow, User
from app.schemas.daily_challenge import (
    DailyChallenge,
    DailyChallengeListResponse,
    DailyChallengePublic,
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
def today(
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
                    correct_option=ch.answer,
                    explanation=ch.explanation,
                    attempted_at=row.created_at.isoformat(),
                )
    return DailyChallengeResponse(
        challenge=DailyChallengePublic.from_challenge(ch),
        date=d.isoformat(),
        my_attempt=my_attempt,
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
    return DailyChallengeResponse(
        challenge=DailyChallengePublic.from_challenge(ch), date=d.isoformat(),
    )


@router.get("/by_id/{challenge_id}", response_model=DailyChallengePublic)
async def by_id(
    challenge_id: str,
    svc: DailyChallengeService = Depends(get_daily_challenge_service),
) -> DailyChallengePublic:
    ch = svc.get_by_id(challenge_id)
    if ch is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"daily challenge {challenge_id} not found",
        )
    return DailyChallengePublic.from_challenge(ch)


@router.get("/all", response_model=DailyChallengeListResponse)
async def all_challenges(
    svc: DailyChallengeService = Depends(get_daily_challenge_service),
) -> DailyChallengeListResponse:
    items = svc.all_challenges()
    return DailyChallengeListResponse(
        items=[DailyChallengePublic.from_challenge(ch) for ch in items],
        total=len(items),
    )


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
def attempt(
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
        try:
            s.flush()
        except IntegrityError:
            # Concurrent double-submit lost the UNIQUE(user, challenge) race —
            # return the winner's stored result rather than a 500 (F4).
            s.rollback()
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
            raise
        # CR096: one award per attempt, spec's 3-outcome table (right +5 /
        # close +2 / wrong-but-tried +1). Every shipped challenge type is
        # strict single-correct multiple-choice with no graded partial-credit
        # answer space, so "close" isn't reachable from today's content —
        # it's wired into POINTS for a challenge type that defines it later.
        rep = get_reputation_service()
        rep.award(
            s, user_id=current_user.id,
            event_type="challenge_correct" if correct else "challenge_wrong_tried",
            ref_id=cid,
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


class ReminderPreference(BaseModel):
    """`null` turns reminders off — the column's own "off" value, so there is no
    separate enabled flag to drift out of sync with the hour."""

    daily_reminder_hour: int | None = Field(
        default=None,
        ge=0,
        le=23,
        description=(
            "Hour in the user's own timezone (users.timezone). Explicit null = "
            "reminders off. Omit to leave unchanged."
        ),
    )
    timezone: str | None = Field(
        default=None,
        description="IANA name, e.g. Asia/Riyadh. Omit to leave unchanged.",
    )


@router.put("/reminder", response_model=ReminderPreference)
def set_reminder_preference(
    req: ReminderPreference,
    current_user: User = Depends(get_current_user),
) -> ReminderPreference:
    """CR095 — the write path for the daily-reminder time.

    Without this the reminder job is unreachable: `daily_reminder_hour` is NULL
    for every user, NULL means off, and nothing else in the API writes it — so
    the tick would run forever and correctly send nothing. The CR's acceptance
    says "at their configured local time", and there was no way to configure it.

    Timezone is settable here rather than in a separate call because the hour is
    meaningless without it, and a user who sets one and not the other gets a
    reminder at the wrong time — an error they cannot see or diagnose. Validated
    against `zoneinfo` so an unknown name is rejected at the boundary instead of
    surfacing later inside the tick.

    Scoped to the caller's own row (`get_current_user`); there is no user_id in
    the path, so there is nothing to authorize across users.
    """
    if req.timezone is not None:
        try:
            ZoneInfo(req.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"unknown timezone {req.timezone!r}",
            ) from exc

    with get_session() as s:
        row = s.get(User, current_user.id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
        # CR095 audit MAJOR: assign ONLY when the caller actually sent the
        # field. A plain `Optional[int] = None` cannot distinguish "omitted"
        # from "explicitly null", and `null` is a meaningful value here (it
        # is the column's own "off"), so an unconditional assign turned a
        # timezone-only PUT — the single most plausible real call, from a
        # user who travels or relocates — into a silent 200 OK that cleared
        # their reminder hour. `model_fields_set` carries exactly the
        # distinction Pydantic drops on the value itself.
        if "daily_reminder_hour" in req.model_fields_set:
            row.daily_reminder_hour = req.daily_reminder_hour
        if req.timezone is not None:
            row.timezone = req.timezone
        s.commit()
        return ReminderPreference(
            daily_reminder_hour=row.daily_reminder_hour,
            timezone=row.timezone,
        )
