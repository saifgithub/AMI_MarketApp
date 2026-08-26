"""The signed-in user's own identity — the handle, and nothing else yet.

`PATCH /v1/me/handle` regenerates the pseudonymous handle, once ever.

**Why this module exists (CR109 slice 7).** This route lived at
`PATCH /v1/league/handle`, and slice 7 deletes `/v1/league/*` along with the
reputation league Amendment A retired. Deleting it with them would have been
wrong: the handle is not a league artifact. It is the player's public name, and
`games_board.py` renders `User.handle` on the NEW game's leaderboard and sorts
the field by it — so removing the only way to change it would have taken a live
capability out of the feature CR109 was built to ship, silently, on the strength
of the prefix it happened to sit under.

The league name on the old path was always incidental to what this does. Here it
sits under the user, which is what it was always about.
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

router = APIRouter(prefix="/v1/me", tags=["me"])

# Amendment M's lesson, applied to this move rather than re-learned. The backend
# goes out by rsync today; the Flutter half calling `/v1/me/handle` goes out
# through store review days later. Every INSTALLED build in between still calls
# `PATCH /v1/league/handle`, and while its READS are covered (`_nullOn404` makes
# a removed league read as "nothing to show"), the regenerate button is not: a
# 404 lands in its generic catch and tells the user "couldn't change your
# handle". So the old path stays as an alias for exactly one release.
#
# DELETE THIS ALIAS once a store build carrying `/v1/me/handle` is live on both
# platforms — the same condition slice 7 itself waited on, and now readable off
# `client_release_floors` rather than guessed: raise the floor past that build
# and no client can be calling the old path any more.
legacy_handle_router = APIRouter(
    prefix="/v1/league", tags=["me"], include_in_schema=False,
)


@router.get("")
def me(current_user: User = Depends(get_current_user)) -> dict:
    """The signed-in user's own handle.

    Added by the same slice that deleted `GET /v1/league/me`. That route
    returned handle + tier + reputation + week points + rank + streak; every
    field but the first belonged to the retired league. Settings still has to
    render the name it lets you change, and no other surviving route returns
    your own handle — the game board returns the FIELD's handles, which is a
    different question and needs a seat in a run to answer. So the one field
    that outlived the league comes back on the user's own route.
    """
    with get_session() as s:
        user = s.execute(
            select(User).where(User.id == current_user.id)
        ).scalar_one_or_none()
        if user is None:  # pragma: no cover — bearer already validated
            raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
        return {"handle": user.handle}


@router.patch("/handle")
def regenerate_handle(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Regenerate the handle. 409 `already_regenerated` on the second attempt —
    once ever, which is `users.handle_regenerated_at` and predates this move."""
    svc = get_league_service()
    with get_session() as s:
        user = s.execute(
            select(User).where(User.id == current_user.id)
        ).scalar_one_or_none()
        if user is None:  # pragma: no cover — bearer already validated
            raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
        try:
            handle = svc.regenerate_handle(s, user)
        except HandleAlreadyRegenerated:
            raise HTTPException(status.HTTP_409_CONFLICT, "already_regenerated")
    return {"handle": handle}


@legacy_handle_router.patch("/handle")
def regenerate_handle_legacy(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Deprecated alias of `PATCH /v1/me/handle` — see the note above."""
    return regenerate_handle(current_user=current_user)

