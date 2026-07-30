<!-- lane assign — Architect-owned. CR052. -->
# BE-MINOR — three silent-degradation fixes in the compliance surface

KIND: code
INSTANCE: coder.api
GATE: none    <!-- Sprint mode (Saiful, 2026-07-30): lanes integrate on my verification; track U audits the whole sprint as one item at the end. -->
BUDGET: $10
DEPENDS-ON: none

## What and why

Three defects, one shape: **a check that declines to run, or runs on the wrong input, and says
nothing.** That is `CR040` degrade-loudly, and all three sit in the surface whose output the user
reads as a *compliance verdict* — so a silent skip is not a missing log line, it is the app telling
someone their trade passed a check that never happened.

**Read each row file — it carries the measured diagnosis and the intended fix shape:**

```
docs/defect/_registry/DEF165.row.md   sector_allocation.py:224-227 — DEF149's max() fallback re-adopts the exact denominator DEF149 was filed to remove
docs/defect/_registry/DEF169.row.md   safety_floor.py:266 — single-name concentration cap silently skipped when portfolio_value <= 0
docs/defect/_registry/DEF196.row.md   overlay_generator.py — the PM overlay says a limit is BOTH "not set" and "enforced as a hard block", in one sentence
```

**DEF196 is the one to take most seriously despite being a string.** Its reader is an LLM, all five
CR101-BE2 fields default to unset, so *today this is what nearly every user's PM prompt actually
says*. CR038 measured that agents ignore even emphatic instructions ~70% of the time; a
**self-contradicting** instruction is strictly worse input than a clear one, and it fails invisibly
— nothing goes red, the deterministic floor still behaves, and the only symptom is a PM arguing
from a mandate it was told two incompatible things about.

**DEF165 and DEF169 share a trap:** in both, the existing test covers the *branch* but not the
*field*, so the defective path is green. DEF165's test pins `weight <= 1.0`, which the broken
denominator also satisfies. Your new test must assert **which denominator / which code path was
taken**, not merely that the output is in range. A test that cannot distinguish the fallback from
the fix is the reason these shipped.

## Fences

- **Do NOT touch `backend/app/api/mandate.py`, `backend/app/services/mandate_store.py`,
  `backend/app/api/one_on_one.py`, `backend/app/services/brief_engine.py` or
  `backend/app/schemas/mandate.py`** — lane `BE-MANDATE` is live in a parallel worktree and owns them.
- **Do NOT touch `backend/app/services/sim_engine.py`** — lane `SIM-DEF166` owns it.
- **Do NOT touch `backend/app/services/room_runner.py`** — lane `ROOM-MINOR` owns it.
- **Do NOT touch `mobile/`.**
- **Do NOT touch `DEF182` / `SECRET_KEY` usage, and do not edit `infra/alpha.env`.**
- DEF196 touches agent-facing copy: use the **interpolate-the-constant** discipline already
  documented at `safety_floor.py:30-35`. No hand-edited numeric literals in agent copy (CR105 item 2).

## Acceptance

1. **Each of the three is proven by a test that FAILS against current code.** Write the test first,
   watch it go red, then fix.
2. **DEF165:** the new test asserts *which* denominator was used. Additionally decide and state in
   your hand-off whether a stale `portfolio_value` is common enough that the staleness itself wants
   its own row — the DEF165 row explicitly invites that judgement. Do not file the row yourself; say
   so in the hand-off and I will mint the ID.
3. **DEF169:** the compliance result for a skipped cap must read **not-evaluated**, not passed. A
   log line alone does not satisfy this — the absence has to be visible in the verdict object that
   the caller receives, so a reader cannot confuse "checked and clear" with "could not check".
4. **DEF196:** the "not set" state and the "enforced as a hard block" mechanism sentence are never
   emitted together. Prove it with a table-driven test over all seven fields × {set, unset}.
   Also add the one documentation line the row asks for: `0` binds as "block everything" on six of
   the seven fields but is a **no-op on `post_loss_cooldown_hours`** (a zero-hour wait).
5. **Mutations:** revert each of your three fixes in turn and show the corresponding test goes RED.
   Report honestly, **including any that come back GREEN** — a green mutation means the test does
   not pin the fix and the lane is not done.
6. Full suite from repo root: `"./backend/.venv/bin/python" -m pytest backend/tests/unit/ -q`.
   **`python` is not on PATH. Never use `-x`.** Baseline is **1743**; finish `>= 1743` with zero
   failures. **Do not pipe the run through `tail`/`head` and read the exit code — you get the
   pipe's exit code, not pytest's.** Read the `N passed, M failed` line.

## Registers

Flip each row you actually closed to `fixed` in its own `docs/defect/_registry/DEF###.row.md`, then
`python3 scripts/registers/gen_registers.py gen def`, and commit the row files and the regenerated
table **in the same commit** (DEF159). Leave any you did not close `open`, and say why.
**Commit with an explicit pathspec — never `git add -A`, never bare `git commit`.**

## Hand-off delivery

**Write your hand-off file EARLY and keep updating it** — a budget cap that kills you mid-lane with
the hand-off unwritten is the worst place to stop, and it has already happened twice on this project.

Write `orchestration/dispatch/lanes/BE-MINOR.coder.api.md` with `STATUS: READY_FOR_AUDIT (round 1)`;
get it onto `main` AND push your lane branch to origin (**DEF175** — a finished lane and an
invisible lane look identical from `main`).

**No `.architect.md` submit file for this lane** — sprint mode, I integrate on my own verification
and track U audits the sprint as one batch afterwards.

**If you can measure that an instruction here is wrong, stop and disclose with the measurement.**
That is the standard here and it has been the right call every time it has happened.

ASSIGNED: coder.api round 1
DISPATCH: ACCEPTED
