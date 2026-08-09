"""CR109 slice 3 — the Close, the Record and the PR board (read models).

implementation_plan.md §6 (API surface), §8.4 (the PR board — self-
competition, works at n=1), CR109.md §10.2 (the Close's three-beat budget)
and §10.4 (the private mirrors).

Three read-only surfaces, all self-scoped (a caller only ever sees their
OWN data — there is no cross-user query anywhere in this file):

  - `get_close_payload`  -> `GET /v1/games/runs/{run_id}/close`
  - `get_record`         -> `GET /v1/games/record`
  - `get_personal_records` -> `GET /v1/games/record/prs`

**The Close is complete without an entitlement.** implementation_plan.md
§6: a free user's response already carries rank, delta, curve, BOTH
counterfactual lines, markers and the re-entry CTA — there is no paid
feature built in this slice (the agent post-mortem is a later slice), so
there is nothing to strip and no entitlement check anywhere below.

**The public/private serializer fence** (CR109.md §10.4 / implementation_
plan.md §7.2: "assert it at the serializer, not the widget"). Intent,
wildness index and the two counterfactual lines are PRIVATE — they belong
on the Close and the Record (both self-facing) and nowhere else.
`_entry_public_fields` is what a FUTURE board/opponent-facing surface may
render (unused by any route today — slice 4 builds the board); it is
tested directly to guarantee it excludes every private-mirror key, so a
later board built on top of it cannot leak them by construction.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.db import get_session
from app.db.models import GameEntryRow, GameFieldRow
from app.services import career_ledger
from app.services import games_service as games
from app.services.portfolio_nav_daily import nav_history
from app.trading_math.returns import max_drawdown_pct

PRIVATE_MIRROR_KEYS = frozenset({
    "intent",
    "wildness_index",
    "counterfactual_hold_index_pct",
    "counterfactual_hold_first_picks_pct",
})


class RecordServiceError(Exception):
    """Base for this module's errors — `api/games.py` translates these."""


class RunNotFoundError(RecordServiceError):
    """No entry exists for this (user, run_id) pair."""


class RunNotClosedError(RecordServiceError):
    """The entry exists but hasn't reached `finished`/`void` yet (still
    live, or was forfeited — a forfeit has no Close)."""


def _entry_private_fields(entry: GameEntryRow) -> dict:
    """The private mirrors (design §10.4) — self-facing ONLY. Never fold
    this into a board or any opponent-facing payload."""
    return {
        "intent": entry.intent,
        "wildness_index": (
            float(entry.wildness_index) if entry.wildness_index is not None else None
        ),
        "counterfactual_hold_index_pct": (
            float(entry.counterfactual_hold_index_pct)
            if entry.counterfactual_hold_index_pct is not None else None
        ),
        "counterfactual_hold_first_picks_pct": (
            float(entry.counterfactual_hold_first_picks_pct)
            if entry.counterfactual_hold_first_picks_pct is not None else None
        ),
    }


def _entry_public_fields(entry: GameEntryRow, field: GameFieldRow) -> dict:
    """What a board/opponent-facing surface may show. Not called by any
    route in slice 3 (there is no board yet — slice 4) — kept here, tested
    directly, so the FUTURE board serializer has a safe base to build on
    rather than reinventing the exclusion list."""
    return {
        "entry_id": str(entry.id),
        "rank": entry.final_rank,  # always None through slice 4 — no placement
        "final_twr_pct": (
            float(entry.final_twr_pct) if entry.final_twr_pct is not None else None
        ),
        "alpha_display_pct": (
            float(entry.alpha_display_pct) if entry.alpha_display_pct is not None else None
        ),
        "scoring_basis": field.scoring_basis,
        "entrant_count": field.entrant_count,
    }


# ── The Close ──────────────────────────────────────────────────────────


def get_close_payload(user_id: UUID, run_id: UUID, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    with get_session() as s:
        row = s.execute(
            select(GameEntryRow, GameFieldRow)
            .join(GameFieldRow, GameEntryRow.field_id == GameFieldRow.id)
            .where(GameEntryRow.user_id == user_id, GameEntryRow.run_id == run_id)
        ).first()
        if row is None:
            raise RunNotFoundError(f"no run {run_id} for user {user_id}")
        entry, field = row
        if entry.state not in ("finished", "void"):
            raise RunNotClosedError(
                f"run {run_id} is {entry.state}, not closed"
            )
        private = _entry_private_fields(entry)
        payload_entry = {
            "run_id": str(run_id),
            "field_id": str(field.id),
            "cadence": field.cadence,
            "state": entry.state,
            "scoring_basis": field.scoring_basis,
            "entrant_count": field.entrant_count,
            "void_reason": entry.void_reason,
            "rank": entry.final_rank,
            "final_twr_pct": (
                float(entry.final_twr_pct) if entry.final_twr_pct is not None else None
            ),
            "alpha_scored_pct": (
                float(entry.alpha_scored_pct) if entry.alpha_scored_pct is not None else None
            ),
            "alpha_display_pct": (
                float(entry.alpha_display_pct) if entry.alpha_display_pct is not None else None
            ),
            "career_points_delta": entry.career_points_delta,
            "stipend_points": entry.stipend_points,
            "fees_paid": float(entry.fees_paid),
            "trade_count": entry.trade_count,
            **private,
        }
        cadence = field.cadence

    curve = [
        {
            "as_of_date": r.as_of_date.isoformat(),
            "nav": float(r.nav),
            "price_source": r.price_source,
        }
        for r in nav_history(user_id, run_id=run_id)
    ]

    beat_result = {
        "rank": payload_entry["rank"],
        "career_points_delta": payload_entry["career_points_delta"],
        "final_twr_pct": payload_entry["final_twr_pct"],
    }
    # Beat 2 — one insight. Slice 3 has no duel verdict, no paid post-mortem
    # and no board (so no near-miss line) — the counterfactual is the ONLY
    # candidate this slice ever has, per §10.2's own priority order.
    beat_insight = {
        "kind": "counterfactual",
        "hold_first_picks_pct": payload_entry["counterfactual_hold_first_picks_pct"],
        "hold_index_pct": payload_entry["counterfactual_hold_index_pct"],
        "beat_index_gross": (
            payload_entry["alpha_display_pct"] is not None
            and payload_entry["alpha_display_pct"] > 0
        ),
    }
    beat_reentry = _reentry_cta(user_id, cadence, now=now)

    return {
        **payload_entry,
        "curve": curve,
        "beats": {
            "result": beat_result,
            "insight": beat_insight,
            "re_entry": beat_reentry,
        },
        "debrief": {
            "intent": payload_entry["intent"],
            "wildness_index": payload_entry["wildness_index"],
            "counterfactual_hold_index_pct": payload_entry["counterfactual_hold_index_pct"],
            "counterfactual_hold_first_picks_pct": (
                payload_entry["counterfactual_hold_first_picks_pct"]
            ),
            "fees_paid": payload_entry["fees_paid"],
            "trade_count": payload_entry["trade_count"],
            "stipend_points": payload_entry["stipend_points"],
        },
    }


def _reentry_cta(user_id: UUID, cadence: str, *, now: datetime) -> dict | None:
    for c in games.list_cadences(user_id, now=now):
        if c["cadence"] == cadence:
            return {
                "cadence": c["cadence"],
                "field_id": c["field_id"],
                "state": c["state"],
                "queue_count": c["queue_count"],
                "deadline": c["deadline"],
                "already_held": c["already_held"],
            }
    return None


# ── The Record ─────────────────────────────────────────────────────────


def get_record(user_id: UUID) -> dict:
    with get_session() as s:
        net = career_ledger.career_points_total(s, user_id)
        forfeits = career_ledger.forfeit_count(s, user_id)
        rows = s.execute(
            select(GameEntryRow, GameFieldRow)
            .join(GameFieldRow, GameEntryRow.field_id == GameFieldRow.id)
            .where(GameEntryRow.user_id == user_id)
            .order_by(GameFieldRow.starts_on.desc())
        ).all()

    finished_count = sum(1 for e, _ in rows if e.state == "finished")
    void_count = sum(1 for e, _ in rows if e.state == "void")
    history = [
        {
            "run_id": str(e.run_id),
            "field_id": str(f.id),
            "cadence": f.cadence,
            "state": e.state,
            "final_twr_pct": float(e.final_twr_pct) if e.final_twr_pct is not None else None,
            "alpha_scored_pct": (
                float(e.alpha_scored_pct) if e.alpha_scored_pct is not None else None
            ),
            "career_points_delta": e.career_points_delta,
            "starts_on": f.starts_on.isoformat(),
            "ends_on": f.ends_on.isoformat(),
        }
        for e, f in rows
    ]

    return {
        "career_points_net": net,
        "forfeit_count": forfeits,
        "finished_count": finished_count,
        "void_count": void_count,
        "run_count": len(rows),
        "run_history": history,
    }


# ── The PR board (self-competition — works at n=1) ────────────────────


def get_personal_records(user_id: UUID) -> dict:
    with get_session() as s:
        rows = s.execute(
            select(GameEntryRow, GameFieldRow)
            .join(GameFieldRow, GameEntryRow.field_id == GameFieldRow.id)
            .where(GameEntryRow.user_id == user_id)
            .order_by(GameFieldRow.starts_on.asc())
        ).all()

    held_to_close = [(e, f) for e, f in rows if e.state in ("finished", "void")]
    finished = [(e, f) for e, f in rows if e.state == "finished"]

    best_twr = _best_by(held_to_close, key=lambda e: e.final_twr_pct, value_name="final_twr_pct")
    best_alpha = _best_by(
        finished, key=lambda e: e.alpha_scored_pct, value_name="alpha_scored_pct",
        extra=lambda e: {
            "alpha_display_pct": (
                float(e.alpha_display_pct) if e.alpha_display_pct is not None else None
            ),
        },
    )
    best_drawdown = _best_drawdown_control(held_to_close, user_id)
    longest_hold = _longest_hold(held_to_close)
    longest_streak = _longest_finish_streak(rows)

    return {
        "has_any_finished_runs": bool(finished),
        "best_weekly_twr": best_twr,
        "best_alpha": best_alpha,
        "best_drawdown_control": best_drawdown,
        "longest_hold_days": longest_hold,
        "longest_finish_streak": longest_streak,
    }


def _best_by(pairs, *, key, value_name: str, extra=None) -> dict | None:
    best_entry = None
    best_value = None
    for e, _f in pairs:
        v = key(e)
        if v is None:
            continue
        v = float(v)
        if best_value is None or v > best_value:
            best_value, best_entry = v, e
    if best_entry is None:
        return None
    out = {"entry_id": str(best_entry.id), value_name: best_value}
    if extra is not None:
        out.update(extra(best_entry))
    return out


def _best_drawdown_control(pairs, user_id: UUID) -> dict | None:
    best_entry = None
    best_dd = None
    for e, _f in pairs:
        values = [float(r.nav) for r in nav_history(user_id, run_id=e.run_id)]
        dd = max_drawdown_pct(values) if len(values) >= 2 else None
        if dd is None:
            continue
        if best_dd is None or dd < best_dd:
            best_dd, best_entry = dd, e
    if best_entry is None:
        return None
    return {"entry_id": str(best_entry.id), "max_drawdown_pct": best_dd}


def _longest_hold(pairs) -> dict | None:
    best_entry = None
    best_days = None
    for e, f in pairs:
        days = (f.ends_on - f.starts_on).days
        if best_days is None or days > best_days:
            best_days, best_entry = days, e
    if best_entry is None:
        return None
    return {"entry_id": str(best_entry.id), "days": best_days}


def _longest_finish_streak(rows) -> dict | None:
    """Consecutive 'finished' entries, ordered by field.starts_on — a
    forfeit OR a void breaks the streak (neither is a completed, scored
    finish, even though a void run did hold to close through no fault of
    the player's own)."""
    best_len = 0
    best_end_entry: GameEntryRow | None = None
    current_len = 0
    current_entry: GameEntryRow | None = None
    for e, _f in rows:
        if e.state == "finished":
            current_len += 1
            current_entry = e
        else:
            current_len = 0
            current_entry = None
        if current_len > best_len:
            best_len, best_end_entry = current_len, current_entry
    if best_end_entry is None:
        return None
    return {"count": best_len, "entry_id": str(best_end_entry.id)}
