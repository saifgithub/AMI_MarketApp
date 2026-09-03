"""CR219 R55 — admin-gated read of the verdict-outcome calibration ledger.

    GET /v1/admin/verdict-outcomes/aggregates

Internal only. There is deliberately no user-facing surface, no client route,
and no unauthenticated path: the ledger is a calibration *sanity floor*, not a
performance claim, and AMI Trade is a simulation-only education product with no
licence to present a track record. Saiful's 2026-09-02 ruling on the
internal-only half of R55 still binds — nothing here reaches a user before
v1.0, and if it ever does, the AI is named **AMI**.

Gating follows `/v1/admin/config-check` exactly: `Depends(get_admin)`, which is
CF Access JWT first, then the static `ADMIN_SECRET` bearer. 503 when neither is
configured, 403 when configured but nothing verifies.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.api.admin import get_admin
from app.services import verdict_outcomes

router = APIRouter(
    prefix="/v1/admin/verdict-outcomes",
    tags=["admin"],
    dependencies=[Depends(get_admin)],
)


@router.get("/aggregates")
def verdict_outcome_aggregates() -> dict[str, Any]:
    return verdict_outcomes.aggregates()
