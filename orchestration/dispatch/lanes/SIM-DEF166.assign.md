<!-- lane assign — Architect-owned. CR052. -->
# SIM-DEF166 — the ledger and the P&L disagree about how many shares were sold

KIND: code
INSTANCE: coder.api
GATE: none    <!-- Sprint mode (Saiful, 2026-07-30): lanes integrate on my verification; track U audits the whole sprint as one item at the end. -->
BUDGET: $8
DEPENDS-ON: none

## What and why

`docs/defect/_registry/DEF166.row.md` — **read it in full, it carries the measured diagnosis.**

This is the highest-value open defect in the backlog and the only money-math inconsistency among
them. On a **clamped close**, `sim_engine.py:858` credits cash for the shares *actually* sold after
clamping, while the realised-P&L stamp uses `t.quantity` — the **full requested** quantity. So a
partially-fillable close shows a realised P&L whose magnitude the cash movement cannot support. The
journal's per-trade P&L and the portfolio's cash balance cannot both be right, and the
streaks/outcome surfaces read from the wrong one.

**It is now two sites, not one.** The behaviour is inherited from `manual_close` (:883-885), and
**DEF110 propagated it to outcome liquidation** — a path that had one instance now has two. Fix
both.

**Why it stayed green:** the clamp test pins the cash figure and never inspects P&L. A guard that
covers the branch but not the field. That is the same shape as DEF165 and DEF163 in this sprint, and
it is why "there is a test for that" is not an answer here.

**CR131 (Day Trader outcome instrumentation) depends on this landing correctly** — it will build
statistics on top of `realised_pnl`, so a wrong stamp becomes a wrong conclusion presented to the
user as evidence about their own trading.

## Fences

- **`backend/app/services/sim_engine.py` and `backend/scripts/def110_backfill.py` are yours.
  Nothing else in `backend/app/` is.** Three other backend lanes are live in parallel worktrees:
  `BE-MINOR` owns `sector_allocation.py` / `safety_floor.py` / `overlay_generator.py`, `BE-MANDATE`
  owns `api/mandate.py` / `mandate_store.py` / `one_on_one.py` / `brief_engine.py`, `ROOM-MINOR`
  owns `room_runner.py`. Do not edit any of them.
- **Do NOT touch `mobile/`.**
- **Do NOT "tidy up" the permanently-open sell rows.** They are **load-bearing for the DEF110
  backfill formula**. See acceptance 4.
- **Do not run the backfill script against anything.** This lane changes code and tests only.
  Whether historical rows need correcting is a separate decision and it is mine, not yours — but
  **do tell me in the hand-off** whether you believe already-written rows carry the wrong
  `realised_pnl`, and how one would identify them. That is the question I will have to answer next.

## Acceptance

1. **A test that FAILS against current code**, asserting that on a clamped close the realised P&L
   and the cash movement describe the **same share count**. Write it first, watch it go red.
2. **Both sites stamp `realised_pnl` on the clamped quantity** — the `manual_close` path and the
   DEF110 outcome-liquidation path. A test per site; do not fix one and assume the other.
3. **The existing clamp test is extended to assert cash and P&L agree**, rather than leaving a new
   parallel test beside a guard that still only checks cash. The row asks for this specifically —
   the old test's silence is part of the defect.
4. **The coupling is written down where a future editor will see it.** The permanently-open sell
   rows are load-bearing for the backfill formula, and nothing currently enforces that. Put the note
   at the sell-row site itself, not only in the backfill. If you can make it a **test** rather than
   a comment, do that instead and say so — a guard beats a note, and this project's whole failure
   register is comments that did not hold.
5. **Fix the `def110_backfill.py:184-190` docstring**, which misdescribes the exit-2-with-partial-write
   case (the row's adjacent finding).
6. **Mutation:** revert the P&L stamp fix at each site in turn and show the corresponding test goes
   RED. Report honestly, **including any that come back GREEN**.
7. Full suite from repo root: `"./backend/.venv/bin/python" -m pytest backend/tests/unit/ -q`.
   **`python` is not on PATH. Never use `-x`.** Baseline **1719**; finish `>= 1719`, zero failures.
   **Do not pipe pytest through `tail`/`head` and read the exit code** — you get the pipe's exit
   code, not pytest's. Read the `N passed, M failed` line.

## Registers

Flip `docs/defect/_registry/DEF166.row.md` to `fixed` only if you closed it fully, then
`python3 scripts/registers/gen_registers.py gen def`, and commit the row file and the regenerated
table **in the same commit** (DEF159). **Explicit pathspec — never `git add -A`, never bare commit.**

## Hand-off delivery

**Write your hand-off file EARLY and keep updating it** — a budget cap that kills you mid-lane with
the hand-off unwritten is the worst place to stop.

Write `orchestration/dispatch/lanes/SIM-DEF166.coder.api.md` with `STATUS: READY_FOR_AUDIT (round 1)`;
get it onto `main` AND push your lane branch to origin (**DEF175**).

**No `.architect.md` submit file** — sprint mode, I integrate on my own verification and track U
audits the sprint as one batch afterwards.

**If you can measure that an instruction here is wrong, stop and disclose with the measurement.**
This is money math; a confident wrong answer here is worse than a disclosed gap.

ASSIGNED: coder.api round 1
DISPATCH: OPEN
