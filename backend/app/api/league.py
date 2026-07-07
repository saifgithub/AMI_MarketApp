"""Weekly league endpoints (CR004, D-060).

GET   /v1/league/standings   my cohort's board this week (404 if unassigned)
GET   /v1/league/me          handle, tier, reputation, week points, rank, streak
GET   /v1/league/history     my past weeks (tier, final rank, outcome)
PATCH /v1/league/handle      regenerate the pseudonymous handle (once, ever)

Reputation-based only — no P&L appears anywhere in this surface (D-060,
store declaration). Handles keep the leaderboard pseudonymous; real names
render only for members who opted in via `users.show_display_name`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.dependencies import get_current_user
from app.db import get_session
from app.db.models import User
from app.services.league_service import (
    HandleAlreadyRegenerated,
    get_league_service,
)
from app.services.reputation_service import get_reputation_service


router = APIRouter(prefix="/v1/league", tags=["league"])


def _attached_user(session, user_id) -> User:
    user = session.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()
    if user is None:  # pragma: no cover — bearer already validated
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    return user


@router.get("/standings")
async def standings(current_user: User = Depends(get_current_user)) -> dict:
    svc = get_league_service()
    with get_session() as s:
        board = svc.standings(s, current_user.id)
    if board is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_in_league")
    return board


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)) -> dict:
    league = get_league_service()
    rep = get_reputation_service()
    with get_session() as s:
        user = _attached_user(s, current_user.id)
        handle = league.ensure_handle(s, user)
        member = league.membership(s, user.id)
        rank = None
        tier = league._current_tier(s, user.id)
        points_this_week = 0
        if member is not None:
            points_this_week = member.points
            board = league.standings(s, user.id)
            if board is not None:
                tier = board["tier"]
                rank = next(
                    (m["rank"] for m in board["members"] if m["is_me"]), None,
                )
        streak = rep.streak(s, user.id)
        return {
            "handle": handle,
            "tier": tier,
            "reputation": user.reputation,
            "points_this_week": points_this_week,
            "rank": rank,
            "show_display_name": user.show_display_name,
            "streak": {
                "current": streak.current,
                "longest": streak.longest,
                "next_milestone": streak.next_milestone,
            },
        }


@router.get("/history")
async def history(current_user: User = Depends(get_current_user)) -> list[dict]:
    with get_session() as s:
        return get_league_service().history(s, current_user.id)


@router.patch("/handle")
async def regenerate_handle(
    current_user: User = Depends(get_current_user),
) -> dict:
    svc = get_league_service()
    with get_session() as s:
        user = _attached_user(s, current_user.id)
        try:
            handle = svc.regenerate_handle(s, user)
        except HandleAlreadyRegenerated:
            raise HTTPException(status.HTTP_409_CONFLICT, "already_regenerated")
    return {"handle": handle}
