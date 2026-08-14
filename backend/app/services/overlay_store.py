"""User-overlay store — Postgres-backed.

Coach Your Agent produces a `UserOverlay` per (user, agent) pair, versioned.
The store is the source of truth `build_agent_prompt` reads to compose the
runtime prompt — see `agent_prompts.append_user_overlay`.

Tier-based retention is enforced on save: when over the cap, the oldest
non-active version is dropped (active is whatever the user last accepted;
rollback resets active to an older version).

A separate `overlay_edit_counts` table tracks lifetime accepted edits. The
two-table split lets retention drop old version rows while the lifetime
count keeps gating Floor-Pass tier writes.

The public sync API matches the previous in-memory store so callers + tests
don't change.
"""

from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from app.core.logging import logger
from app.db import get_session, init_schema
from app.db.models import OverlayEditCounter, UserOverlayRow
from app.schemas import AgentId, Plan
from app.schemas.coach import UserOverlay
from uuid import UUID


RETENTION_BY_PLAN: dict[Plan, int | None] = {
    Plan.FLOOR_PASS: 5,
    Plan.TRADER: 20,
    Plan.TRIAL_TRADER: 20,
    Plan.FLOOR_MANAGER: None,
}

LIFETIME_EDIT_CAP_BY_PLAN: dict[Plan, int | None] = {
    Plan.FLOOR_PASS: 3,
    Plan.TRADER: None,
    Plan.TRIAL_TRADER: None,
    Plan.FLOOR_MANAGER: None,
}


class OverlayVersionConflictError(RuntimeError):
    """An overlay write lost two consecutive version races and was NOT persisted.

    DEF220, and the same reasoning as `MandateVersionConflictError`: the overlay
    is text the user wrote, so "your edit did not land" must be distinguishable
    from any other database error rather than surfacing as a generic 500 that
    reads, one layer up, like nothing happened.
    """


def _agent_str(agent_id: AgentId) -> str:
    return agent_id.value if hasattr(agent_id, "value") else str(agent_id)


def _row_to_overlay(row: UserOverlayRow) -> UserOverlay:
    return UserOverlay(
        id=row.id,
        user_id=row.user_id,
        agent_id=AgentId(row.agent_id),
        version=row.version,
        content=row.content,
        plain_english=row.plain_english,
        based_on_session=row.based_on_session,
        created_at=row.created_at,
    )


class OverlayStore:
    def __init__(self) -> None:
        init_schema()

    def get_active(self, user_id: UUID, agent_id: AgentId) -> UserOverlay | None:
        aid = _agent_str(agent_id)
        with get_session() as s:
            row = s.execute(
                select(UserOverlayRow).where(
                    UserOverlayRow.user_id == user_id,
                    UserOverlayRow.agent_id == aid,
                    UserOverlayRow.is_active.is_(True),
                )
            ).scalar_one_or_none()
            if row is not None:
                return _row_to_overlay(row)
            # Active flag could be off everything (shouldn't happen) — fall
            # back to the latest version so reads stay deterministic.
            row = s.execute(
                select(UserOverlayRow).where(
                    UserOverlayRow.user_id == user_id,
                    UserOverlayRow.agent_id == aid,
                ).order_by(UserOverlayRow.version.desc()).limit(1)
            ).scalar_one_or_none()
            return _row_to_overlay(row) if row else None

    def list_versions(self, user_id: UUID, agent_id: AgentId) -> list[UserOverlay]:
        aid = _agent_str(agent_id)
        with get_session() as s:
            rows = s.execute(
                select(UserOverlayRow).where(
                    UserOverlayRow.user_id == user_id,
                    UserOverlayRow.agent_id == aid,
                ).order_by(UserOverlayRow.version.asc())
            ).scalars().all()
            return [_row_to_overlay(r) for r in rows]

    def active_version(self, user_id: UUID, agent_id: AgentId) -> int:
        v = self.get_active(user_id, agent_id)
        return v.version if v is not None else 0

    def edit_count(self, user_id: UUID, agent_id: AgentId) -> int:
        aid = _agent_str(agent_id)
        with get_session() as s:
            row = s.execute(
                select(OverlayEditCounter).where(
                    OverlayEditCounter.user_id == user_id,
                    OverlayEditCounter.agent_id == aid,
                )
            ).scalar_one_or_none()
            return row.count if row else 0

    def can_edit(self, user_id: UUID, agent_id: AgentId, plan: Plan) -> bool:
        cap = LIFETIME_EDIT_CAP_BY_PLAN.get(plan)
        if cap is None:
            return True
        return self.edit_count(user_id, agent_id) < cap

    def edits_remaining(self, user_id: UUID, agent_id: AgentId, plan: Plan) -> int | None:
        cap = LIFETIME_EDIT_CAP_BY_PLAN.get(plan)
        if cap is None:
            return None
        return max(0, cap - self.edit_count(user_id, agent_id))

    def save_new_version(
        self,
        user_id: UUID,
        agent_id: AgentId,
        content: str,
        plain_english: str,
        plan: Plan,
        based_on_session: UUID | None = None,
    ) -> UserOverlay:
        aid = _agent_str(agent_id)
        with get_session() as s:
            # Demote prior active, insert the new one as active. The version probe that
            # used to sit above this line is gone: the retry loop below recomputes it per
            # attempt, and leaving a second copy here would be one derivation reading
            # stale while the other retried (DEF098's shape, in miniature).
            s.execute(
                update(UserOverlayRow)
                .where(
                    UserOverlayRow.user_id == user_id,
                    UserOverlayRow.agent_id == aid,
                    UserOverlayRow.is_active.is_(True),
                ).values(is_active=False)
            )
            # DEF220, insert 1 of 2 — chosen outcome: RETRY ONCE, then RAISE.
            # Same reasoning as `mandate_store.upsert`: an overlay is text the
            # user wrote, `UNIQUE(user_id, agent_id, version)` collides when two
            # saves read the same `current_max`, and skipping would drop an edit
            # the user believes they made. The version is a sequence, so landing
            # at N+2 is what a millisecond's difference would have produced.
            #
            # This insert was invisible to the P15 guard until DEF220 widened it:
            # the rule only saw `s.add(Model(...))` constructed inline, and this
            # one binds to `new_row` first. Its sibling counter below WAS seen —
            # two inserts, one function, one hazard, and the guard could see one
            # of them.
            for attempt in (1, 2):
                current_max = s.execute(
                    select(UserOverlayRow.version).where(
                        UserOverlayRow.user_id == user_id,
                        UserOverlayRow.agent_id == aid,
                    ).order_by(UserOverlayRow.version.desc()).limit(1)
                ).scalar()
                next_version = (current_max + 1) if current_max else 1
                new_row = UserOverlayRow(
                    user_id=user_id,
                    agent_id=aid,
                    version=next_version,
                    content=content,
                    plain_english=plain_english,
                    based_on_session=based_on_session,
                    is_active=True,
                )
                try:
                    with s.begin_nested():
                        s.add(new_row)
                        s.flush()
                except IntegrityError:
                    logger.warning(
                        "overlay_version_lost_race",
                        user_id=str(user_id), agent_id=aid,
                        attempted_version=next_version, attempt=attempt,
                    )
                    continue
                break
            else:
                raise OverlayVersionConflictError(
                    f"overlay for user {user_id} / agent {aid} lost two "
                    "consecutive version races; the write was NOT persisted"
                )

            # Bump lifetime counter.
            # DEF220, insert 2 of 2 — chosen outcome: FOLD INTO AN UPDATE.
            # This counter feeds `can_edit`, i.e. the Floor Pass lifetime edit
            # cap, so a dropped increment hands the user a free edit and a
            # double-count silently charges them one they did not spend. Neither
            # is acceptable, and both are avoidable: on collision the row now
            # exists, so re-read it and apply the same `+1` the else-branch does.
            counter = s.execute(
                select(OverlayEditCounter).where(
                    OverlayEditCounter.user_id == user_id,
                    OverlayEditCounter.agent_id == aid,
                )
            ).scalar_one_or_none()
            if counter is None:
                try:
                    with s.begin_nested():
                        s.add(OverlayEditCounter(
                            user_id=user_id, agent_id=aid, count=1,
                        ))
                        s.flush()
                except IntegrityError:
                    counter = s.execute(
                        select(OverlayEditCounter).where(
                            OverlayEditCounter.user_id == user_id,
                            OverlayEditCounter.agent_id == aid,
                        )
                    ).scalar_one_or_none()
                    logger.info(
                        "overlay_edit_counter_lost_race",
                        user_id=str(user_id), agent_id=aid,
                        recovered=counter is not None,
                    )
                    if counter is not None:
                        counter.count = counter.count + 1
            else:
                counter.count = counter.count + 1

            # Flush so the new row participates in retention counting below.
            s.flush()
            self._enforce_retention(s, user_id, aid, plan, next_version)

            return _row_to_overlay(new_row)

    def rollback_to(self, user_id: UUID, agent_id: AgentId, version: int) -> UserOverlay:
        aid = _agent_str(agent_id)
        with get_session() as s:
            target = s.execute(
                select(UserOverlayRow).where(
                    UserOverlayRow.user_id == user_id,
                    UserOverlayRow.agent_id == aid,
                    UserOverlayRow.version == version,
                )
            ).scalar_one_or_none()
            if target is None:
                raise ValueError(f"version {version} not found for {agent_id}")
            s.execute(
                update(UserOverlayRow)
                .where(
                    UserOverlayRow.user_id == user_id,
                    UserOverlayRow.agent_id == aid,
                ).values(is_active=False)
            )
            target.is_active = True
            return _row_to_overlay(target)

    def _enforce_retention(
        self, s, user_id: UUID, aid: str, plan: Plan, active_version: int,
    ) -> None:
        cap = RETENTION_BY_PLAN.get(plan)
        if cap is None:
            return
        rows = s.execute(
            select(UserOverlayRow).where(
                UserOverlayRow.user_id == user_id,
                UserOverlayRow.agent_id == aid,
            ).order_by(UserOverlayRow.version.asc())
        ).scalars().all()
        if len(rows) <= cap:
            return
        # Drop oldest non-active versions to fit under the cap.
        drop_count = len(rows) - cap
        droppable = [r for r in rows if r.version != active_version]
        for r in droppable[:drop_count]:
            s.delete(r)

    def clear(self) -> None:
        with get_session() as s:
            s.execute(delete(UserOverlayRow))
            s.execute(delete(OverlayEditCounter))


_store: OverlayStore | None = None


def get_overlay_store() -> OverlayStore:
    global _store
    if _store is None:
        _store = OverlayStore()
    return _store
