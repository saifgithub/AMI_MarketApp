"""DEF377 — find every stored bracket sitting on the wrong side of its entry.

Read-only. Prints one line per offending row across both books and exits 1 if
any exist, so it can be run as a check rather than read as a report.

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


def main() -> int:
    findings: list[str] = []
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
                findings.append(
                    f"sim_trades       {row.id} {row.ticker:<6} {side:<5} "
                    f"status={row.status:<6} entry={float(row.entry_price):>10.4f} "
                    f"stop={_num(row.stop)} target={_num(row.target)} :: {reason}"
                )
        for row in s.execute(select(SimShortPositionRow)).scalars():
            reason = bracket_is_wrong_side(
                is_short=True, entry=float(row.entry_price),
                stop=_num(row.stop), target=_num(row.target),
            )
            if reason is not None:
                findings.append(
                    f"sim_short_positions {row.id} {row.ticker:<6} "
                    f"state={row.state:<6} entry={float(row.entry_price):>10.4f} "
                    f"stop={_num(row.stop)} target={_num(row.target)} :: {reason}"
                )

    for line in findings:
        print(line)
    print(f"DEF377 CENSUS: {len(findings)} wrong-side bracket(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
