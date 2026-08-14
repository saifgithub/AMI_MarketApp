<!-- lane assign — Architect-owned. CR052. -->
# SIM-DEF305 — a fabricated price must never move a real ledger

KIND: code
INSTANCE: coder.api
GATE: independent    <!-- money math on live user ledgers; DISPATCH_PROTOCOL §4a routes this to an independent auditor on reversibility, not size. -->
BUDGET: $12
DEPENDS-ON: none
HOT-FILES: `backend/app/services/sim_engine.py` (no other lane live on it as of this writing — check `dispatch.sh state` before you start)
ACCEPTANCE: `docs/defect/_registry/DEF305.row.md`

## What and why

**Read `docs/defect/_registry/DEF305.row.md` in full first.** It carries the measured diagnosis off
live Alpha, including the eight fabricated close prices and the arithmetic that identifies them.

Short version: `yf.Ticker(t).fast_info.last_price` is intermittently raising
`'PriceHistory' object has no attribute '_dividends'` — 18 times in 6 hours, in bursts that take out
a whole batch of tickers at once. `YFinanceProvider.quote` returns `None`,
`FallbackProvider.quote` (`market_data.py:749`) silently substitutes the mock walk,
`SimEngine.current_price` (`:580`) keeps the float and **discards `Quote.source`**, and
`evaluate_outcomes` (`:2476`) compares that float to every open stop/target. A price drawn from
`[50, 450]` breaches one side of any real bracket, so the sweep does not close *some* positions —
on 2026-08-14 at 14:46:22Z it closed **all 8 bracketed positions on Alpha**, across two unrelated
users, and credited `closed_price × quantity` into their cash. HPQ (a $30 stock) was booked out at
$334.96.

**The guard you need already exists and this path does not call it.**
`sim_resting_orders.py:103::_quote_is_fillable` refuses exactly this, in exactly the right terms:

> A `mock_walk` price is a deterministic random walk with no relationship to reality. Booking a
> user's ledger off one is a fiction that never comes off the books.

It is applied at `:423` and `:568`, on the **entry** book. `_sweep_position_brackets` (`:332`) is in
the same file and in the same sweep call, but delegates to `SimEngine.evaluate_outcomes`, which
takes a `float` and therefore cannot consult a source it never receives. **The entry half of one
tick refuses to fill on a fake price while the exit half of the same tick liquidates the book on
one.** This is DEF190's shape: the guard is real, it is just not on the path that moves the money.

CR170 made it unattended — correctly (*"a stop-loss that only fires when you open the app is not a
stop-loss"*), but the tick runs every 5 minutes for all users with nobody watching, and it inherited
the unguarded price.

## Scope — the sites

`SimEngine` hands an unguarded `current_price()` float to **eight** money-moving sites. Fix the
class, not the instance that fired:

| Site | Line | What a fabricated price does |
|---|---|---|
| `evaluate_outcomes` | `:2476` | **the one that fired** — liquidates the position, credits fake proceeds |
| `manual_close` | `:2525` | books the user's own close at a fiction |
| `submit` | `:998` | a **buy** fills at a fabricated price |
| `submit_game_trade` | `:1570` | same, game lane |
| `evaluate_short_brackets` | `:2230` | inverted bracket, same failure |
| borrow accrual | `:2284` | charges borrow against a fictional mark |
| `check_margin_calls` | `:2328` | **force-closes** a short on a fiction |
| `cover_short` | `:2366` | books the cover at one |

`preview()` (`:1873`) already takes a `Quote` and already has a `price_source` field on its result —
look at what it does before designing anything, it is the closest thing to a correct shape in the
file.

## Fences

- **`backend/app/services/sim_engine.py`, `sim_resting_orders.py`, `market_data.py` and their tests
  are yours. Nothing else in `backend/app/` is.** Check `dispatch.sh state` for live lanes before
  you start and again before you commit.
- **Do NOT touch `mobile/`.**
- **Do NOT write to any user's ledger.** Saiful ruled explicitly (2026-08-14): *leave the data, fix
  the code only.* The two corrupted portfolios (`5a488bb8-2cd8-488b-8212-86b9209f81d2`,
  `0aff5dca-ed90-4b4a-9a59-dee7e0c4662a`) stay exactly as they are. No backfill script, no
  correction migration, no "while I was in there". If you conclude the data *should* be corrected,
  say so in the hand-off and stop — that decision is Saiful's and he has already made it.
- **Do NOT write a second copy of `_quote_is_fillable`.** One predicate, reused. DEF098's lesson —
  *one function, two lanes, no second derivation to drift.* If it needs to move to be importable
  from `sim_engine`, move it and leave the resting-order call sites calling the same object.
- **Do NOT break mock-only mode.** `_quote_is_fillable` refuses `mock_walk` **only when
  `settings.use_real_market_data` is on**, because with real data off the mock walk *is* the intended
  provider. Preserve that branch exactly — the Mac's test fixture and any local/dev run depend on it.
- **Do NOT bump or pin `yfinance`.** The library fault is real and worth fixing, but it is a
  dependency change with its own blast radius and it is not this lane. Report what you learn about
  it (below); do not act on it.

## Acceptance

1. **A test that FAILS against current code**, reproducing the live event: a portfolio with a
   bracketed open position, a provider stack whose quote resolves to `mock_walk` while
   `use_real_market_data` is true, one `evaluate_outcomes` pass ⇒ assert the position is **still
   open**, `current_cash` is **unchanged**, and no `sim_trades` row was stamped. Write it first,
   watch it go red. Use the real numbers from the row if it helps: HPQ entry `28.52`, target
   `32.23`, mock price `334.96`.
2. **Refusal is a skip, not a close, and never an exception.** A refused tick must leave the
   position exactly as it found it and let the next tick try again. It must not raise — one bad
   ticker must not stop the sweep for other users (`_sweep_position_brackets` already catches, do
   not rely on that as the mechanism).
3. **All eight sites covered**, one test per site. Do not fix the one that fired and assume the
   rest. Where a site's honest behaviour on refusal is *not* "skip" — a user-initiated
   `manual_close` or `submit` should arguably **fail loudly to the caller** rather than silently do
   nothing — decide it per site, state the reasoning in the hand-off, and make the user-facing
   message say AMI cannot price the ticker right now, **never** "the AI".
4. **The guard is on the path, not beside it.** A test that exercises the helper proves nothing
   about whether the argument arrives (DEF190). At least one test must assert at the **call site** —
   that `evaluate_outcomes` consults the source, e.g. by driving it through a provider stack rather
   than by calling the predicate directly.
5. **Degrade loudly (CR040).** `FallbackProvider.quote` currently falls through with **no log, no
   counter, no signal of any kind** — that silence is why this ran for hours undetected and why the
   only evidence left was the `[50, 450]` band being visible to the naked eye. Emit a warning when
   the secondary serves under `use_real_market_data`, and surface a count in the sweep's existing
   `sim_resting_order_sweep_complete` stats line (it already carries `aborted` and
   `_UNFILLABLE_ABORT_RATIO` — reuse that shape rather than inventing a parallel one). Ask before
   adding any new config key; this lane should need none.
6. **Provenance on the trade row — answer, do not necessarily build.** `sim_trades` records no price
   source, which is why an eight-position corruption was diagnosable only by eyeball. State in the
   hand-off whether a `price_source` column belongs there and what it would cost. **Do not add a
   migration in this lane** — schema is a separate decision and it is mine.
7. **Mutation:** revert the guard at each site in turn and show the corresponding test goes RED.
   Report honestly, **including any that come back GREEN** — a green mutation means that site's test
   is not testing the guard.
8. Full suite from repo root: `"./backend/.venv/bin/python" -m pytest backend/tests/unit/ -q`.
   **`python` is not on PATH. Never use `-x`.** Baseline measured 2026-08-14: **4182 passed, 3
   skipped, 0 failed** (~8 min). Finish `>= 4182`, zero failures. **Do not pipe pytest through
   `tail`/`head` and read the exit code** — you get the pipe's exit code, not pytest's. Tee to a
   file and read the `N passed, M failed` line.

## Report back (do not act on these)

- **The yfinance fault itself.** `'PriceHistory' object has no attribute '_dividends'` on
  `fast_info.last_price` — is this a known upstream bug, a version mismatch with our pin, or
  something about how we construct the `Ticker`? Reproduce it if you can and say what you found. A
  fix there reduces how often the guard fires; it does not replace the guard, and it is a separate
  lane.
- **Whether the guard changes what a user sees.** With it in place, a burst means stops do not fire
  for those minutes. That is the correct trade — a missed stop is recoverable, a fabricated fill is
  not — but say plainly what the user experiences, so the decision is on the record.

## Registers

Flip `docs/defect/_registry/DEF305.row.md` to `fixed` only if you closed it fully, then
`python3 scripts/registers/gen_registers.py gen def`, and commit the row file and the regenerated
table **in the same commit** (DEF159). **Explicit pathspec — never `git add -A`, never bare commit.**

## Hand-off delivery

**Write your hand-off file EARLY and keep updating it** — a budget cap that kills you mid-lane with
the hand-off unwritten is the worst place to stop.

Write `orchestration/dispatch/lanes/SIM-DEF305.coder.api.md` with `STATUS: READY_FOR_AUDIT (round 1)`;
get it onto `main` AND push your lane branch to origin (**DEF175**).

`GATE: independent` — write your submit file `orchestration/audit/cr/SIM-DEF305.architect.md` on
hand-off. An independent auditor gates this; I do not integrate on my own verification.

**If you can measure that an instruction here is wrong, stop and disclose with the measurement.**
This is money math on live ledgers; a confident wrong answer here is worse than a disclosed gap.

ASSIGNED: coder.api round 1
DISPATCH: OPEN
