"""CR109 slice 3 — the career-points ledger (implementation_plan.md §4.5).

Append-only, like `reputation_events`: `career_events` never gets a mutable
running-total column anywhere, on this table or on `users`. `SUM(delta)` for
a user IS the displayed number, with NO clamp on read anywhere in this
codebase — that is Amendment D's correction to the design's original plan
("clamp the display"), which gave a player whose signed total sat below zero
an invisible debt: they would earn points and the screen would not move
until they'd earned their way back through the hole.

**Clamp at write, not on read.** When posting a DEBIT (`delta_uncapped` is
negative), the stored `delta` is `max(delta_uncapped, -current_total)` — the
running sum can never go below zero. `delta_uncapped` keeps the RAW value
for the audit trail (a forfeit's "real" cost, even though the ledger only
ever collected part of it). A credit is never clamped; there is no ceiling.

Amendment F (mandatory): `post_career_event` REFUSES to build a row without
both `field_id` and `entry_id` — before it ever touches the session. The
column-level NOT NULL on `career_events` (see `models.py`) is the structural
backstop behind that refusal.

Idempotency is DEF039/DEF049-shaped: the (entry_id, reason) dedup check
below is a SELECT, not a lock, so two concurrent posts for the same pair can
both pass it — `CareerEventRow`'s `UniqueConstraint(entry_id, reason)` (and,
for the stipend, the partial `(user_id, period_key)` index) is the real
backstop. A caller does not need its own retry logic: losing that race
returns the row that already exists (or `None` for a lost stipend-period
claim) rather than raising.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.logging import logger
from app.db.models import CareerEventRow


def career_points_total(session, user_id: UUID) -> int:
    """`SUM(delta)` for a user — the ONE number ever displayed anywhere
    (Record header, share card, ...). Never clamped here; the clamp already
    happened, once, when each debit was WRITTEN."""
    total = session.execute(
        select(func.coalesce(func.sum(CareerEventRow.delta), 0)).where(
            CareerEventRow.user_id == user_id,
        )
    ).scalar_one()
    return int(total)


def post_career_event(
    session,
    *,
    user_id: UUID,
    delta_uncapped: int,
    reason: str,
    field_id: UUID,
    entry_id: UUID,
    period_key: str | None = None,
) -> CareerEventRow | None:
    """Post one ledger row against the caller's OWN session/transaction (the
    reputation_events `award()` pattern) so a clamp computed here and a
    sibling post for the same entry in the same call (e.g. `run_close` then
    `finish_stipend`) see each other's effect via `session.flush()`.

    Returns the written row; the PRE-EXISTING row on an (entry_id, reason)
    dedup hit (no-op, not an error — this is what makes re-running the
    scoring pass safe); or `None` only when a stipend's period claim lost to
    an earlier claim for the same (user_id, period_key) — i.e. "no stipend,
    someone/something already claimed this period."

    The insert itself runs inside a SAVEPOINT (`session.begin_nested()`), not
    the whole-session rollback `reputation_service.award()` uses on its own
    race — this function is called repeatedly against ONE shared session
    while a field's whole entrant list closes (implementation_plan.md's
    clamp-consistency requirement), and a bare `session.rollback()` on a
    losing race would undo every OTHER entrant's already-flushed events in
    that same call. A SAVEPOINT scopes the rollback to just this insert.
    """
    if field_id is None or entry_id is None:
        # Amendment F, structural: never even attempt to build a row that
        # would violate the NOT NULL columns — the column constraint is the
        # backstop, this is the first line of defence.
        raise ValueError(
            "post_career_event requires both field_id and entry_id "
            "(CR109 Amendment F) — a career_events row may never carry a "
            "null field_id or entry_id"
        )

    existing = session.execute(
        select(CareerEventRow).where(
            CareerEventRow.entry_id == entry_id, CareerEventRow.reason == reason,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    if reason == "finish_stipend" and period_key is not None:
        already_claimed = session.execute(
            select(CareerEventRow.id).where(
                CareerEventRow.user_id == user_id,
                CareerEventRow.reason == "finish_stipend",
                CareerEventRow.period_key == period_key,
            )
        ).first()
        if already_claimed is not None:
            return None

    delta = delta_uncapped
    if delta_uncapped < 0:
        current_total = career_points_total(session, user_id)
        delta = max(delta_uncapped, -current_total)

    row = CareerEventRow(
        user_id=user_id,
        delta=int(round(delta)),
        delta_uncapped=int(round(delta_uncapped)),
        reason=reason,
        field_id=field_id,
        entry_id=entry_id,
        period_key=period_key,
    )
    try:
        with session.begin_nested():
            session.add(row)
            session.flush()
    except IntegrityError:
        logger.info(
            "career_event_post_lost_race",
            user_id=str(user_id), entry_id=str(entry_id), reason=reason,
        )
        return session.execute(
            select(CareerEventRow).where(
                CareerEventRow.entry_id == entry_id, CareerEventRow.reason == reason,
            )
        ).scalar_one_or_none()

    logger.info(
        "career_event_posted",
        user_id=str(user_id), entry_id=str(entry_id), field_id=str(field_id),
        reason=reason, delta=row.delta, delta_uncapped=row.delta_uncapped,
    )
    return row


def forfeit_count(session, user_id: UUID) -> int:
    """Count of the user's forfeited entries — cheap enough to compute
    straight from `game_entries` rather than the ledger; kept here so
    `games_record_service.py` has one place to import Record-header stats
    from."""
    from app.db.models import GameEntryRow

    return int(
        session.execute(
            select(func.count()).select_from(GameEntryRow).where(
                GameEntryRow.user_id == user_id, GameEntryRow.state == "forfeit",
            )
        ).scalar_one()
    )
