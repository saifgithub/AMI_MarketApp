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
from app.schemas import Mandate
from app.schemas.mandate import CLIENT_UNWRITABLE_MANDATE_FIELDS
from app.services.brief_engine import hydrate_brief_mandate


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge `updates` into `base`. A nested dict field (e.g. a
    BaseModel field's own keys, like `risk_components` or `compliance`) merges
    key-by-key instead of being replaced wholesale — the CR101-BE1 fix: PATCHing
    ONE nested key (`{"risk_components": {"concentration_tolerance": 4}}`) used
    to drop that object's required siblings entirely, and DEF062's re-validation
    then 422'd on the resulting incomplete object. Lists and scalars still
    replace wholesale (unchanged); only dict-vs-dict recurses."""
    merged = dict(base)
    for key, value in updates.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(existing, value)
        else:
            merged[key] = value
    return merged


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
        """Recursively merge updates into the current mandate, bump version
        (CR101-BE1). A nested BaseModel field (`risk_components`, `compliance`,
        ...) merges key-by-key — see `_deep_merge` — so PATCHing one nested key
        no longer drops its required siblings.

        DEF062: `model_copy(update=...)` explicitly skips validation, so an
        out-of-range `max_drawdown_pct` / `risk_score` (or any wrong-typed
        field) would otherwise persist untouched and `max_drawdown_pct`
        specifically feeds a raw numeric comparison inside the safety
        floor's deterministic compliance check. Re-validate the merged
        result through the full `Mandate` schema before persisting —
        `Mandate.model_validate` raises `ValidationError` on anything the
        schema wouldn't have accepted on write.

        DEF179: entitlement fields (`plan`, `credit_balance`, ...) are silently
        dropped from `updates` before the merge — they are `Mandate` fields
        with no columns behind them (CR039, `_with_plan_state`), and letting
        a PATCH set them was a paywall bypass. Every field the schema still
        validates types for; only these five never reach the merge.
        """
        updates = {
            k: v for k, v in updates.items()
            if k not in CLIENT_UNWRITABLE_MANDATE_FIELDS
        }
        current = self.get_or_default(user_id)
        merged_dict = _deep_merge(current.model_dump(mode="json"), updates)
        new = Mandate.model_validate(merged_dict)
        return self.upsert(user_id, new)

    def list_versions(self, user_id: UUID) -> list[dict]:
        """BL5 (AT:R33): all mandate rows for a user, newest first.

        Returns plain dicts with version + is_current + created_at — the
        route layer decorates each with the corresponding `mandate_edit`
        journal entry's change summary.
        """
        with get_session() as s:
            rows = s.execute(
                select(MandateRow)
                .where(MandateRow.user_id == user_id)
                .order_by(MandateRow.version.desc())
            ).scalars().all()
            return [
                {
                    "version": r.version,
                    "is_current": bool(r.is_current),
                    "created_at": r.created_at,
                }
                for r in rows
            ]

    def get_version(self, user_id: UUID, version: int) -> Mandate | None:
        """BL5: fetch a specific historical mandate version. Returns None
        if the (user_id, version) tuple doesn't exist."""
        with get_session() as s:
            row = s.execute(
                select(MandateRow).where(
                    MandateRow.user_id == user_id,
                    MandateRow.version == version,
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            return Mandate.model_validate(row.snapshot)

    def rollback_to(self, user_id: UUID, version: int) -> Mandate | None:
        """BL5: rollback to a previous version. Creates a NEW mandate row
        (with bumped version) whose snapshot mirrors the target version.

        Old versions stay intact — rollback is forward-only history.
        Returns None if the target version doesn't exist; otherwise the
        new current Mandate.
        """
        target = self.get_version(user_id, version)
        if target is None:
            return None
        return self.upsert(user_id, target)

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

    DEF179: `override` is the client-supplied `mandate_override` body on
    `/v1/brief/start` and `/v1/agents/one_on_one/start` (a paywall bypass
    vector reachable with no PATCH at all) — entitlement fields are stripped
    from it before hydrating, same fields `MandateStore.patch()` drops.
    `hydrate_brief_mandate` itself stays a trusted constructor for its other
    (test/internal) callers.
    """
    store = get_mandate_store()
    mandate: Mandate
    if user_id is not None and (existing := store.get(user_id)) is not None:
        mandate = existing
    else:
        safe_override = (
            {k: v for k, v in override.items() if k not in CLIENT_UNWRITABLE_MANDATE_FIELDS}
            if override else override
        )
        mandate = hydrate_brief_mandate(safe_override)
    patch: dict[str, Any] = {}
    if user_id is not None:
        patch["user_id"] = user_id
    if locale is not None:
        patch["locale"] = locale
    if patch:
        mandate = mandate.model_copy(update=patch)
    return mandate
