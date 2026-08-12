"""CR109 slice 8 — progress markers (design §8.4).

> *"If one player in 26 receives something, twenty-five received nothing, and
> that is the churn."* This is a bigger retention lever than the champion
> prize.

Every close yields **one** marker where one is true — a personal best, a
first, a streak. §8.4's own framing is *"evidence of movement, not
participation trophies"*, which is why every marker here is a THRESHOLD
CROSSED rather than a thing that happens for showing up: the finish stipend
already pays for showing up, and §8.4 says so explicitly (*"one ethos, said
twice: a marker is the qualitative version, the stipend is the number that
moves"*).

**One marker, not a list**, for the same reason the Close has a three-beat
budget: a screen that hands out five achievements at once has handed out
none. The priority below runs firsts → bests → streaks, because a first is
the only one that can never happen again.

**Markers are never points.** §10.4: *"Challenge completions are markers,
never points — the career ledger must never pay for a self-imposed
constraint, or constraints become the farm this section exists to avoid."*
Nothing in this module writes to `career_ledger`, and nothing may.

**Computed, never stored.** A marker is a statement about a run's place in
the player's history, and history keeps growing — "first positive run" is
answered by looking at what came before, which is exactly what the query
below does. Storing it at close would freeze an answer that was only ever
true relative to a set that has since changed.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from app.db import get_session
from app.db.models import GameEntryRow, GameFieldRow

# §8.4's list, as kinds. Copy is the client's — these are the keys an ARB
# string is written against, so a translator can hold each to the design's
# "evidence of movement, never a scold" rule.
MARKER_FIRST_FINISH = "first_finish"
MARKER_FIRST_POSITIVE = "first_positive"
MARKER_FIRST_PODIUM = "first_podium"
MARKER_PERSONAL_BEST = "personal_best_twr"
MARKER_CLEAN_STREAK = "clean_streak"

# §8.4 names "five finishes without a forfeit". One constant, first cut.
CLEAN_STREAK_TARGET = 5

# §8.4 says "first time in the top ten", which presupposes a field with more
# than ten in it. Below that the phrase is not a smaller version of itself —
# it is meaningless, because everyone is in the top ten. So the podium marker
# is gated on a field big enough for a placing to mean something, the same
# posture slice 4's `PLACEMENT_MIN_FIELD` fence takes toward the scoring
# curve. Rank is still a fact at every size; only the CELEBRATION is gated.
PODIUM_MIN_FIELD = 8
PODIUM_MAX_RANK = 3


def marker_for_close(user_id: UUID, run_id: UUID) -> dict | None:
    """The one marker this close earned, or `None` when it earned none.

    `None` is a real and frequent answer, and it is better than the
    alternative: a marker invented for every close is a participation trophy,
    which is the thing §8.4 distinguishes itself from in its first sentence.
    """
    with get_session() as s:
        rows = s.execute(
            select(GameEntryRow, GameFieldRow.ends_on)
            .join(GameFieldRow, GameEntryRow.field_id == GameFieldRow.id)
            .where(GameEntryRow.user_id == user_id)
            .order_by(GameFieldRow.ends_on.asc())
        ).all()

    this_entry = next((e for e, _ in rows if e.run_id == run_id), None)
    if this_entry is None or this_entry.state != "finished":
        return None
    twr = float(this_entry.final_twr_pct) if this_entry.final_twr_pct is not None else None
    if twr is None:
        return None

    # Everything that closed BEFORE this one — the set the "first" and "best"
    # claims are measured against. Keyed on the entry, not the date, so two
    # runs of different cadences ending on the same day cannot each claim to
    # be the other's first.
    seen_this = False
    prior: list[GameEntryRow] = []
    for entry, _ends_on in rows:
        if entry.run_id == run_id:
            seen_this = True
            continue
        if not seen_this:
            prior.append(entry)
    prior_finished = [e for e in prior if e.state == "finished"]

    if not prior_finished:
        return {"kind": MARKER_FIRST_FINISH, "value": None}

    if twr > 0 and not any(
        e.final_twr_pct is not None and float(e.final_twr_pct) > 0
        for e in prior_finished
    ):
        return {"kind": MARKER_FIRST_POSITIVE, "value": round(twr, 2)}

    rank = this_entry.final_rank
    field_size = this_entry.scored_entrant_count or 0
    if (
        rank is not None
        and rank <= PODIUM_MAX_RANK
        and field_size >= PODIUM_MIN_FIELD
        and not any(
            e.final_rank is not None
            and e.final_rank <= PODIUM_MAX_RANK
            and (e.scored_entrant_count or 0) >= PODIUM_MIN_FIELD
            for e in prior_finished
        )
    ):
        return {"kind": MARKER_FIRST_PODIUM, "value": rank}

    best_prior = max(
        (float(e.final_twr_pct) for e in prior_finished if e.final_twr_pct is not None),
        default=None,
    )
    if best_prior is not None and twr > best_prior:
        return {"kind": MARKER_PERSONAL_BEST, "value": round(twr, 2)}

    # §8.4's "five finishes without a forfeit", counted backwards from THIS
    # close rather than over the whole history — the run being closed is the
    # fifth, or there is nothing to say yet.
    #
    # Reported only ON the crossing (`== `, not `>= `), because a marker that
    # fires on every close after the fifth stops being evidence of movement
    # and becomes the participation trophy §8.4 opens by excluding.
    ordered = [e for e, _ in rows]
    here = next(i for i, e in enumerate(ordered) if e.run_id == run_id)
    streak = 0
    for entry in reversed(ordered[: here + 1]):
        if entry.state != "finished":
            break
        streak += 1
    if streak == CLEAN_STREAK_TARGET:
        return {"kind": MARKER_CLEAN_STREAK, "value": streak}

    return None
