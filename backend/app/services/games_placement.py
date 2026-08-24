"""CR207 — the one place that decides what a finished run's placement MEANS.

The Close screen and the settlement push both have to answer the same
question — *where did this player end up, and may we say so?* — and before
this module they answered it in two languages. `games_close_screen.dart`
resolved it from `isThinField` / `rank != null` / `rankedFieldSize`, and the
push did not resolve it at all: it said *"Your week results are ready"* and
left the result out of the message entirely.

Resolving it here follows the precedent `_wind_up_block` set in
`games_record_service` and states in its own comment: decide from stored
columns on the server, so the client never re-derives a rule that governs
the highest-attention screen in the product. A threshold duplicated on both
sides is a threshold that will eventually disagree with itself.

**Why the kinds are separate rather than a rank plus a couple of booleans.**
Every one of them is a different sentence, and three of them must NOT assert
a position:

  * `void`         — the run has no usable result. Not last place.
  * `unmeasured`   — no `final_rank` was ever written. The absence of a
                     measurement, which is not the same fact as a bad one
                     (DEF059: `?? 0` renders "not measured" as "zero").
  * `thin_field`   — a rank exists, but the field was too thin for placement
                     to be the scoring basis, so the run was scored against
                     the index. Saying "you came 2nd of 3" here describes a
                     contest the scoring did not actually run.

and three of them do:

  * `champion`     — sole rank 1.
  * `co_champion`  — rank 1 shared. Standard competition ranking (1, 1, 3)
                     is what `games_scoring_pass` writes, so this is a real
                     and reachable state, not a defensive branch.
  * `tied`         — any other shared rank. The live 2026-08-14 field has
                     two entrants at rank 3 of 4; DEF343 is the in-app half
                     of this same fact, where the tied player renders
                     visually last with no tie marker.
  * `ranked`       — a clean, sole position.

`thin_field` deliberately outranks `champion`: winning a field that was too
small to be scored as a field is not a win to announce.
"""

from __future__ import annotations

from typing import NamedTuple

# `games_scoring_pass` writes "benchmark" when the comparable-entry count is
# below PLACEMENT_MIN_FIELD (or zero). Imported as a literal rather than from
# that module to keep this one free of DB imports and trivially testable; the
# string is the stored column's value, not a threshold, so it cannot drift.
BASIS_BENCHMARK = "benchmark"


class Placement(NamedTuple):
    """What may be said about where a run finished, and the numbers to say it with.

    `field_size` is the `n` the rank was actually taken over — never the raw
    entrant count when a scored count exists, because entries that voided
    were never comparable: "3rd of 9" in a field where two runs voided is a
    sentence about a contest that did not happen. `None` rather than `0`
    when neither count is usable, so a caller cannot render "1st of 0".
    """

    kind: str
    rank: int | None
    field_size: int | None
    tie_count: int

    @property
    def asserts_position(self) -> bool:
        return self.kind in ("champion", "co_champion", "tied", "ranked")


def resolve(
    *,
    state: str,
    scoring_basis: str | None,
    final_rank: int | None,
    scored_entrant_count: int | None,
    entrant_count: int | None,
    tie_count: int = 1,
) -> Placement:
    """Resolve a closed entry's placement from its stored columns only.

    Pure and DB-free on purpose: every branch below is a sentence a real user
    reads, and the cost of testing them should be zero.
    """
    size = _field_size(scored_entrant_count, entrant_count)

    if state == "void":
        return Placement("void", None, size, 0)
    if final_rank is None:
        return Placement("unmeasured", None, size, 0)
    if scoring_basis == BASIS_BENCHMARK:
        return Placement("thin_field", final_rank, size, max(1, tie_count))

    ties = max(1, tie_count)
    if final_rank == 1:
        return Placement("champion" if ties == 1 else "co_champion", 1, size, ties)
    return Placement("ranked" if ties == 1 else "tied", final_rank, size, ties)


def _field_size(scored: int | None, entrants: int | None) -> int | None:
    if scored is not None and scored > 0:
        return scored
    if entrants is not None and entrants > 0:
        return entrants
    return None


def push_copy(placement: Placement, *, cadence: str) -> tuple[str, str]:
    """The settled push's (title, body).

    Server-authored English, like every other beat in `games_push` — the
    notification bodies are not localised today, and inventing a second
    localisation path for one beat would be a bigger change than this CR.

    The three non-asserting kinds each get their own honest sentence rather
    than a shared "results are ready", which is the copy this CR exists to
    replace: it told the player their result existed without telling them
    what it was, and that is the half of the ceremony that reaches someone
    who has not opened the app.
    """
    if placement.kind == "void":
        return ("Your run was voided", f"Your {cadence} run could not be scored.")
    if placement.kind == "unmeasured":
        return ("Your run has settled", f"Your {cadence} results are ready.")
    if placement.kind == "thin_field":
        return (
            "Your run has settled",
            f"Your {cadence} run was scored against the S&P 500, not the field.",
        )

    of = f" of {placement.field_size}" if placement.field_size else ""
    if placement.kind == "champion":
        return ("You won your field", f"You finished 1st{of}.")
    if placement.kind == "co_champion":
        return ("You tied for 1st", f"You finished joint 1st{of}.")
    if placement.kind == "tied":
        return (
            "Your run has settled",
            f"You finished joint {_ordinal(placement.rank)}{of}.",
        )
    return ("Your run has settled", f"You finished {_ordinal(placement.rank)}{of}.")


def _ordinal(n: int | None) -> str:
    if n is None:
        return "unranked"
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"
