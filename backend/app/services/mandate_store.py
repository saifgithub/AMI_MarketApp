"""User Mandate store — Postgres-backed, versioned.

The onboarding flow produces a Mandate at the end of the Concierge
conversation; this store persists it beyond onboarding so:

  - Settings → My Mandate can edit a single user's mandate across sessions
  - Every agent (1-on-1, Coach, Room, Sim) reads the same mandate via
    `resolve_mandate()`
  - Mandate edits are versioned — old rows are kept for journal replay

Each edit writes a new `mandates` row with the same `user_id` and an
incremented `version`. `is_current=True` is moved to the new row; old rows
keep history. Reads always go through `is_current=True`.

The public sync API matches the previous in-memory store byte-for-byte so
existing callers and tests don't change.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, update

from app.db import get_session, init_schema
from app.db.models import MandateRow
from app.schemas import Compliance, Mandate
from app.services.brief_engine import hydrate_brief_mandate


class MandateStore:
    """Thin facade over the `mandates` table. Sync API; opens its own session."""

    def __init__(self) -> None:
        init_schema()

    def get(self, user_id: UUID) -> Mandate | None:
        with get_session() as s:
            row = s.execute(
                select(MandateRow).where(
                    MandateRow.user_id == user_id,
                    MandateRow.is_current.is_(True),
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            return Mandate.model_validate(row.snapshot)

    def get_or_default(self, user_id: UUID) -> Mandate:
        m = self.get(user_id)
        if m is not None:
            return m
        default = hydrate_brief_mandate({"user_id": str(user_id)})
        return default.model_copy(update={"user_id": user_id})

    def upsert(self, user_id: UUID, mandate: Mandate) -> Mandate:
        with get_session() as s:
            existing = s.execute(
                select(MandateRow).where(
                    MandateRow.user_id == user_id,
                    MandateRow.is_current.is_(True),
                )
            ).scalar_one_or_none()
            now = datetime.now(timezone.utc)
            new_version = (existing.version + 1) if existing else 1
            created_at = existing.created_at if existing else now
            updated = mandate.model_copy(update={
                "user_id": user_id,
                "version": new_version,
                "updated_at": now,
                "created_at": created_at,
            })
            # Demote prior current row(s), then insert the new one.
            s.execute(
                update(MandateRow)
                .where(MandateRow.user_id == user_id, MandateRow.is_current.is_(True))
                .values(is_current=False)
            )
            s.add(MandateRow(
                user_id=user_id,
                version=new_version,
                is_current=True,
                snapshot=updated.model_dump(mode="json"),
                created_at=created_at,
                updated_at=now,
            ))
            return updated

    def patch(self, user_id: UUID, updates: dict[str, Any]) -> Mandate:
        """Shallow-merge updates into the current mandate, bump version.

        `compliance` is merged by key and re-coerced into a Compliance
        instance so downstream code (.compliance.halal etc) keeps working.
        """
        current = self.get_or_default(user_id)
        if "compliance" in updates and isinstance(updates["compliance"], dict):
            current_compl = current.compliance.model_dump()
            current_compl.update(updates["compliance"])
            updates = {**updates, "compliance": Compliance(**current_compl)}
        new = current.model_copy(update=updates)
        return self.upsert(user_id, new)

    def clear(self) -> None:
        with get_session() as s:
            s.query(MandateRow).delete()


_store: MandateStore | None = None


def get_mandate_store() -> MandateStore:
    global _store
    if _store is None:
        _store = MandateStore()
    return _store


def resolve_mandate(
    user_id: UUID | None,
    override: dict[str, Any] | None,
    *,
    locale: str | None = None,
) -> Mandate:
    """Single resolver used by all session endpoints (1-on-1, Coach, Room, Sim).

    Resolution order:
      1. Stored mandate for `user_id` (from MandateStore — set via Settings).
      2. Hydrated mandate from `override` (typical demo / test path).
      3. Hydrated defaults.

    Any caller-provided locale wins over what's stored.
    """
    store = get_mandate_store()
    mandate: Mandate
    if user_id is not None and (existing := store.get(user_id)) is not None:
        mandate = existing
    else:
        mandate = hydrate_brief_mandate(override)
    patch: dict[str, Any] = {}
    if user_id is not None:
        patch["user_id"] = user_id
    if locale is not None:
        patch["locale"] = locale
    if patch:
        mandate = mandate.model_copy(update=patch)
    return mandate
