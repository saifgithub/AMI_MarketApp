# Audit run — 2026-07-27 run-74

**Item:** DEF120 round 3 · **SHA** `740119b` (`lane/DEF120.coder.api`) · **Verdict:** AWAITING_FIXES · **BLOCKER 0 · MAJOR 1 · MINOR 0**

Worktree `.claude/worktrees/audit-DEF120-r3` (`git worktree add --detach`), venv symlinked from the
main checkout, reaped after.

## Order of operations

1. Scope diff `93c6b84..740119b` — **one test file +70/−3** + the lane hand-off, no production code.
2. Full suite **1372 passed / 191.81s** on a clean tree, `__pycache__` cleared, **run to completion
   before any mutation**. Round 2 was 1371; +1 = D10.
3. Read the guard internals (`_offending_routes`, `_find_blocking_reachable`, `_blocking_call_sites`,
   `_ModuleInfo`) before writing probes, so the probes targeted the walk's real resolution limits
   rather than guesses.
4. Mutation battery (Q1–Q9), each verified **present in source** before running, reverted after,
   `git status --short backend/app` = 0 at the end.
5. Fix prototype measured on the clean tree **and** with the evasion injected, before recommending it.

## Probe results

| # | Shape | Result |
|---|---|---|
| Q1 | round-2 P4 verbatim — `sim.current_marks(["AAPL"])` direct from async `sector_allocation` | **RED** |
| Q2 | round-2 P2 — `sim._marks_with_quotes([...])` direct | **RED** |
| Q3 | **same call via a module-level sync helper** | **GREEN — the MAJOR** |
| Q4 | bound-method alias `_cm = sim.current_marks; _cm([...])` | GREEN — recorded, **not scored** |
| Q5 | nested `def` inside the async route body | **RED** |
| Q6 | `to_thread(lambda: sim.current_marks([...]))` | RED — fail-closed false positive, 0 live occurrences |
| Q7 | round-2 P1 unwired — new undeclared net-reaching method | **RED** (D9 intact) |
| Q8 | round-2 P3 **unwired** | GREEN — **different probe, not a regression** |
| Q8b | round-2 P3 **verbatim** (method + route wiring) | **2 failed** — identical to round 2 |
| Q9 | colliding name on an unrelated receiver (`sector_map.preview`) | 3 failed — fail-closed, name-based resolution, not a finding |

## Fix prototype (measured before recommending)

`_BLOCKING_LEAF_METHOD_NAMES |= _SIM_ENGINE_SYNC_SAFE_METHODS` inside the reachability walk:

- clean tree → **3** offender pairs, all real, all `room.py:stream_room`
- Q3 injected → **5** pairs; the 2 new ones are on `portfolio.py:sector_allocation`. Caught.
- correctly-wrapped `to_thread(sim.<name>, …)` stays invisible → **zero** false positives elsewhere
- subsumes D10 (Q1/Q2/Q5 stay red through the transitive mechanism)

## Out-of-lane finding (flagged, not scored — D7 scopes `room_runner.py` out)

`room_runner.py:1906` calls `_build_sim_holdings_block(...)` un-`to_thread`'d from inside async
`run()` (`:1748`, awaited on the loop via `_pump`'s `async for` at `:1687`); that builder calls
`sim.total_value` (`:574`) and `sim.current_marks` (`:583`) — the full yfinance fan-out, on every
Room convene. **The lane's disclosure names only `:1912`.** Carry both to DEF124/DEF125.

## Methodology notes

- The Q8 unwired-vs-verbatim distinction is the reason for the "verify the mutation is present, and
  that it is the *same* mutation" rule — an unwired probe going green would have read as a D9
  regression had I not re-run it verbatim.
- Prototyping the recommended fix and measuring both directions (does it catch the evasion / does it
  fire on the clean tree) is a direct response to round 1, where an unmeasured recommendation was
  implemented faithfully and still left the hole open.
