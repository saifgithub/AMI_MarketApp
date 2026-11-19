"""Beta Room thumbs (CR278 / CR267 WP-36): store, change and summarise them.

A Room has at most one rating (`room_ratings.room_run_id` is UNIQUE) and only
that Room's owner may set or change it; both rules live here so the user route
and any future caller share them. The admin read feeds the WP-53 exit report.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.logging import logger
from app.db import get_session
from app.db.models import RoomRatingRow, RoomRunRow, _utcnow


class RoomNotFound(LookupError):
    """No such Room."""


class NotRoomOwner(PermissionError):
    """The caller does not own the Room."""


class RoomNotRateable(ValueError):
    """The Room has no verdict yet (still running, or it failed)."""


@dataclass(frozen=True)
class StoredRating:
    run_id: UUID
    helpful: bool
    created_at: datetime
    updated_at: datetime
    changed: bool  # True when this call replaced an earlier, different answer


def _existing(s, run_id: UUID) -> RoomRatingRow | None:
    return s.execute(
        select(RoomRatingRow).where(RoomRatingRow.room_run_id == run_id)
    ).scalar_one_or_none()


def set_rating(*, run_id: UUID, user_id: UUID, helpful: bool) -> StoredRating:
    with get_session() as s:
        run = s.get(RoomRunRow, run_id)
        if run is None:
            raise RoomNotFound(str(run_id))
        if run.user_id != user_id:
            raise NotRoomOwner(str(run_id))
        if not run.verdict:
            raise RoomNotRateable(str(run_id))
        row = _existing(s, run_id)
        now = _utcnow()
        changed = False
        inserted = False
        if row is None:
            # SAVEPOINT so a lost race on UNIQUE(room_run_id) (a double tap, two
            # devices) rolls back only this insert; the loser then updates the
            # row the winner wrote. P15 (failure_patterns.md).
            try:
                with s.begin_nested():
                    row = RoomRatingRow(
                        room_run_id=run_id, helpful=helpful,
                        created_at=now, updated_at=now,
                    )
                    s.add(row)
                    s.flush()
                inserted = True
            except IntegrityError:
                row = _existing(s, run_id)
                if row is None:
                    raise
                logger.info("room_rating_insert_lost_race", run_id=str(run_id))
        if not inserted:
            changed = row.helpful != helpful
            if changed:
                row.helpful = helpful
                row.updated_at = now
        s.flush()
        return StoredRating(
            run_id=run_id, helpful=row.helpful, created_at=row.created_at,
            updated_at=row.updated_at, changed=changed,
        )


def summary(*, limit: int = 100, since: datetime | None = None) -> dict:
    """Totals plus the newest `limit` ratings (with the Room they were for)."""
    with get_session() as s:
        stmt = (
            select(RoomRatingRow, RoomRunRow)
            .join(RoomRunRow, RoomRunRow.id == RoomRatingRow.room_run_id)
            .order_by(RoomRatingRow.updated_at.desc())
        )
        if since is not None:
            stmt = stmt.where(RoomRatingRow.updated_at >= since)
        pairs = s.execute(stmt).all()
        total = len(pairs)
        up = sum(1 for r, _ in pairs if r.helpful)
        recent = [
            {
                "run_id": str(r.room_run_id),
                "ticker": run.ticker,
                "verdict_action": (run.verdict or {}).get("action"),
                "helpful": r.helpful,
                "rated_at": r.created_at,
                "updated_at": r.updated_at,
            }
            for r, run in pairs[:limit]
        ]
    return {
        "totals": {
            "ratings": total,
            "helpful": up,
            "not_helpful": total - up,
            "helpful_pct": round(100.0 * up / total, 1) if total else None,
        },
        "recent": recent,
    }
