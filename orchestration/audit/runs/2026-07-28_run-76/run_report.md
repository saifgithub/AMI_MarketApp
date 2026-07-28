# Audit run — 2026-07-28 run-76

**Item:** DEF120 round 4 · **SHA** `f9e0ca5` (`lane/DEF120.coder.api`) · **Verdict:** COMPLETE · **BLOCKER 0 · MAJOR 0 · MINOR 2**

Worktree `.claude/worktrees/audit-DEF120-r4` (`git worktree add --detach`), venv symlinked, reaped after.

## Queue note — this lane waited 7h45m for a dead watcher

The background watcher died at **00:11** with the previous process teardown, printing its startup
line and nothing else — no lane, no exit-3 timeout. DEF120 r4 was submitted at **02:07** and
CR098-MOBILE-LIVE at **02:11**; neither was picked up until 09:52. `watcher.sh state` reported both
correctly the whole time, so **the cross-check on wake is what catches this, not the watcher itself**.
Recorded because my own checkpoint memo said "queue is EMPTY", which was true when written and wrong
two hours later.

## Order of operations

1. Scope diff `5db1815..f9e0ca5` — **10 files, +665/−82**; round 4's own delta `0a64e7e..f9e0ca5` is
   **one test file, +80/−9**. Test-file-only, as claimed.
2. Full suite **1404 passed / 190.82s**, `__pycache__` cleared, **run to completion before any mutation**.
3. `+6` verified by a different method than the lane's: `^def test_` counts on `main` vs the lane,
   `3 → 5` and `0 → 4`.
4. Probe battery, 10 probes — Q1, Q3, Q3-off, Q3-off-B, Q10, Q11, Q-CTL, Q-CTL2, Q13, Q13b, Q14.
   Each mutation verified present in source, reverted after, `__pycache__` cleared between steps,
   `dirty=0` at the end.
5. Q15 — dumped the empty-waiver walk from the module and compared it to the pinned set.
6. Checked the decorator-detection surface for route forms the guard would miss (`websocket`,
   `add_api_route`): **0 live instances**, so no gap.

## Provenance — why this round is thinner than it looks

Round 4 had **no independent worker**. I designed and measured the fix in round 3; the Architect
implemented it and disclosed that, asking me to re-derive rather than confirm. Six of the ten probes
are new. But I cannot be independent of a fix I specified, and the verdict says so.

## Results

| Probe | | Result |
|---|---|---|
| Baseline, both DEF120 test files | | 9 passed |
| **Q1** | direct `sim.current_marks()` in an async route — verbatim pre-DEF120 | **RED** (3) |
| **Q3** | same call via a module-level sync helper — **my round-3 MAJOR** | **RED** (2) |
| **Q3-off** | Q3 + round-4 union disabled | 1 failed — the **pin** test, stale-set, not Q3 |
| **Q3-off-B** | Q3 + union disabled **and** pin set emptied | **5 passed** — causation proved |
| **Q10** ⁿᵉʷ | helper in a different module | **RED** (2) |
| **Q11** ⁿᵉʷ | helper as a class method | **RED** (2) |
| **Q-CTL** | correct `to_thread(sim.current_marks, …)` | **GREEN** |
| **Q-CTL2** ⁿᵉʷ | `to_thread(lambda: sim.current_marks(…))` | **RED** (3) — **MINOR 1** |
| **Q13** ⁿᵉʷ | wrap `_build_sim_holdings_block` | **RED** — shrink assertion fires |
| **Q13b** ⁿᵉʷ | wrap `_build_room_sector_context` instead | **GREEN** — recorded, not scored |
| **Q14** ⁿᵉʷ | new blocking leaf inside the **waived** chain | **RED** — round-1 fail-open shut |
| **Q15** ⁿᵉʷ | empty-waiver walk vs pinned set | **3 pairs, equal exactly**; 6 full chains traced |

## Findings

- **MINOR 1** — `to_thread(lambda: …)` is flagged identically to a raw blocking call. Fail-closed,
  **0** live instances in `backend/app/`. Matters only via the second-order path: silencing a false
  positive with a waiver entry *would* be fail-open.
- **MINOR 2** — all six `room_runner.py` line numbers cited in the round-4 comment are stale by ~+89
  (`:1906 → :1995`, `:1912 → :2001`, `:1748 → :1837`, `:1687 → :1778`, `:574 → :663`, `:583 → :672`).
  DEF124 landed in that file in the merge **immediately preceding** the commit that wrote them. No
  assertion depends on a line number, but these numbers are being carried into the Room queue's assign.

## Deviation from the round-3 prescription: accepted

`_route_walk_leaf_method_names()` returning the union, instead of the `|=` I specified, is
behaviourally identical for the walk and avoids collapsing the two declaration buckets D9's failure
message names. Better than what I asked for.

## Not verified

Load, promotion, and the item's real acceptance. **Two un-`to_thread`'d calls still block the loop on
every Room convene** (`room_runner.py:1995` and `:2001`); DEF116 + DEF120 do not close the MVP
show-stopper. Q4 (bound-method alias) remains out of reach by design and was not re-opened.
