# CR194 — price provenance on `sim_trades`

**Status:** proposed · **Raised:** 2026-08-18 (AT:R70) · **Origin:** the schema question
[DEF305](../../defect/def_list.md)'s lane deliberately left open, answered by the architect rather
than decided inside a money-math lane.

## Why this exists

DEF305 corrupted two portfolios: a yfinance outage fell through to a deterministic random walk, and
the stop/target sweep liquidated every bracketed position in the system at fabricated prices,
crediting `$6,882.22` of invented proceeds into real cash. Saiful's ruling was **leave the data, fix
the code only**, so those rows are permanent and any later reading of his training history has to
know they are fiction.

The diagnosis worked. But look at *how* it worked:

> `_PriceWalk.price_at` does `round(v, 2)`, so every mock price stores as `.XX00` in a
> `Numeric(12,4)` column, while yfinance fills all four. **Every fabricated close in this row ends
> in two zeros; the one legitimate close does not.**

That is what separated nine fabricated closes from one legitimate `TSLA` stop firing correctly. It
is an accident of rounding. Nobody designed it, no test protects it, and it disappears the day
someone changes that rounding or a genuine quote lands on a round cent.

`sim_trades` records **no price provenance at all**. An eight-position corruption of a live ledger
was diagnosable only because a coincidence held.

## The objection, and why it does not win

Once DEF305's guard lands, a `mock_walk` price can never book a fill. So this column would read
`yfinance` on essentially every row forever — and *a column whose value is constant is not
evidence*. That is DEF123's lesson exactly (six attempts at labelling fabricated data, all of which
shipped a better disclosure string around the same rng scaffolding; the fix that worked removed the
data instead of describing it).

It does not win, because this column is not a label on fabricated data. Nothing fabricated is
supposed to survive the guard. It is the **audit trail that proves the guard held** — the thing that
turns a future regression into one query instead of an eyeball exercise on decimal places. The same
argument that makes a log worth keeping after you have fixed the bug.

## Scope

**In**

1. `sim_trades.price_source` and `sim_trades.close_price_source`, both nullable text, one Alembic
   revision.
2. Written explicitly at every site that creates or closes a trade row.
3. A test that a fill records the source it was actually priced from — asserted at the call site,
   not on a helper (DEF190).

**Out, and why**

- **No `server_default`, no backfill.** Same rule as CR141's usage columns: a row written by a site
  that forgot to set it must read **NULL**, because "we do not know" and "it was a real quote" are
  different facts and only one of them is a measurement (CR040). Defaulting to `'yfinance'` would
  manufacture the exact reassurance this CR exists to stop manufacturing.
- **Existing rows stay NULL.** All 111 of them (34 closed, measured 2026-08-18) predate the column.
  A backfill would be inventing provenance for precisely the rows whose provenance is in question —
  including the nine fabricated closes.
- **Not folded into DEF305's lane.** That lane is `GATE: independent` money math on live ledgers and
  its assign says schema is a separate decision. Adding a migration to it would widen an audited
  lane mid-flight.

## Acceptance

1. A fill priced from a live quote records the provider that served it.
2. A trade row created by a path that does not set the field reads NULL, not a default.
3. The 111 pre-existing rows are unchanged and still NULL after the migration.
4. Reverting the write at any one site reds a test that asserts at that site.

## Sequencing

**After DEF305's fix lands**, not before. Until the guard is in, the interesting value of this
column would be `mock_walk` on rows that should never have existed — and DEF305's lane must not be
widened while it is under independent audit.
