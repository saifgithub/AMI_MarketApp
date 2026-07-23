"""Mandate read + patch endpoints.

GET   /v1/mandate/{user_id}                       Read current mandate (returns a default if none stored).
PATCH /v1/mandate/{user_id}                       Shallow-merge updates. compliance.* fields merge by key.
                                                   Bumps version, emits a mandate_edit journal entry.
GET   /v1/mandate/{user_id}/audit                 BL12: audit current holdings against the current mandate.
GET   /v1/mandate/{user_id}/versions              BL5: list every persisted mandate version, newest first.
GET   /v1/mandate/{user_id}/versions/{v}          BL5: fetch a specific historical version's snapshot.
POST  /v1/mandate/{user_id}/rollback/{v}          BL5: create a new version mirroring version v.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ValidationError

from app.agents.safety_floor import (
    HoldingsAuditResult,
    check_holdings_against_mandate,
)
from app.api.dependencies import get_current_user
from app.db.models import User
from app.schemas import Compliance, Mandate
from app.services.credit_service import balance_for, room_cost_for_plan
from app.services.entitlements import effective_plan_for_user
from app.schemas.journal import EntryType, JournalEntryCreate
from app.services.journal_store import get_journal_store
from app.services.mandate_store import MandateStore, get_mandate_store
from app.services.sharia_universe import default_halal_universe
from app.services.sim_engine import (
    SimEngine,
    get_sim_engine,
)


router = APIRouter(
    prefix="/v1/mandate",
    tags=["mandate"],
    dependencies=[Depends(get_current_user)],
)


def _own(current_user: User, user_id: UUID) -> None:
    if current_user.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")


def _with_plan_state(mandate: Mandate, user: User) -> Mandate:
    """Stamp live plan + credit state onto a mandate response (CR039).

    `Mandate.plan` / `trial_expires_at` / `credit_balance` are schema fields
    with no columns behind them — they live on `users`. Nothing populated them,
    so every client saw `floor_pass` with 0 credits no matter what it had. The
    Room meter makes that gap visible (the UI can't render a wall it can't
    see), so the read path resolves them here.

    `balance_for` re-grants a due allowance as a side effect, which is what
    makes an expired trial's drop appear on the next mandate read rather than
    at month rollover.
    """
    plan = effective_plan_for_user(user.id)
    balance, allowance, resets_at = balance_for(user.id)
    return mandate.model_copy(update={
        "plan": plan,
        "trial_expires_at": user.trial_expires_at,
        "credit_balance": balance,
        "credit_allowance": allowance,
        "credits_reset_at": resets_at,
        "room_cost": room_cost_for_plan(plan),
        "room_cooldown_until": user.room_cooldown_until,
    })


@router.get("/{user_id}", response_model=Mandate)
async def get_mandate(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    store: MandateStore = Depends(get_mandate_store),
) -> Mandate:
    _own(current_user, user_id)
    return _with_plan_state(store.get_or_default(user_id), current_user)


@router.patch("/{user_id}", response_model=Mandate)
async def patch_mandate(
    user_id: UUID,
    updates: dict[str, Any],
    current_user: User = Depends(get_current_user),
    store: MandateStore = Depends(get_mandate_store),
) -> Mandate:
    _own(current_user, user_id)
    before = store.get_or_default(user_id)
    try:
        updated = store.patch(user_id, updates)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

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

    return _with_plan_state(updated, current_user)


class MandateVersionSummary(BaseModel):
    """BL5 (AT:R33): one row in the mandate history list."""

    version: int
    is_current: bool
    created_at: datetime
    change_summary: str | None = None  # from the matching mandate_edit journal entry


class MandateVersionsResponse(BaseModel):
    versions: list[MandateVersionSummary]


@router.get("/{user_id}/versions", response_model=MandateVersionsResponse)
async def list_mandate_versions(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    store: MandateStore = Depends(get_mandate_store),
) -> MandateVersionsResponse:
    """BL5: list every persisted mandate version for this user, newest first.

    Decorates each version with the matching `mandate_edit` journal entry's
    summary so the history UI can render plain-English change descriptions
    inline. Versions without a journal entry (e.g. very early rows pre-AT:R20)
    show null change_summary.
    """
    _own(current_user, user_id)
    versions = store.list_versions(user_id)
    # Pull all mandate_edit journal entries in one shot, then index by
    # the version number embedded in their title ("Mandate edited → vN").
    journal_entries, _, _ = get_journal_store().list_for_user(
        user_id, entry_type=EntryType.MANDATE_EDIT, limit=200,
    )
    summary_by_version: dict[int, str] = {}
    for e in journal_entries:
        title = e.title or ""
        # title format: "Mandate edited → vN"
        if "→ v" in title:
            try:
                v = int(title.split("→ v", 1)[1].strip())
                summary_by_version[v] = e.summary or ""
            except ValueError:
                continue
    return MandateVersionsResponse(versions=[
        MandateVersionSummary(
            version=v["version"],
            is_current=v["is_current"],
            created_at=v["created_at"],
            change_summary=summary_by_version.get(v["version"]),
        )
        for v in versions
    ])


@router.get("/{user_id}/versions/{version}", response_model=Mandate)
async def get_mandate_version(
    user_id: UUID,
    version: int,
    current_user: User = Depends(get_current_user),
    store: MandateStore = Depends(get_mandate_store),
) -> Mandate:
    """BL5: fetch a specific historical mandate version's full snapshot."""
    _own(current_user, user_id)
    m = store.get_version(user_id, version)
    if m is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"mandate version {version} not found for this user",
        )
    return m


@router.post("/{user_id}/rollback/{version}", response_model=Mandate)
async def rollback_mandate(
    user_id: UUID,
    version: int,
    current_user: User = Depends(get_current_user),
    store: MandateStore = Depends(get_mandate_store),
) -> Mandate:
    """BL5: rollback to a previous mandate version.

    Forward-only: creates a NEW current version whose snapshot mirrors the
    target. Old versions stay intact. Writes a mandate_edit journal entry
    tagged with `rollback` so the history view shows it clearly.
    """
    _own(current_user, user_id)
    before = store.get_or_default(user_id)
    new_current = store.rollback_to(user_id, version)
    if new_current is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"mandate version {version} not found for this user",
        )
    try:
        get_journal_store().append(JournalEntryCreate(
            user_id=user_id,
            entry_type=EntryType.MANDATE_EDIT,
            reference_id=None,
            title=f"Mandate edited → v{new_current.version}",
            summary=f"Rolled back to v{version}.",
            tags=["mandate", "rollback"],
            payload={
                "before": before.model_dump(mode="json"),
                "after": new_current.model_dump(mode="json"),
                "rolled_back_to_version": version,
            },
        ))
    except Exception:  # pragma: no cover
        pass
    return new_current


@router.get("/{user_id}/audit", response_model=HoldingsAuditResult)
async def audit_holdings(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    store: MandateStore = Depends(get_mandate_store),
    sim: SimEngine = Depends(get_sim_engine),
) -> HoldingsAuditResult:
    """BL12: audit the user's current sim holdings against the current mandate.

    Designed to be called by mobile immediately after a successful PATCH so the
    "your portfolio may now violate the new mandate" resolve modal can render
    with per-holding violations + Liquidate/Postpone/Override options.

    Pure read — no journal writes, no DB mutations. The resolve actions
    themselves are BL6.
    """
    _own(current_user, user_id)
    mandate = store.get_or_default(user_id)
    portfolio = sim.ensure_portfolio(user_id)
    tickers = [h.ticker for h in portfolio.holdings]
    marks = sim.current_marks(tickers)
    portfolio_value = sim.total_value(user_id)
    drawdown_pct = sim.current_drawdown_pct(user_id)
    return check_holdings_against_mandate(
        holdings=portfolio.holdings,
        marks=marks,
        portfolio_value=portfolio_value,
        current_drawdown_pct=drawdown_pct,
        mandate=mandate,
        halal_universe=default_halal_universe(),
    )
