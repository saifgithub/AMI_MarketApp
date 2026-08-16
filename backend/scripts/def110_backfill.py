"""DEF110 backfill — remove the phantom holdings the old `evaluate_outcomes`
left behind, and credit the sale proceeds it never paid.

The code fix (`SimEngine.evaluate_outcomes` now liquidates on a stop/target
hit) stops NEW phantoms. It does nothing about the rows already written: every
position that self-closed before the fix shipped is still sitting in
`sim_holdings`, and its proceeds are still missing from `current_cash`. This
script repairs that state. It is a one-time repair, but written to be safely
re-runnable — see "Idempotence" below.

What it does NOT do: re-realise P&L. `realised_pnl` was correctly stamped on
every affected trade at close time. Only shares and cash move here.

Idempotence — why this is a state repair, not a replay:

    A replay ("for each won/lost trade, credit its proceeds") double-credits
    on a second run. Instead we compute the drift from the trade ledger's own
    view of what should be held:

        expected(portfolio, ticker) = Σ quantity_open over that ticker's FIFO lots

    Anything `sim_holdings` carries above `expected` is phantom. Once repaired
    the drift is zero, so a second run finds nothing to do.

    **DEF319 — this used to be its own formula**, `Σ open buys − Σ open sells`,
    justified as "the same rule `cost_basis_lots.py` already applies". It was
    not the same rule, and the gap opened on an ordinary sequence:

        buy 10 @ $100  ·  sell 4 through the ticket  ·  the other 6 stop out

    The stopped-out BUY row leaves the open set carrying all 10, while the SELL
    row keeps subtracting its 4 — so `expected` reads −4 against a holding of 0
    and this script reports **4 phantom shares that do not exist**. The premise
    that made the formula look sound (*"a self-close never produces a sell
    row"*) is true of whole positions and false of partial ones. Two derivations
    of one fact, drifting exactly where it mattered — DEF098's shape, in the
    detector built to catch drift.

    It now calls `cost_basis_lots.open_quantity`, which sums
    `compute_lots_fifo`'s `quantity_open`: the audited FIFO
    primitive (CR029-MATH) is the single derivation of "how much of this lot is
    still held", shared with `SimEngine`'s bracket gates (DEF318), the
    position-level bracket (CR189), the per-lot display, and the autouse ledger
    invariant in `tests/conftest.py`.

Cash is attributed by walking that ticker's won/lost buy trades oldest-close
first and crediting each consumed chunk at its own `closed_price` — the price
the sale should have executed at, not today's mark.

Reuses `SimEngine._apply_sell_row` rather than issuing its own UPDATE. That
private call is deliberate: "reduce the holding and credit the proceeds" must
have exactly one implementation, or this script and the engine drift apart
(the DEF098 failure class — two renderers of one rule, neither a superset).

Usage — runs INSIDE the api container, which is the only place with both the
real `DATABASE_URL` and the `app` package (the Mac has no DB; see CLAUDE.md).
`backend/Dockerfile` copies only `app/`, `tests/` and `alembic/`, so this file
is NOT in the image and has to be copied in. `ENV PYTHONPATH=/app` makes the
`app.*` imports resolve from anywhere in the container.

    scp backend/scripts/def110_backfill.py melehost:/tmp/
    ssh melehost "docker cp /tmp/def110_backfill.py ami_api_alpha:/tmp/"

    # dry run (default) — prints the plan, writes nothing
    ssh melehost "docker exec ami_api_alpha python /tmp/def110_backfill.py"

    # apply
    ssh melehost "docker exec ami_api_alpha python /tmp/def110_backfill.py --apply"

Exit codes: 0 clean (nothing to do, or everything attributable was applied);
2 if any phantom shares could not be attributed to a closed trade. Under
--apply, exit 2 does NOT mean nothing was written: whatever WAS attributable
is committed same as a clean run, and only the unattributed remainder is left
in place (see "LEFT IN PLACE" in the printed plan). Exit 2 flags unexplained
drift that wants eyes on the next run, not a rollback of the current one —
check the printed plan, not just the exit code, before assuming a repair was
a no-op.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict

from sqlalchemy import select

from app.db.models import SimHoldingRow, SimPortfolioRow, SimTradeRow
from app.db.session import get_sessionmaker
from app.services.cost_basis_lots import open_quantity
from app.services.sim_engine import SimEngine


_EPS = 1e-6


def _plan_and_apply(s, engine: SimEngine) -> tuple[list[str], float, float, int]:
    """Repair every portfolio in place. Returns (lines, shares, cash, unattributed)."""
    lines: list[str] = []
    total_shares = 0.0
    total_cash = 0.0
    unattributed = 0

    portfolios = s.execute(select(SimPortfolioRow)).scalars().all()
    for p_row in portfolios:
        trades = s.execute(
            select(SimTradeRow).where(SimTradeRow.portfolio_id == p_row.id)
        ).scalars().all()

        # DEF319 — one derivation, `cost_basis_lots.open_quantity`, instead of
        # the parallel formula this script used to carry. See the module
        # docstring. The R70 audit's MINOR-1: the *rule* was single-sourced
        # from the first fix, but the SUMMING step was still written out here
        # and again in the invariant that guards this script, so it is now one
        # function both call.
        by_ticker: dict[str, list[SimTradeRow]] = defaultdict(list)
        for t in trades:
            by_ticker[t.ticker].append(t)

        expected: dict[str, float] = defaultdict(float)
        for ticker, rows in by_ticker.items():
            expected[ticker] = open_quantity(rows)

        # Oldest close first, so proceeds are attributed in the order the
        # sales should have happened.
        closers: dict[str, list[SimTradeRow]] = defaultdict(list)
        for t in trades:
            side = t.side.value if hasattr(t.side, "value") else str(t.side)
            if side == "buy" and t.status in ("won", "lost"):
                closers[t.ticker].append(t)
        for rows in closers.values():
            rows.sort(key=lambda r: (r.closed_at is None, r.closed_at))

        holdings = s.execute(
            select(SimHoldingRow).where(SimHoldingRow.portfolio_id == p_row.id)
        ).scalars().all()

        block: list[str] = []
        for h in holdings:
            phantom = float(h.quantity) - expected.get(h.ticker, 0.0)
            if phantom <= _EPS:
                continue

            cash_before = float(p_row.current_cash)
            remaining = phantom
            for t in closers.get(h.ticker, []):
                if remaining <= _EPS:
                    break
                if t.closed_price is None:
                    block.append(
                        f"  !! {h.ticker}: trade {t.id} is {t.status} with no "
                        f"closed_price — cannot price its proceeds, skipped"
                    )
                    continue
                chunk = min(remaining, float(t.quantity))
                sold = engine._apply_sell_row(
                    s, p_row, h.ticker, chunk, float(t.closed_price),
                )
                remaining -= sold
                if sold <= _EPS:
                    break

            credited = round(float(p_row.current_cash) - cash_before, 2)
            moved = phantom - remaining
            total_shares += moved
            total_cash += credited
            block.append(
                f"  {h.ticker:<6} phantom {phantom:>10.4f}  removed {moved:>10.4f}"
                f"  cash +{credited:>10.2f}"
            )
            if remaining > _EPS:
                unattributed += 1
                block.append(
                    f"  !! {h.ticker}: {remaining:.4f} phantom shares with no "
                    f"closed trade to attribute them to — LEFT IN PLACE"
                )

        if block:
            lines.append(f"user {p_row.user_id}  (cash now {float(p_row.current_cash):.2f})")
            lines.extend(block)

    return lines, total_shares, total_cash, unattributed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--apply", action="store_true",
        help="commit the repair (default is a dry run that rolls back)",
    )
    args = ap.parse_args(argv)

    engine = SimEngine()
    session = get_sessionmaker()()
    try:
        lines, shares, cash, unattributed = _plan_and_apply(session, engine)
        session.flush()

        mode = "APPLY" if args.apply else "DRY RUN"
        print(f"DEF110 backfill — {mode}")
        print("-" * 60)
        for line in lines:
            print(line)
        if not lines:
            print("  nothing to repair — no phantom holdings found")
        print("-" * 60)
        print(f"  phantom shares removed : {shares:.4f}")
        print(f"  cash credited          : {cash:.2f}")
        if unattributed:
            print(f"  UNATTRIBUTED holdings  : {unattributed} (left in place)")

        if args.apply:
            session.commit()
            print("\ncommitted.")
        else:
            session.rollback()
            print("\nrolled back — re-run with --apply to write.")
        return 2 if unattributed else 0
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
