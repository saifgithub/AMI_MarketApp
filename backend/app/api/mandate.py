"""Mandate read + patch endpoints.

GET   /v1/mandate/{user_id}        Read current mandate (returns a default if none stored).
PATCH /v1/mandate/{user_id}        Shallow-merge updates. compliance.* fields merge by key.
                                    Bumps version, emits a mandate_edit journal entry.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends

from app.schemas import Compliance, Mandate
from app.schemas.journal import EntryType, JournalEntryCreate
from app.services.journal_store import get_journal_store
from app.services.mandate_store import MandateStore, get_mandate_store


router = APIRouter(prefix="/v1/mandate", tags=["mandate"])


@router.get("/{user_id}", response_model=Mandate)
async def get_mandate(
    user_id: UUID,
    store: MandateStore = Depends(get_mandate_store),
) -> Mandate:
    return store.get_or_default(user_id)


@router.patch("/{user_id}", response_model=Mandate)
async def patch_mandate(
    user_id: UUID,
    updates: dict[str, Any],
    store: MandateStore = Depends(get_mandate_store),
) -> Mandate:
    before = store.get_or_default(user_id)
    updated = store.patch(user_id, updates)

    # Journal — record what changed, in plain English
    try:
        diffs: list[str] = []
        if updates.get("max_drawdown_pct") and updates["max_drawdown_pct"] != before.max_drawdown_pct:
            diffs.append(f"max drawdown {before.max_drawdown_pct}% → {updates['max_drawdown_pct']}%")
        if updates.get("risk_score") and updates["risk_score"] != before.risk_score:
            diffs.append(f"risk score {before.risk_score} → {updates['risk_score']}")
        if "compliance" in updates and isinstance(updates["compliance"], dict):
            before_c = before.compliance.model_dump()
            for k, v in updates["compliance"].items():
                if before_c.get(k) != v:
                    diffs.append(f"compliance.{k}: {before_c.get(k)} → {v}")
        summary = "; ".join(diffs) if diffs else "Mandate updated."
        get_journal_store().append(JournalEntryCreate(
            user_id=user_id,
            entry_type=EntryType.MANDATE_EDIT,
            reference_id=None,
            title=f"Mandate edited → v{updated.version}",
            summary=summary,
            tags=["mandate"],
            payload={
                "before": before.model_dump(mode="json"),
                "after": updated.model_dump(mode="json"),
            },
        ))
    except Exception:  # pragma: no cover
        pass

    return updated
