"""Portfolio analytics endpoints (CR026).

GET /v1/portfolio/sector-allocation/{user_id}
    The user's sector-allocation donut feed + mandate concentration-compliance.
    Authenticated, user's own (`_own` guard, mirroring `sim.py`). The ticker →
    sector resolution reads the pre-populated classification snapshot — NEVER a
    yfinance socket on this request path (the CR075/DEF089 rule); an unclassified
    holding lands in the "Other" bucket (disclosed, never a compliance breach).

The path carries `{user_id}` (like `sim.py`'s `/v1/sim/portfolio/{user_id}`) so the
`_own` guard can 403 another user's request — the documented base path
`/v1/portfolio/sector-allocation` with the owned id appended.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.db.models import User
from app.services.sector_allocation import (
    NON_SECTOR_BUCKETS,
    SectorMap,
    allocate_by_sector,
    default_sector_map,
    sector_concentration_cap,
)
from app.services.mandate_store import resolve_mandate
from app.services.sim_engine import SimEngine, get_sim_engine

router = APIRouter(prefix="/v1/portfolio", tags=["portfolio"])


def _own(current_user: User, user_id: UUID) -> None:
    if current_user.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")


def get_sector_map() -> SectorMap:
    """FastAPI dependency — the snapshot-backed ticker → sector resolver. Overridable
    in tests (a local read of the stored map; never a socket on the request path)."""
    return default_sector_map()


@router.get("/sector-allocation/{user_id}")
async def sector_allocation(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    sim: SimEngine = Depends(get_sim_engine),
    sector_map: SectorMap = Depends(get_sector_map),
) -> dict:
    """Sector allocation + concentration-compliance for the user's sim portfolio.

    Returns `{allocation: {sector: weight}, total_value, compliance:
    {max_sector, max_sector_name, max_allowed, compliant}}`. `allocation` weights are
    normalised over invested market value (`total_value`). `max_allowed` is read from
    the user's mandate `concentration_tolerance` (default 0.40), never hard-coded.
    Compliance is judged over KNOWN sectors only — the "Other" (unclassified) bucket
    is disclosed but never counts as a breach (the DEF059 inversion guard)."""
    _own(current_user, user_id)

    # DEF120 D1: single to_thread hop around a one-fetch snapshot (the
    # total_value/drawdown_pct fields it also returns go unused here, but
    # the fetch itself is the same one this route already needed).
    p, marks, _total_value, _drawdown_pct, _source = await asyncio.to_thread(
        sim.portfolio_marks_snapshot, user_id,
    )
    invested = sum(marks.get(h.ticker, 0.0) * h.quantity for h in p.holdings)
    # DEF149: allocation is a fraction of the WHOLE portfolio, cash included, so the
    # donut and the cap agree with the breach copy's own words ("of your portfolio").
    total_value = round(invested + p.current_cash, 2)

    allocation = allocate_by_sector(
        p.holdings, marks, cash=p.current_cash, sector_of=sector_map.sector,
    )

    mandate = resolve_mandate(user_id, None)
    cap = sector_concentration_cap(mandate)

    known = {s: w for s, w in allocation.items() if s not in NON_SECTOR_BUCKETS}
    if known:
        max_name, max_weight = max(known.items(), key=lambda kv: kv[1])
    else:
        max_name, max_weight = None, 0.0
    compliant = max_weight <= cap + 1e-9

    return {
        "allocation": {s: round(w, 4) for s, w in allocation.items()},
        "total_value": total_value,
        "compliance": {
            "max_sector": round(max_weight, 4),
            "max_sector_name": max_name,
            "max_allowed": cap,
            "compliant": compliant,
        },
    }
