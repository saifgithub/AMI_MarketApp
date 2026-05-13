"""Daily-challenge endpoints.

GET  /v1/daily_challenge/today         today's challenge (Asia/KL TZ)
GET  /v1/daily_challenge/by_date/YYYY-MM-DD  specific date
GET  /v1/daily_challenge/by_id/{id}    specific challenge by id
GET  /v1/daily_challenge/all           full list (admin / debugging)
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.daily_challenge import (
    DailyChallenge,
    DailyChallengeListResponse,
    DailyChallengeResponse,
)
from app.services.daily_challenge_service import (
    DailyChallengeService,
    get_daily_challenge_service,
)


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
