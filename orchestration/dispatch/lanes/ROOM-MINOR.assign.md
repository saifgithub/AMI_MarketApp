<!-- lane assign — Architect-owned. CR052. -->
# ROOM-MINOR — a crash and a cosmetic strip bug, both in room_runner

KIND: code
INSTANCE: coder.room
GATE: none    <!-- Sprint mode (Saiful, 2026-07-30): lanes integrate on my verification; track U audits the whole sprint as one item at the end. -->
BUDGET: $6
DEPENDS-ON: none

## What and why

Two small, independent defects in `backend/app/services/room_runner.py`. Batched only because they
share a file — they share no logic.

```
docs/defect/_registry/DEF172.row.md   room_runner.py:877 — round(entry * 0.94) raises TypeError and kills the turn when both entry sources are None
docs/defect/_registry/DEF163.row.md   room_runner.py:1516 — _clip_summary strips in the wrong order, leaving " …" when punctuation precedes a space
```

**DEF172 is the real one.** `entry` resolves at :870 from `entry_raw` falling back to
`ctx.trader_entry`; when both are absent the multiply is `None * float` and the exception propagates
out of the agent turn. A crash in the Room runner is a **user-visible dead convene**, not a missing
field. The honest output is the absence of the level — and per **CR040** the absence must be
*visible*, not a stack trace and not a silently omitted key that reads as "no signal".

**DEF163 is one token**, but read why it survived: the existing guard test's single fixture has a
cut point with no punctuation-then-space, so it cannot trigger the bug. `cut.rstrip().rstrip(',;:')`
strips the space first, so a cut landing on `"… ,"` has the punctuation removed and the space it was
hiding exposed. The fix is `.rstrip(',;:').rstrip()`. **The missing fixture is the actual defect** —
a shipped guard that could not catch a one-token bug.

## Fences

- **`backend/app/services/room_runner.py` is yours. Nothing else in `backend/app/` is.**
  Three other backend lanes are live in parallel worktrees: `BE-MINOR` owns
  `sector_allocation.py` / `safety_floor.py` / `overlay_generator.py`, `BE-MANDATE` owns
  `api/mandate.py` / `mandate_store.py` / `one_on_one.py` / `brief_engine.py`, and `SIM-DEF166`
  owns `sim_engine.py`. Do not edit any of them.
- **Do NOT touch `mobile/`.**
- **Do not restructure the runner.** Both fixes are local; this is not a refactor lane.

## Acceptance

1. **Both are proven by a test that FAILS against current code.** Write it first, watch it go red.
2. **DEF172: the turn survives.** A test convening with `entry_raw` and `ctx.trader_entry` both
   `None` must complete rather than raise, and the derived level must be **visibly absent** in the
   output — not silently dropped in a way a reader would mistake for "no level applies". State in
   your hand-off which shape you chose and why.
3. **DEF172: check the siblings.** The row asks you to check the surrounding block for other
   derivations off `entry` with the same unguarded shape. Report what you find **even if you fix
   nothing** — if there are more, I want them named, not quietly patched or quietly skipped.
4. **DEF163: the new fixture's cut point lands on punctuation-preceded-by-space.** Verify it fails
   before the fix — a fixture that passes both ways adds nothing and repeats the original mistake.
   `('ab , cd ' * 40)` is the row's own reproduction; use it or something equivalent you have
   actually watched go red.
5. **Mutations:** revert each fix in turn, show the corresponding test goes RED. Report honestly,
   **including any that come back GREEN**.
6. Full suite from repo root: `"./backend/.venv/bin/python" -m pytest backend/tests/unit/ -q`.
   **`python` is not on PATH. Never use `-x`.** Baseline **1743**; finish `>= 1743`, zero failures.
   **Do not pipe pytest through `tail`/`head` and read the exit code** — that gives you the pipe's
   exit code, not pytest's. Read the `N passed, M failed` line.

## Registers

Flip each row you closed to `fixed` in its own `docs/defect/_registry/DEF###.row.md`, then
`python3 scripts/registers/gen_registers.py gen def`, and commit the row files and the regenerated
table **in the same commit** (DEF159). **Explicit pathspec — never `git add -A`, never bare commit.**

## Hand-off delivery

**Write your hand-off file EARLY and keep updating it** — a budget cap that kills you mid-lane with
the hand-off unwritten is the worst place to stop.

Write `orchestration/dispatch/lanes/ROOM-MINOR.coder.room.md` with `STATUS: READY_FOR_AUDIT (round 1)`;
get it onto `main` AND push your lane branch to origin (**DEF175**).

**No `.architect.md` submit file** — sprint mode, I integrate on my own verification and track U
audits the sprint as one batch afterwards.

**If you can measure that an instruction here is wrong, stop and disclose with the measurement.**

ASSIGNED: coder.room round 1
DISPATCH: ACCEPTED
