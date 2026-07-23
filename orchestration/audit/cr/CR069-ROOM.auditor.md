<!--
CR069-ROOM.auditor.md — auditor lane file (track U owns). State derives from round numbers
here vs CR069-ROOM.architect.md (see PROTOCOL.md).
-->

# CR069-ROOM — audit lane (auditor)

**Item:** CR069-ROOM — render the sourced `ShariaVerdict` (CR069-BE) into the 12 agents'
overlays, replacing DEF084's "curated demonstration universe" narration. Chunk under the CR069
decomposition (chunk evidence list, not the CR-level DoD — the terminal `CR069` lane isn't
dispatched yet).

**Audited SHAs:** `57f2c0f` → `08b0574` → `eed49ef`, tip of `lane/CR069-ROOM.coder.room` (not on
main). Audited in an isolated worktree `.claude/worktrees/audit-CR069-ROOM/` (separate from the
coder's own `coder.room-CR069-ROOM` worktree already present in the shared tree — never trust the
live one).

## Round 1

### Reproduced independently

| Check | Command | Result |
|---|---|---|
| Self-test subset | `uv run pytest tests/unit/ -q -k "overlay or room_runner or sharia or halal or room_prompt or agent_prompt"` | **242 passed, 794 deselected** (`uv sync --extra dev` first — fresh-worktree fallback). Matches. |
| Full backend suite | `uv run pytest tests/unit/ -q` | **1036 passed, 2 warnings** (129.79s). Matches exactly. |
| Guard red-before-fix — **my own revert, not the lane doc's** | `git checkout 9dcc750 -- app/agents/overlay_generator.py` (working tree only, other 4 files left at `eed49ef`), then `pytest tests/unit/test_def084_overlay_narration_copy_guard.py -q` | **67 failed** — matches the lane doc's claim exactly. Restored (`git checkout eed49ef -- app/agents/overlay_generator.py`), reran: **67 passed**. Non-vacuous. |

### Source re-read (file:line, not from the lane doc's prose)

- `app/agents/overlay_generator.py` — `_halal_narration()` (lines ~150-190): duck-types via
  `getattr(halal_universe, "resolve", None)`; a bare `set`/`None` has no `.resolve` → degrades
  loudly ("NOT attached", "could not be confirmed") rather than raising or silently omitting the
  constraint. `stale=True` short-circuits to the PAUSED line before any per-ticker text. Otherwise
  renders provenance (`standard`/`source`/`as_of`) + the fixed three-state explainer, and — only
  `if ticker:` — appends `probe.message()` verbatim. Confirmed the `resolve(ticker or "")` call
  used purely to read provenance when `ticker is None` (the 1-on-1 path) is safe: it returns an
  UNKNOWN-status verdict for the empty string, but only `.standard/.source/.as_of` off it are
  used — `.status`/`.message()` are never read in that branch.
- `_compliance_block()`: `_halal_narration` is only invoked `if c.halal` — a non-halal mandate
  never sees the block, confirmed by `test_non_halal_mandate_gets_no_sharia_narration`.
- `app/schemas/sharia.py` `ShariaVerdict.message()` — read the three PASS/SCREENED_OUT/UNKNOWN
  branches directly; the guard's `test_per_ticker_line_is_byte_identical_to_the_sourced_verdict`
  asserts `_UNIVERSE.resolve(ticker).message()` (called from the test itself, not the overlay) is
  a substring of the rendered overlay for AAPL/XOM/ZZZZ — this is the real anti-drift structural
  assertion the lane doc claims, not a phrase check. Re-read the test body, not just its name.
- Wiring (`08b0574`), read at file:line rather than trusted from the commit message:
  - `agent_prompts.py:build_agent_prompt` — new `halal_universe`/`ticker` kwargs, passed straight
    into `generate_overlay`. Signature-additive (new kwargs default `None`), no existing caller
    broken — confirmed by the 1036/1036 full suite.
  - `room_prompts.py:build_room_messages` — new `halal_universe` kwarg threaded into
    `build_agent_prompt(..., halal_universe=halal_universe, ticker=ticker)`; `ticker` was already
    a required param on this function (pre-existing), correctly reused rather than duplicated.
  - `room_runner.py:1664` (`_speak_one_agent`) and `:1754` (`_stream_pm_response`) — both pass
    `halal_universe=ctx.halal_universe`. Traced `ctx.halal_universe`'s origin to line 1294/1318:
    `halal = halal_universe or await default_halal_universe_async()` → `_RoomContext(...,
    halal_universe=halal, ...)` — the **same** resolved object `_assemble_verdict` (line 627)
    feeds into `check_mandate_compliance` for enforcement. Narration and enforcement read one
    object, not two independently-fetched ones that could drift.
  - `agent_runner.py` (1-on-1 path) — gates the fetch on `mandate.compliance.halal` (no needless
    network call for non-halal mandates), `await default_halal_universe_async()` (the offloaded
    accessor CR069-BE round 3 added — no new sync-blocking call introduced here). Passes
    `halal_universe=` but no `ticker=` — confirmed intentional: `build_agent_prompt`'s `ticker`
    param stays `None` on this path since none is known at prompt-build time, and
    `_halal_narration` correctly omits the per-ticker line only (`if ticker:` gate), still
    rendering provenance + the three-state rules.
- Scope discipline — `git show --name-only` on all 3 commits: `57f2c0f` → 1 file
  (`overlay_generator.py`); `08b0574` → 4 files (`agent_prompts.py`, `agent_runner.py`,
  `room_prompts.py`, `room_runner.py`); `eed49ef` → 1 file (the guard test). Exactly 5 distinct
  files, all coder.room-owned per the assign. `sharia_universe.py` and `safety_floor.py`: zero
  hits — CR069-BE's HOT-FILES genuinely untouched.
- Constraint 4 (`sharia_screen()` stays dormant) — `grep -rn "sharia_screen(" app/` outside its
  own definition/module: only 2 comment references (`safety_floor.py:117,147`), zero live calls.
  Holds.
- "AMI by name, never 'the AI'" — `grep -n "the AI\b" app/agents/overlay_generator.py` → no hits.

### Guard quality — read the test file, not just run it

`test_def084_overlay_narration_copy_guard.py` (240 lines): retired-mechanism blocklist (4
phrases) + ratio-phrase blocklist (6 phrases) + a **numeric anti-evasion regex** matching any
`\d+%|percent` inside the scoped HALAL block (catches a reworded threshold the phrase lists would
miss) + the byte-identity assertion + per-state assertions (unknown reads as no-ruling and never
as a pass; screened-out reads as a real exclusion; paused degrades loudly; missing-universe
degrades loudly; non-halal gets nothing) — most parametrized across all 12
`TWELVE_AGENT_IDS`. Confirmed non-vacuous via the revert-proof above (67/67 fail without the
fix, on genuinely the guard file, not a collection error).

### Findings

Zero BLOCKER, zero MAJOR, zero MINOR.

**OUT-OF-SCOPE (informational, pre-existing, not this lane's doing).** `room_runner.py:239`
`_RoomContext.halal_universe: set[str]` — the dataclass field's type annotation predates both
CR069-BE and this lane (untouched by either diff) and is stale (the runtime object is a
`HalalUniverse`, a `frozenset` subclass with extra attributes, not a bare `set`). Cosmetic only —
Python dataclasses don't enforce field types at runtime, and every call site duck-types correctly
regardless of the hint. Not minting a DEF — too trivial to be worth one; noting per gap-fill so
whoever next touches this dataclass can tidy it in passing.

**Disclosed-not-verified, correctly left open, not re-litigated here:** CR069 §Acceptance 4's live
`llm_audit` smoke test (needs a promotion — Mac is a pure editor, per CLAUDE.md) and "whether an
LLM actually obeys the unknown-state instruction" (CR038: prompt instructions are not controls;
the structural control is CR069-BE's `is_blocking`, which this lane correctly does not touch —
this lane is narration, audited as narration).

### Verdict

Every claim in the architect's hand-off independently reproduced: test counts (242/242, 1036/1036),
the guard's red-before-fix (67/67, my own revert not theirs), scope (5 files, exact match, HOT-FILES
respected), the byte-identity structural assertion (read the test body, confirmed real), the shared
enforcement/narration object (traced `ctx.halal_universe` to one origin, not assumed from the
comment), and the G3 unknown-permits-not-blocks posture in the narration text itself.

**VERDICT: COMPLETE (round 1)**

Run report: [`../runs/2026-07-23_run-38/run_report.md`](../runs/2026-07-23_run-38/run_report.md)
