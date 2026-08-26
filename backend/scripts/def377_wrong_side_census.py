"""DEF377 — find every stored bracket sitting on the wrong side of its entry.

Read-only. Prints one line per offending row across both books, in two buckets,
and exits 1 only on the bucket that can still act.

**Both buckets, and only one of them is a failure.** The first run of this
script against the promoted build exited 1 on three rows that had already been
remediated — their `status` was corrected but the levels they were entered with
are still on the row, as history. A check that fails on rows nobody can act on
would fail on every run, forever, and a gate whose failing state IS its normal
state teaches the operator to reason past it: that is DEF277 exactly, and it is
the shape this whole session has been removing. So ACTIVE — a bracket that a
sweep could still read — is the exit code; HISTORICAL is printed and costs
nothing, because a closed row's levels are a record of what the user typed, not
an instruction anything will follow.

**Why a script and not a test.** The guard in `sim_engine` stops the sweep
firing on these rows; it cannot delete them, and it must not — inventing a
level a user never set is the same class of fabrication the guard exists to
prevent. So a corrupt row stays corrupt until an operator looks at it, and this
is what an operator looks with. Run it against Alpha after any promotion that
touches the bracket path, and after any backfill that writes `stop`/`target`:

    ssh melehost "cd ~/ami_trade && docker compose exec -T api-alpha \\
        python scripts/def377_wrong_side_census.py"

The rule is imported from `order_pricing`, never restated here. A census that
carried its own copy of "which side does a stop belong on" would be DEF098's
shape — and DEF312 is already what happens when that rule gets written twice.
"""

from __future__ import annotations

import sys

from sqlalchemy import select

from app.db import get_session
from app.db.models import SimShortPositionRow, SimTradeRow
from app.trading_math.order_pricing import bracket_is_wrong_side


def _num(v) -> float | None:
    return None if v is None else float(v)


#: The only states in which a stored bracket is still read by a sweep.
ACTIONABLE_TRADE_STATUS = frozenset({"open"})
ACTIONABLE_SHORT_STATE = frozenset({"open"})


def is_actionable(state: str | None) -> bool:
    """Can a sweep still fire on this row's bracket?

    `evaluate_outcomes` filters `status == "open"` and `evaluate_short_brackets`
    filters `state == "open"`; everything else has already exited. Written once,
    here, against those two filters — a census that guessed at this would fail
    the first time a new terminal status appeared.
    """
    return str(state) in ACTIONABLE_TRADE_STATUS | ACTIONABLE_SHORT_STATE


def main() -> int:
    active: list[str] = []
    historical: list[str] = []
    with get_session() as s:
        # Long book. EVERY status, not just `open`: a row already closed on a
        # bracket that could not fire honestly is carrying a won/lost verdict
        # the market never delivered, and that verdict is on a track record.
        for row in s.execute(select(SimTradeRow)).scalars():
            side = row.side.value if hasattr(row.side, "value") else str(row.side)
            if side != "buy":
                continue
            reason = bracket_is_wrong_side(
                is_short=False, entry=float(row.entry_price),
                stop=_num(row.stop), target=_num(row.target),
            )
            if reason is not None:
                line = (
                    f"sim_trades       {row.id} {row.ticker:<6} {side:<5} "
                    f"status={row.status:<6} entry={float(row.entry_price):>10.4f} "
                    f"stop={_num(row.stop)} target={_num(row.target)} :: {reason}"
                )
                (active if is_actionable(row.status) else historical).append(line)
        for row in s.execute(select(SimShortPositionRow)).scalars():
            reason = bracket_is_wrong_side(
                is_short=True, entry=float(row.entry_price),
                stop=_num(row.stop), target=_num(row.target),
            )
            if reason is not None:
                line = (
                    f"sim_short_positions {row.id} {row.ticker:<6} "
                    f"state={row.state:<6} entry={float(row.entry_price):>10.4f} "
                    f"stop={_num(row.stop)} target={_num(row.target)} :: {reason}"
                )
                (active if is_actionable(row.state) else historical).append(line)

    if historical:
        print("HISTORICAL — already exited, kept as the record of what was entered:")
        for line in historical:
            print(f"  {line}")
    if active:
        print("ACTIVE — a sweep still reads these:")
        for line in active:
            print(f"  {line}")
    print(
        f"DEF377 CENSUS: {len(active)} active, {len(historical)} historical "
        f"wrong-side bracket(s)"
    )
    return 1 if active else 0


if __name__ == "__main__":
    sys.exit(main())
