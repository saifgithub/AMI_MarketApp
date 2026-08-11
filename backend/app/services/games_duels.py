"""Duels — one-versus-one inside a field. CR109 slice 3b, design §11.1.

Saiful, after the playability review: *"I really like the Dual….. how can we
bring it back?"*

**Why this exists, in one paragraph.** §6.6 says the open board needs `n >= 8`
before placement means anything, and §16.4 concedes that at alpha every field
is below that — so the flagship competitive surface is inert exactly when the
product most needs a player to feel something. A duel needs `n = 2`. It is
the only competitive format that works at alpha field sizes, and it produces
better ceremony than a thin board can: *"You vs VECTOR_11. 3 days left.
They're 1.1% ahead"* beats *"1st of 3, scored against the S&P"* by a wide
margin.

**The three rules that are not negotiable**, each carved out of a formula
that would otherwise swallow it:

1. **A duel never routes through the placement formula (§6.2).** At `n = 2`,
   placement `p` is exactly 1.0 or 0.0 — placement would pay the winner the
   maximum in the game and debit the loser the maximum, for beating one
   person. Nor does it route to §6.6's benchmark path: there `n = 2` is a
   SHORTFALL, here it is the intended field size.
2. **The delta is symmetric.** See `games_scoring.DUEL_POINTS` for why that
   is load-bearing rather than tidy. **One honest caveat, recorded rather
   than discovered:** Amendment D clamps career-point DEBITS at write so a
   player's running total can never go below zero. A loser already sitting
   at zero therefore pays nothing while the winner still collects, so the
   pair is not zero-sum at the floor, and a player at zero is strictly +EV
   in duels. That is accepted, not overlooked: the clamp exists to prevent
   invisible debt (a player earning points while the screen does not move),
   which is a worse problem; and the farm the symmetry argument defends
   against is *already* closed structurally by auto-matching, since you
   cannot choose to duel your own alt. `delta_uncapped` on the ledger row
   keeps the symmetric number for the audit trail either way.
3. **Auto-matched only.** Onboarding is anonymous-first, so a second account
   is nearly free; direct challenge-by-handle plus cheap accounts is a
   trivial farm — make an alt, throw the duel, bank the win, repeat.
   Removing the ability to CHOOSE your opponent closes that structurally
   rather than by detection. There is no challenge entry point in this
   module, and adding one later must come with its own answer (no points, or
   a per-period cap).

**Pairing runs in the lock window**, in the same sweep that fills the house
desks — after entries close, so the field is final and nobody can enter a
duel and then walk away from it; and before the market opens, so both books
start from the same bar. Pairing earlier would mean pairing against a field
that is still changing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import or_, select

from app.core.logging import logger
from app.db import get_session
from app.db.models import GameDuelRow, GameEntryRow, GameFieldRow, User
from app.services.games_scoring import duel_points

# The desk a first-ever run is always paired against. §11.1: *"Your first
# run: you versus the market. Five trading days. Beat the Index Desk."* It is
# the most legible fantasy in investing, it needs no tutorial, and — unlike a
# concentrated moonshot on the open board — it cannot embarrass a beginner,
# because it holds the benchmark.
FIRST_RUN_DESK_KEY = "index"


class DuelPairingError(Exception):
    """Raised only for a caller mistake (a field that does not exist). A
    field with nobody to pair is not an error — it returns zero pairings."""


# ── Reading ─────────────────────────────────────────────────────────────


def duel_for_run(session, run_id: UUID) -> GameDuelRow | None:
    """The duel this run is in, either side of it, or None."""
    return session.execute(
        select(GameDuelRow).where(
            or_(GameDuelRow.run_a_id == run_id, GameDuelRow.run_b_id == run_id)
        )
    ).scalars().first()


def opponent_of(duel: GameDuelRow, user_id: UUID) -> tuple[UUID, UUID]:
    """(opponent_user_id, opponent_run_id) from the perspective of `user_id`."""
    if duel.user_a_id == user_id:
        return duel.user_b_id, duel.run_b_id
    return duel.user_a_id, duel.run_a_id


def _has_finished_before(session, user_id: UUID, *, excluding_run: UUID) -> bool:
    """Has this user ever finished a run other than this one?

    "First run" is defined by FINISHED runs, not by entries. A player who
    entered last week and forfeited has still never had a Close, and the
    first-Close narrative (§11.1) is the whole point of the first-run duel —
    so they get one. Defining it by entry count would spend the guaranteed
    opponent on a run nobody saw the end of.
    """
    row = session.execute(
        select(GameEntryRow.id).where(
            GameEntryRow.user_id == user_id,
            GameEntryRow.state == "finished",
            GameEntryRow.run_id != excluding_run,
        ).limit(1)
    ).scalar_one_or_none()
    return row is not None


def _already_paired_run_ids(session, field_id: UUID) -> set[UUID]:
    rows = session.execute(
        select(GameDuelRow.run_a_id, GameDuelRow.run_b_id).where(
            GameDuelRow.field_id == field_id
        )
    ).all()
    return {r for pair in rows for r in pair}


def _has_live_duel_in_cadence(session, user_id: UUID, cadence: str) -> bool:
    """One live duel per cadence — for attention, not integrity (§12.2 case 1
    settles the integrity question: a symmetric delta is unfarmable). Two
    live weekly duels would mean two opponents to track in a surface built
    to name one."""
    row = session.execute(
        select(GameDuelRow.id).where(
            GameDuelRow.cadence == cadence,
            GameDuelRow.state == "live",
            or_(GameDuelRow.user_a_id == user_id, GameDuelRow.user_b_id == user_id),
        ).limit(1)
    ).scalar_one_or_none()
    return row is not None


# ── Pairing ─────────────────────────────────────────────────────────────


def pair_field(field_id: UUID, *, now: datetime | None = None) -> dict:
    """Pair every unpaired entrant in a locked field. Idempotent.

    Order matters and is deliberate: **first-run players are paired against
    the Index Desk BEFORE humans are matched against each other.** §11.1 (Q8)
    settles this — the first run is a duel *instead of* an open-field result,
    and it is the only book a new player holds. Matching a beginner into a
    human duel first would spend their guaranteed, bounded-difficulty
    opponent on whoever happened to be waiting.

    Leftovers are fine. An odd human out simply has no duel this period and
    is scored on the open field as usual — a duel is an addition to the run,
    never a replacement for it (except in the first-run narrative, which is a
    Close-surface routing rule rather than a scoring one).
    """
    now = now or datetime.now(timezone.utc)
    made_first_run = 0
    made_auto = 0

    with get_session() as s:
        field = s.execute(
            select(GameFieldRow).where(GameFieldRow.id == field_id)
        ).scalar_one_or_none()
        if field is None:
            raise DuelPairingError(f"no field {field_id}")
        cadence = field.cadence

        entries = s.execute(
            select(GameEntryRow, User)
            .join(User, GameEntryRow.user_id == User.id)
            .where(
                GameEntryRow.field_id == field_id,
                GameEntryRow.state.in_(("entered", "active")),
            )
            .order_by(GameEntryRow.entered_at.asc())
        ).all()

        paired = _already_paired_run_ids(s, field_id)
        desk_entry = next(
            (
                (e, u) for e, u in entries
                if u.is_desk and u.desk_key == FIRST_RUN_DESK_KEY
            ),
            None,
        )
        humans = [
            (e, u) for e, u in entries
            if not u.is_desk and e.run_id not in paired
        ]

        # ── Pass 1 — first-ever runs, against the Index Desk.
        #
        # The desk appears on the B side of MANY duels in one field: it is
        # one opponent held by every beginner at once, which is exactly what
        # "a guaranteed opponent at n=1 real players" means. That is why side
        # B's unique index is scoped to `auto` duels — see the model's
        # `__table_args__`. Side A is always the human.
        first_run_ids: set[UUID] = set()
        if desk_entry is not None:
            for entry, _user in humans:
                if _has_finished_before(s, entry.user_id, excluding_run=entry.run_id):
                    continue
                if _has_live_duel_in_cadence(s, entry.user_id, cadence):
                    continue
                first_run_ids.add(entry.run_id)

        # ── Pass 2 — everyone else, oldest entry first (the same FIFO rule
        # the queue drain uses, and for the same reason: it is the only order
        # a player can reason about, and it does not reward re-entering).
        waiting = [
            (e, u) for e, u in humans
            if e.run_id not in first_run_ids
            and not _has_live_duel_in_cadence(s, e.user_id, cadence)
        ]

        for entry, _user in humans:
            if entry.run_id not in first_run_ids:
                continue
            s.add(GameDuelRow(
                id=uuid4(), field_id=field_id, cadence=cadence, kind="first_run",
                user_a_id=entry.user_id, run_a_id=entry.run_id,
                user_b_id=desk_entry[0].user_id, run_b_id=desk_entry[0].run_id,
                state="live", created_at=now,
            ))
            made_first_run += 1

        for i in range(0, len(waiting) - 1, 2):
            a, _ = waiting[i]
            b, _ = waiting[i + 1]
            s.add(GameDuelRow(
                id=uuid4(), field_id=field_id, cadence=cadence, kind="auto",
                user_a_id=a.user_id, run_a_id=a.run_id,
                user_b_id=b.user_id, run_b_id=b.run_id,
                state="live", created_at=now,
            ))
            made_auto += 1

    if made_first_run or made_auto:
        logger.info(
            "duels_paired", field_id=str(field_id), cadence=cadence,
            first_run=made_first_run, auto=made_auto,
        )
    return {
        "field_id": str(field_id),
        "cadence": cadence,
        "first_run": made_first_run,
        "auto": made_auto,
        "unpaired": max(0, len(waiting) % 2),
    }


def run_duel_pairing_tick(*, now: datetime | None = None) -> dict:
    """Background entry point — runs in the same lock window the desk fill
    uses, and AFTER it, so a first-run player has an Index Desk to be paired
    against.

    Idempotent by the same mechanism `fill_field_with_desks` uses: already-
    paired runs are excluded by query, so a restart mid-sweep resumes rather
    than double-pairing, and the two unique constraints make a genuine race
    fail loudly at the DB rather than silently produce two duels for one run.
    """
    from app.services.games_desks import fields_in_lock_window

    now = now or datetime.now(timezone.utc)
    fields = fields_in_lock_window(now)
    first_run = 0
    auto = 0
    for field_id in fields:
        try:
            stats = pair_field(field_id, now=now)
        except Exception:
            logger.exception("duel_pairing_failed", field_id=str(field_id))
            continue
        first_run += stats["first_run"]
        auto += stats["auto"]
    return {"fields": len(fields), "first_run": first_run, "auto": auto}


# ── Settlement ──────────────────────────────────────────────────────────


def settle_duel(
    session,
    duel: GameDuelRow,
    *,
    twr_a_pct: float | None,
    twr_b_pct: float | None,
    a_is_void: bool = False,
    b_is_void: bool = False,
    now: datetime | None = None,
) -> int:
    """Decide one duel and post the symmetric delta. Returns the delta
    applied to side A (negated for B; 0 on a tie or a void).

    **Void beats everything.** If either side's run was voided — the scoring
    pass voids a run whose NAV series was built on fabricated marks — the
    duel is void too, at zero. A contest decided by comparing a real return
    against a mock-walk one is not a result, and paying it out would be the
    DEF059 shape on a number the player will remember.

    **A tie is a real outcome, not a failure.** Both TWRs equal to four
    decimal places settles at zero with no winner, and `state` stays
    `settled` — a player who drew deserves to be told they drew.

    Idempotent: a duel already out of `live` is returned untouched, so
    re-running the scoring pass cannot double-post.
    """
    from app.services import career_ledger

    now = now or datetime.now(timezone.utc)
    if duel.state != "live":
        return 0

    duel.settled_at = now
    duel.twr_a_pct = twr_a_pct
    duel.twr_b_pct = twr_b_pct

    if a_is_void or b_is_void or twr_a_pct is None or twr_b_pct is None:
        duel.state = "void"
        duel.winner_user_id = None
        duel.points_delta = 0
        session.add(duel)
        logger.info(
            "duel_void", duel_id=str(duel.id),
            a_void=a_is_void, b_void=b_is_void,
            a_measured=twr_a_pct is not None, b_measured=twr_b_pct is not None,
        )
        return 0

    duel.state = "settled"
    # Four decimals — the precision `game_duels.twr_*_pct` stores. Comparing
    # at full float precision would make a genuine dead heat essentially
    # impossible and decide it on noise the player cannot see.
    a = round(float(twr_a_pct), 4)
    b = round(float(twr_b_pct), 4)
    if a == b:
        duel.winner_user_id = None
        duel.points_delta = 0
        session.add(duel)
        logger.info("duel_tie", duel_id=str(duel.id), twr_pct=a)
        return 0

    delta = duel_points(duel.cadence)
    a_won = a > b
    duel.winner_user_id = duel.user_a_id if a_won else duel.user_b_id
    duel.points_delta = delta
    session.add(duel)

    # Posted against the caller's session so a duel delta and the same
    # entry's close/stipend posts see each other's clamp — the reason
    # `post_career_event` takes a session at all.
    for user_id, entry_id, won in (
        (duel.user_a_id, duel.run_a_id, a_won),
        (duel.user_b_id, duel.run_b_id, not a_won),
    ):
        entry = session.execute(
            select(GameEntryRow).where(GameEntryRow.run_id == entry_id)
        ).scalars().first()
        if entry is None:
            continue
        career_ledger.post_career_event(
            session,
            user_id=user_id,
            delta_uncapped=delta if won else -delta,
            # The reason string is the dedup key alongside entry_id, so it
            # must be stable across re-runs and distinct from `run_close`.
            reason="duel_result",
            field_id=duel.field_id,
            entry_id=entry.id,
        )

    logger.info(
        "duel_settled", duel_id=str(duel.id), cadence=duel.cadence,
        winner=str(duel.winner_user_id), delta=delta, twr_a=a, twr_b=b,
    )
    return delta if a_won else -delta


def duel_record(session, user_id: UUID) -> dict:
    """W–L–D across settled duels — the Record surface's duel line (§11.1).

    Void duels are counted separately and never as a loss. A run voided for
    fabricated marks is not something the player did.
    """
    rows = session.execute(
        select(GameDuelRow).where(
            or_(GameDuelRow.user_a_id == user_id, GameDuelRow.user_b_id == user_id)
        )
    ).scalars().all()

    wins = losses = draws = voids = live = 0
    for d in rows:
        if d.state == "live":
            live += 1
        elif d.state == "void":
            voids += 1
        elif d.winner_user_id is None:
            draws += 1
        elif d.winner_user_id == user_id:
            wins += 1
        else:
            losses += 1
    return {
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "voids": voids,
        "live": live,
        "settled": wins + losses + draws,
    }


def settle_field_duels(session, field_id: UUID, *, now: datetime | None = None) -> dict:
    """Settle every live duel in a field. Called by the scoring pass AFTER
    every entry in the field has been scored, and inside its transaction.

    The ordering is the whole reason this is a separate phase rather than
    part of `_apply_score`: a duel needs BOTH sides' final TWR, and
    `_apply_score` runs per entry. Settling as each entry closed would decide
    half the duels against an opponent whose number did not exist yet.
    """
    now = now or datetime.now(timezone.utc)
    duels = session.execute(
        select(GameDuelRow).where(
            GameDuelRow.field_id == field_id, GameDuelRow.state == "live",
        )
    ).scalars().all()
    if not duels:
        return {"settled": 0, "void": 0, "ties": 0}

    settled = void = ties = 0
    for duel in duels:
        entries = {
            e.run_id: e for e in session.execute(
                select(GameEntryRow).where(
                    GameEntryRow.run_id.in_((duel.run_a_id, duel.run_b_id))
                )
            ).scalars().all()
        }
        a = entries.get(duel.run_a_id)
        b = entries.get(duel.run_b_id)
        # A side that never reached a terminal state is treated as void
        # rather than as a loss. Forfeiting is already debited by §6.7's own
        # rule; taking a duel loss on top would charge the same act twice.
        a_void = a is None or a.state != "finished"
        b_void = b is None or b.state != "finished"
        settle_duel(
            session, duel,
            twr_a_pct=float(a.final_twr_pct) if a and a.final_twr_pct is not None else None,
            twr_b_pct=float(b.final_twr_pct) if b and b.final_twr_pct is not None else None,
            a_is_void=a_void, b_is_void=b_void, now=now,
        )
        if duel.state == "void":
            void += 1
        elif duel.winner_user_id is None:
            ties += 1
            settled += 1
        else:
            settled += 1
    return {"settled": settled, "void": void, "ties": ties}


def duel_view_for_run(user_id: UUID, run_id: UUID) -> dict | None:
    """The live duel card for `GET /v1/games/runs/{run_id}` — §11.1's
    *"You vs VECTOR_11. 3 days left. They're 1.1% ahead"*, which is the whole
    reason duels exist at alpha field sizes.

    Returns None when this run has no duel. That is an ordinary state, not a
    degraded one: an odd human out simply has no opponent this period.

    **The delta is signed from THIS player's side, and it is computed here
    rather than on the client.** Both TWRs are on the wire, so a client could
    subtract them — and one that got the sign backwards would tell a losing
    player they were ahead. One subtraction, one place.

    Follows the board's own §6.1 invariant: percentages only, never a
    currency figure for anyone, and the opponent is identified by handle. A
    desk opponent is disclosed as one, with its published rule, exactly as on
    the board — the first-run duel is *"beat the Index Desk"*, and a player
    who did not know their opponent was the benchmark would be reading a
    different result than the one they got.
    """
    from app.services.games_board import _entrant_row

    with get_session() as s:
        duel = duel_for_run(s, run_id)
        if duel is None:
            return None
        opponent_user_id, opponent_run_id = opponent_of(duel, user_id)
        state, kind, cadence = duel.state, duel.kind, duel.cadence
        winner_user_id = duel.winner_user_id
        points_delta = duel.points_delta

    me = _entrant_row(user_id, run_id)
    them = _entrant_row(opponent_user_id, opponent_run_id)

    my_twr = me["twr_pct"]
    their_twr = them["twr_pct"]
    # Null-vs-zero, the ninth-instance bug class this feature keeps
    # producing: either side unmeasured means the gap is UNKNOWN, not level.
    # `0.0` here would draw a dead heat on a duel that has not started.
    lead_pct = (
        round(my_twr - their_twr, 4)
        if my_twr is not None and their_twr is not None
        else None
    )

    outcome = None
    if state == "settled":
        outcome = (
            "draw" if winner_user_id is None
            else ("won" if winner_user_id == user_id else "lost")
        )
    elif state == "void":
        outcome = "void"

    return {
        "duel_id": None,  # not addressable by the client; nothing routes on it
        "kind": kind,
        "cadence": cadence,
        "state": state,
        "opponent": {
            "handle": them["handle"],
            "is_desk": them["is_desk"],
            "desk_key": them["desk_key"],
            "desk_rule": them["desk_rule"],
            "twr_pct": their_twr,
        },
        "my_twr_pct": my_twr,
        # Positive = this player is ahead. Null while either side is
        # unmeasured — see above.
        "lead_pct": lead_pct,
        "outcome": outcome,
        # What the win or loss was worth. Symmetric, so one number serves
        # both sides; 0 on a tie or a void.
        "points_delta": points_delta,
        "points_at_stake": duel_points(cadence) if state == "live" else None,
    }


def close_verdict_for_run(user_id: UUID, run_id: UUID) -> dict | None:
    """The Close's beat-2 duel verdict (§10.2), or None if this run had no
    duel.

    A thinner shape than `duel_view_for_run` on purpose: the Close is a
    ceremony with a three-beat budget, and the run screen's live-gap
    machinery (points at stake, days left, an unmeasured-gap caption) is
    noise once the result exists. What survives is who, what happened, by how
    much, and what it was worth.
    """
    with get_session() as s:
        duel = duel_for_run(s, run_id)
        if duel is None:
            return None
        opponent_user_id, _opponent_run_id = opponent_of(duel, user_id)
        is_a = duel.user_a_id == user_id
        my_twr = duel.twr_a_pct if is_a else duel.twr_b_pct
        their_twr = duel.twr_b_pct if is_a else duel.twr_a_pct
        state, kind = duel.state, duel.kind
        winner_user_id, points_delta = duel.winner_user_id, duel.points_delta

        handle, display_name, is_desk, desk_key = s.execute(
            select(User.handle, User.display_name, User.is_desk, User.desk_key)
            .where(User.id == opponent_user_id)
        ).first() or (None, None, False, None)

    from app.services.games_desks import DESKS_BY_KEY

    desk = DESKS_BY_KEY.get(desk_key or "")
    outcome = (
        "void" if state == "void"
        else "draw" if winner_user_id is None
        else "won" if winner_user_id == user_id
        else "lost"
    )
    my_twr_f = float(my_twr) if my_twr is not None else None
    their_twr_f = float(their_twr) if their_twr is not None else None
    return {
        "state": state,
        # `duel_kind`, not `kind`: the Close's beat-2 envelope uses `kind` as
        # its own discriminator ("duel" vs "counterfactual"), and a duel
        # spread into it under the same key silently overwrote that — the
        # beat announced itself as `first_run`, which is not one of the
        # values the client switches on.
        "duel_kind": kind,
        "outcome": outcome,
        "opponent_handle": handle or display_name or "Unnamed",
        "opponent_is_desk": bool(is_desk),
        "opponent_desk_rule": desk.rule if desk else None,
        "my_twr_pct": my_twr_f,
        "opponent_twr_pct": their_twr_f,
        # Signed from this player's side, computed once here — see
        # `duel_view_for_run` for why a client must never derive it.
        "margin_pct": (
            round(my_twr_f - their_twr_f, 4)
            if my_twr_f is not None and their_twr_f is not None
            else None
        ),
        "points_delta": points_delta,
    }
