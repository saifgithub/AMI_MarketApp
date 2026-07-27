<!--
Auditor run report — run-73 (2026-07-27, session auditor.core/track U). Round-2
audit of DEF120. Audited SHA 93c6b84. Verdict AWAITING_FIXES — one MAJOR
(reproduced with the verbatim pre-DEF120 shape). Owner: AUDITOR.
-->

# run-73 (round 2) — DEF120 portfolio/trade blocking I/O → AWAITING_FIXES

- **Auditor session:** auditor.core (track U), 2026-07-27.
- Round 1 (`cec80c9`) was AWAITING_FIXES with one MAJOR — see run-71.

**Audited SHA:** `93c6b84` (round 1 was `cec80c9`). **Scope: one test file, +141/−0** — no production
code, confirmed by pathspec. Isolated worktree `.claude/worktrees/audit-DEF120-r2/`, own venv.
**Full suite 1371 passed** in 215s on a clean tree, run to completion before any mutation (round 1
was 1370; +1 = D9).

### D9 is the right mechanism, and it closes my round-1 finding

`_referenced_attrs` collects every `ast.Attribute` **referenced or called**, so a leaf handed to
`pool.map` by reference is as visible as one invoked directly — that is precisely the edge the
round-1 walker lacked. `_reaches_network` then recurses `SimEngine`'s own methods from
`self._provider.<quote|history|news|earnings>`, and anything reaching it must appear in
`_BLOCKING_LEAF_METHOD_NAMES` or `_SIM_ENGINE_SYNC_SAFE_METHODS`. Undeclared fails red.

| Probe | Result |
|---|---|
| **P1 — my round-1 mutation**: new undeclared method `audit_probe_snapshot` reaching the network via `_marks_with_quotes`, called directly from `sector_allocation` | **RED** — round-1 MAJOR closed |
| **P3 — a shape nobody tested**: a new method reaching the network *not* via `self._provider.<verb>` (`yf.Ticker(ticker).info` directly, bypassing the provider abstraction) | **RED** (2 tests) — the yfinance leaf detection covers this flank |

Both mutations verified present in source before running, each reverted, tree clean after.

### MAJOR — the sync-safe declaration is an unasserted human claim, and a straight revert of this lane's own fix goes green

`_SIM_ENGINE_SYNC_SAFE_METHODS` carries its membership condition in a comment: *"none of these is
ever called directly from an `async def` route today (**checked by grep** over
`backend/app/api/*.py` … outside a `to_thread` wrapper)."* That check ran once, by hand, at
authoring time. Nothing asserts it, so nothing notices when it stops being true.

Two probes, escalating:

| Probe | Result |
|---|---|
| **P2** — declared-sync-safe `_marks_with_quotes` called directly from async `sector_allocation` | **8 passed, GREEN** |
| **P4** — `marks = sim.current_marks(["AAPL"])` in async `sector_allocation` — **the verbatim pre-DEF120 shape** | **8 passed, GREEN** |

P4 is the one that matters. That line is not a hypothetical new shape: it is the **original bug**,
the code that was in `sim.py:126` / `mandate.py:265` / `portfolio.py:66` until this lane removed it,
and it parks the event loop for the full fan-out because `pool.map` blocks until complete. Both
guards miss it:

- **D9** is satisfied — `current_marks` and `_marks_with_quotes` are *both* declared sync-safe.
- **The main call-graph walk** is blind — `pool.map(self.current_quote, unique)` passes the leaf by
  reference, exactly the edge D9 exists to compensate for, but D9 only asks *"is this method
  declared?"*, never *"is the declaration still true?"*

So a merge accident, a bad rebase, or a well-meaning refactor that reinstates the pre-DEF120 call
produces **zero red**, on the hottest routes in the app, in the lane whose entire purpose is to
prevent it.

**I under-specified this in round 1 and I own that.** My recommendation was to *"assert every public
`SimEngine` method that transitively reaches `_marks_with_quotes`/`current_quote` is either in the
leaf set or on an explicit exclusion list."* The lane implemented exactly that, faithfully. The flaw
is mine: an exclusion list whose membership condition is unasserted is only as strong as the grep
behind it — the same "a claim in a comment is not a control" shape as DEF116's original waiver prose,
which this project has now hit repeatedly.

**Fix — assert the claim instead of commenting it.** For each name in
`_SIM_ENGINE_SYNC_SAFE_METHODS`, walk `backend/app/api/*.py` and fail if any `async def` route
contains a direct `<obj>.<name>(...)` call that is not the first positional argument of an
`asyncio.to_thread(...)`. That is a local AST check over one directory, roughly fifteen lines, and it
converts the frozen human grep into an enforced invariant. It also composes with D9 rather than
duplicating it: D9 governs *what exists*, this governs *how it is called*.

### Unchanged from round 1, and still true

- `_WAIVED_CALL_CHAIN_NAMES` is still exactly `{"_build_room_sector_context"}`, and the empty pin set
  remains a **blind spot, not a clean bill** — the Room's sector-context build is still on the event
  loop at `room_runner.py:1912`. **DEF116 + DEF120 together still do not fully close the MVP
  show-stopper**; that remainder belongs to the CR104 → DEF124 → DEF125 Room queue. The lane states
  this plainly and I confirm it.
- Round 1's accepted work stands: the fan-out primitive, the thread-hop safety, D2/D5/D7.

### Process note — worth recording for Governance

The assign **split the verification structurally**: the worker got only the ~3-second targeted tests,
the Architect took the 193-second full suite. After two CR104 workers died backgrounding a long run
and ending their turn (CR057 / P7) — the second *after being explicitly told not to* — this worker
complied fully, wrote its hand-off to the file, and reported plainly that it had not run the full
suite because that was not its job. **Removing the long-running command from the worker's hands
removed the trap.** That is a structural remedy where three rounds of instruction failed, which is
the correct reading of CR038.

### Not verified

- **Concurrency under real load** — nothing exercised against a running server; Mac is a pure editor,
  `main` under a promotion hold. Unchanged from round 1.

### Findings

1. **MAJOR** — `_SIM_ENGINE_SYNC_SAFE_METHODS` membership is an unasserted human claim. A route
   calling a declared-sync-safe method directly is invisible to both guards — proved with the
   verbatim pre-DEF120 shape (`sim.current_marks(...)` from async `sector_allocation` → 8 passed).
   A straight revert of this lane's own fix would ship green. Fix: assert the claim (~15 lines).

### Verdict

**VERDICT: AWAITING_FIXES (round 2)** — one MAJOR.

D9 is genuinely the right mechanism and it closed what I found in round 1: reference-edges make the
by-reference fan-out visible, deny-by-default removes the allowlist, and it fires on a method merely
*existing* undeclared — a stronger property than reachability. My P1 and P3 both go red.

What remains is the other half of the same question. D9 governs which methods may exist; nothing
governs how the declared-safe ones are called, and that gap admits the original bug verbatim. The
fix is small and I have specified it precisely, including the part I got wrong the first time.

