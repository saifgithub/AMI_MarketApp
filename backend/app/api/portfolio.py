"""Portfolio analytics endpoints (CR026).

GET /v1/portfolio/sector-allocation/{user_id}
    The user's sector-allocation donut feed + mandate concentration-compliance.
    Authenticated, user's own (`_own` guard, mirroring `sim.py`). The ticker →
    sector resolution reads the pre-populated classification snapshot — NEVER a
    yfinance socket on this request path (the CR075/DEF089 rule); an unclassified
    holding lands in the "Other" bucket (disclosed, never a compliance breach).

GET /v1/portfolio/day-trader-outcomes/{user_id}
    CR131 — a measured before/after comparison of a user's own sim trading
    around when they switched on the Day Trader preset (CR129), beside the
    published Barber & Odean / Taiwan retail-trading baselines. See
    `app.services.day_trader_outcomes` for the honesty rules this enforces.

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
from app.services.day_trader_outcomes import compute_day_trader_outcomes
from app.services.health_gate import GateStatus, enforce_gate, evaluate_gate
from app.services.journal_store import get_journal_store
from app.services.llm_gateway import get_llm_gateway
from app.services.passive_twin import build_passive_twin
from app.services.portfolio_finding import generate_and_persist_finding
from app.services.portfolio_health import build_health_context
from app.services.portfolio_health_constants import STATUS_OK
from app.services.portfolio_rules import evaluate_rules_for_context
from app.services.rate_limit import portfolio_health_finding_rate_limit
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

# AT:R66 — CR136-M09 audit round 1, MAJOR M1. The third refusal code the Flutter
# Finding screen switches on. Named so the parity guard has a symbol to import
# rather than re-deriving a literal that lives in two places; its siblings
# already are (`health_gate.GATE_CLOSED_CODE` / `DAILY_CAP_CODE`).
HEALTH_UNAVAILABLE_CODE = "portfolio_health_unavailable"


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
    p, marks, snapshot_total_value, _drawdown_pct, _source = await asyncio.to_thread(
        sim.portfolio_marks_snapshot, user_id,
    )
    # DEF149: allocation is a fraction of the WHOLE portfolio, cash included, so the
    # donut and the cap agree with the breach copy's own words ("of your portfolio").
    #
    # DEF313 — this used to re-derive `invested + current_cash` under the name
    # `total_value`, which is a DIFFERENT number from the one the value card
    # shows: `Portfolio.total_value` carries the short leg and this did not, so
    # the two disagreed by exactly that leg whenever a short was open. One
    # derivation now. (Nothing renders this field today — `SectorAllocation
    # .totalValue` is parsed and unused — so the fix is to the contract before
    # something starts believing it.)
    #
    # Taken off the snapshot rather than recomputed: `portfolio_marks_snapshot`
    # already derived `p.total_value(marks)` inside the one `to_thread` hop this
    # route makes, and the route was discarding it as `_total_value`. Calling it
    # again out here also trips the DEF116/DEF120 guard — `Portfolio.total_value`
    # and `SimEngine.total_value` are the same name to a static reader, and the
    # engine's does fan out to the network. The guard is right to be name-based
    # and the answer is not to waive it, it is to stop making the second call.
    total_value = round(float(snapshot_total_value), 2)

    # DEF313 — the ring stays LONG-ONLY, deliberately and with a measurement
    # behind it: `sim_short_positions` has never held a row on Alpha, so making
    # the ring gross would have meant taking the safety floor's sector cap gross
    # too (or shipping a gross picture beside a long-only verdict) to fix a
    # display for a position type with zero instances. The decision and the
    # arithmetic that settles it are recorded on the DEF313 row; revisit when a
    # short actually exists.
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


# ── CR136 Portfolio Health ──────────────────────────────────────────────────


def _health_envelope(context: dict, gate: GateStatus) -> dict:
    """M07 wraps M04's context; it never edits or strips it. Stripping is the
    prompt-side context builder's job, and the tiles are entitled to the amber
    states — a `sufficient: false` block renders as the engine emitted it."""
    return {
        "status": context.get("status"),
        "as_of": context.get("as_of"),
        "generated_at": context.get("generated_at"),
        "engine_version": context.get("engine_version"),
        "metrics": context,
        "gate": gate.as_dict(),
    }


@router.get("/health/{user_id}")
async def portfolio_health(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    sim: SimEngine = Depends(get_sim_engine),
) -> dict:
    """Portfolio Health tiles. FREE in every gate mode.

    Calls `evaluate_gate` and never `enforce_gate` — the gate is reported so the
    card can render its CTA state, not applied. A mock-mode refusal or an
    all-insufficient book still returns 200: a 5xx would hide the amber state
    from the card, which is the CR040 question answered the wrong way.
    """
    _own(current_user, user_id)

    p = await asyncio.to_thread(sim.ensure_portfolio, user_id)
    context = await asyncio.to_thread(build_health_context, user_id)
    gate = await asyncio.to_thread(evaluate_gate, user_id, p.id)
    return _health_envelope(context, gate)


@router.post("/health/{user_id}/finding")
async def portfolio_health_finding(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    sim: SimEngine = Depends(get_sim_engine),
) -> dict:
    """Generate + persist a Portfolio Health Finding. Gated.

    Order is load-bearing, and two steps sit deliberately before the gate:
    ownership (403 before anything is spent) and the same-day idempotency
    return. Regenerating on the same day returns the existing entry
    unconditionally — no LLM call, no write, no budget, and NOT gated, because
    the entry is already in the user's journal and re-reading it must not cost
    anything or be refusable.
    """
    _own(current_user, user_id)
    portfolio_health_finding_rate_limit.check(f"user:{current_user.id}")

    p = await asyncio.to_thread(sim.ensure_portfolio, user_id)
    context = await asyncio.to_thread(build_health_context, user_id)
    if context.get("status") != STATUS_OK:
        # The engine refused (mock prices) or has nothing to measure. Saying so
        # is the whole point — a Finding narrated over mock-walk prices would
        # read exactly like a real one and mean nothing (CR040).
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "code": HEALTH_UNAVAILABLE_CODE,
                "reason": context.get("status"),
            },
        )

    store = get_journal_store()
    prior = await asyncio.to_thread(
        store.latest_portfolio_health_entry, user_id, p.id,
    )
    if (
        prior is not None
        and prior.deleted_at is None
        and (prior.payload or {}).get("as_of") == context["as_of"]
    ):
        gate = await asyncio.to_thread(evaluate_gate, user_id, p.id)
        return _finding_envelope(prior, created=False, gate=gate)

    gate = await asyncio.to_thread(evaluate_gate, user_id, p.id)
    enforce_gate(gate)

    mandate = await asyncio.to_thread(resolve_mandate, user_id, None)
    # CR222 §2 — `None` while the flag is off, which leaves the Finding exactly
    # as it was before this CR. Synchronous DB reads, so off the event loop.
    twin = await asyncio.to_thread(build_passive_twin, user_id, mandate=mandate)
    result = await generate_and_persist_finding(
        user_id=user_id,
        portfolio_id=p.id,
        as_of=context["as_of"],
        metric_blocks=list(context["blocks"].values()),
        store=store,
        evaluate=lambda prior_states: evaluate_rules_for_context(
            context, mandate, prior_states,
        ),
        gateway=get_llm_gateway(),
        passive_twin=twin,
    )

    # Re-evaluated so `daily_used` includes the row just written — a client that
    # renders the returned gate must not show the user a budget they no longer
    # have.
    gate = await asyncio.to_thread(evaluate_gate, user_id, p.id)
    return _finding_envelope(result.entry, created=result.created, gate=gate)


@router.get("/day-trader-outcomes/{user_id}")
async def day_trader_outcomes(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
) -> dict:
    """CR131 — a measured before/after comparison of a user's own sim
    trading around the moment they switched on the Day Trader preset (CR129),
    placed beside the published Barber & Odean / Taiwan retail-trading
    baselines. Read-only, ownership-guarded like every other endpoint on this
    router (`_own`).

    Three response shapes — see `compute_day_trader_outcomes`'s docstring:
    `not_in_cohort` (never applied the preset), `too_early` (applied it, but
    the sample either side of the switch is too thin to compare honestly —
    no numeric figure in that payload, by design), or `ready` (the full
    comparison). Never a judgement, grade, or warning — numbers and baseline
    provenance only.
    """
    _own(current_user, user_id)
    return await asyncio.to_thread(compute_day_trader_outcomes, user_id)


def _finding_envelope(entry, *, created: bool, gate: GateStatus) -> dict:
    payload = entry.payload or {}
    return {
        "journal_entry_id": str(entry.id),
        "created": created,
        "as_of": payload.get("as_of"),
        # STORED sections, always — mobile renders these and never regenerates
        # (README contract 5), so the idempotent replay and the fresh write
        # return the same shape from the same source.
        "sections": payload.get("sections") or {},
        "gate": gate.as_dict(),
    }
