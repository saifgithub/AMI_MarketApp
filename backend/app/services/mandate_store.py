"""User Mandate store — pre-auth, in-memory, keyed by device user_id.

The onboarding flow produces a Mandate at the end of the Concierge
conversation; today that mandate lives only inside the in-flight onboarding
session, then disappears. This store gives the rest of the app a way to
read and update a user's current mandate beyond onboarding (Settings →
My Mandate editor, mandate_edit journal entries, agent prompt composition
re-reads on each request).

W8 swap: replace dict with Postgres (`mandates` table per data_model.md)
and pull from Supabase Auth-provided user_id.
"""

from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Any
from uuid import UUID

from app.schemas import Compliance, Mandate
from app.services.coach_engine import hydrate_coach_mandate


class MandateStore:
    def __init__(self) -> None:
        self._mandates: dict[UUID, Mandate] = {}
        self._lock = RLock()

    def get(self, user_id: UUID) -> Mandate | None:
        with self._lock:
            return self._mandates.get(user_id)

    def get_or_default(self, user_id: UUID) -> Mandate:
        """Return the stored mandate or a hydrated default."""
        m = self.get(user_id)
        if m is not None:
            return m
        default = hydrate_coach_mandate({"user_id": str(user_id)})
        default = default.model_copy(update={"user_id": user_id})
        return default

    def upsert(self, user_id: UUID, mandate: Mandate) -> Mandate:
        with self._lock:
            now = datetime.now(timezone.utc)
            existing = self._mandates.get(user_id)
            new_version = (existing.version + 1) if existing else 1
            updated = mandate.model_copy(update={
                "user_id": user_id,
                "version": new_version,
                "updated_at": now,
                "created_at": existing.created_at if existing else now,
            })
            self._mandates[user_id] = updated
            return updated

    def patch(self, user_id: UUID, updates: dict[str, Any]) -> Mandate:
        """Shallow-merge updates into the current mandate, increment version.

        `compliance` is merged by key, then re-coerced into a Compliance
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
        with self._lock:
            self._mandates.clear()


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
        mandate = hydrate_coach_mandate(override)
    patch: dict[str, Any] = {}
    if user_id is not None:
        patch["user_id"] = user_id
    if locale is not None:
        patch["locale"] = locale
    if patch:
        mandate = mandate.model_copy(update=patch)
    return mandate
