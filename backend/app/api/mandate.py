"""Mandate read + patch endpoints.

GET   /v1/mandate/{user_id}        Read current mandate (returns a default if none stored).
PATCH /v1/mandate/{user_id}        Shallow-merge updates. compliance.* fields merge by key.
                                    Bumps version, emits a mandate_edit journal entry.
GET   /v1/mandate/{user_id}/audit  BL12: audit current holdings against the current mandate.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.agents.safety_floor import (
    HoldingsAuditResult,
    check_holdings_against_mandate,
)
from app.api.dependencies import get_current_user
from app.db.models import User
from app.schemas import Compliance, Mandate
from app.schemas.journal import EntryType, JournalEntryCreate
from app.services.journal_store import get_journal_store
from app.services.mandate_store import MandateStore, get_mandate_store
from app.services.sim_engine import (
    DEFAULT_HALAL_UNIVERSE,
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


@router.get("/{user_id}", response_model=Mandate)
async def get_mandate(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    store: MandateStore = Depends(get_mandate_store),
) -> Mandate:
    _own(current_user, user_id)
    return store.get_or_default(user_id)


@router.patch("/{user_id}", response_model=Mandate)
async def patch_mandate(
    user_id: UUID,
    updates: dict[str, Any],
    current_user: User = Depends(get_current_user),
    store: MandateStore = Depends(get_mandate_store),
) -> Mandate:
    _own(current_user, user_id)
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
        halal_universe=DEFAULT_HALAL_UNIVERSE,
    )
