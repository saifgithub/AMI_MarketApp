<!-- dispatch audit lane — auditor.core owned. CR052. -->
# DEF084-BE — audit

VERDICT: COMPLETE (round 1)

SHA audited: `bd5c74d` (branch `coder.api-DEF084`, hand-off `838cc4f`). DEF084 Option 2 —
relabel the deterministic `halal` path as a curated demonstration universe (NOT a Sharia
screen); no mechanism change.

## Verification against the five required checks

1. **Enforcement behaviour UNCHANGED (Option 2 relabel only) — PASS.**
   The allowlist is the same 7 tickers `{AAPL, MSFT, NVDA, GOOGL, META, TSLA, AMZN}`,
   only the constant name changed (`DEFAULT_HALAL_UNIVERSE` → `DEFAULT_HALAL_DEMO_UNIVERSE`).
   The membership test is byte-identical (`elif t not in {x.upper() for x in halal_universe}`
   in `check_mandate_compliance`; `elif t not in halal_set` in `check_holdings_against_mandate`).
   No ratio is computed on the halal path. Which trades pass/fail is unchanged.

2. **Copy change COMPLETE across the deterministic (this-lane) surface — PASS.**
   Grepped the whole worktree `backend/app` for `sharia|compliance screen|fails Sharia|Apply
   Sharia`. Surviving strings triaged:
   - `safety_floor.py` (111/141/151/234) — all HONEST DISCLAIMERS ("NOT a computed Sharia
     screen", "not a Sharia screen"). Correct, not offending.
   - `screening.py` (1/85) + `trading_math/__init__.py` (120) — the real (unreachable) ratio
     module + its re-export comment; the diff adds a docstring stating it is NOT wired to the
     `halal` flag. Correct.
   - `sim_engine.py` (71) — the new "NOT a Sharia screen — DEF084" header. Correct.
   - **Affirmative "screen ran" claims survive ONLY in `overlay_generator.py`
     (88 / 157 / 300)** — Room agent-prompt narration ("HALAL / Sharia screen REQUIRED …
     debt-to-equity ≤ 33%, interest income ≤ 5%", "Apply Sharia screen on every candidate",
     "Instrument must pass Sharia screen"). This is the builder-flagged KNOWN GAP; see item 5.

3. **`safety_floor.py` signatures byte-stable (frozen surface for coder.room) — PASS.**
   Diffed every `def`/param line of `safety_floor.py`, `sim_engine.py`, `mandate.py` between
   main (`86b0ef1`) and `bd5c74d`: only line-number shifts from added comment/docstring lines;
   the signature text (params, defaults, return types) is identical. No signature drift.

4. **Guard binds copy to mechanism, non-tautological, and RED-verified — PASS.**
   `test_def084_halal_flag_copy_guard.py` calls the real `check_mandate_compliance` and asserts
   the emitted violation copy (a) names "demonstration universe" and (b) does not AFFIRM a
   screen; a second test asserts the mechanism is a literal set and that no `sharia_screen`
   symbol leaked into either enforcement module (trips if Option 1 is wired in). Reproduced RED
   against unmodified main by dropping the guard into the pre-fix tree: BOTH tests fail,
   including the substantive copy assertion —
   `AssertionError: assert 'demonstration universe' in 'ticker nvda fails sharia compliance screen'`.
   Probe file removed, tree left clean.
   **Tried to defeat the negated-disclaimer stripping — could NOT.** The guard `str.replace`s
   the three literal `"not a … screen"` disclaimers, then scans for any surviving claim phrase.
   Any affirmative occurrence of "sharia screen"/"compliance screen"/"sharia compliance screen"
   that is NOT itself part of a "not a …" disclaimer survives the strip and trips the guard
   (verified by reasoning over e.g. `"is a sharia screen, not a sharia screen"` →
   `"is a sharia screen, "` → still offending). There is no way to both make an affirmative
   claim and pass. Guard is sound, not tautological.

5. **KNOWN GAP (`overlay_generator.py` Room narration) — acceptable for THIS lane's scope.**
   The three affirmative claims (and the embedded 33%/5% thresholds) are agent-prompt narration
   for the Room cluster. They are OWNED by the already-open **DEF084-ROOM lane**
   (`orchestration/dispatch/lanes/DEF084-ROOM.assign.md`, INSTANCE coder.room, DEPENDS-ON
   DEF084-BE, HOT-FILE `overlay_generator.py`) with correct scope fences (do NOT touch the
   33/33/5 thresholds — that is a religious-standards question reserved for Saiful/SME).
   Leaving it out of DEF084-BE is correct: BE's HOT-FILES are the deterministic path, and BE
   must NOT touch the room cluster. The gap is not falling through the cracks — it has a
   dedicated lane. **Caveat for the Architect (not a blocker on this lane):** until DEF084-ROOM
   lands, the two surfaces contradict (deterministic copy says "demonstration universe" while
   agents still narrate "Sharia screen"). BE is complete and correct on its own surface; the
   two lanes should land together before this is called "the halal claim is honest everywhere".

## Tests

Targeted run (foreground, worktree `.claude/worktrees/coder.api-DEF084/backend`, main-tree
interpreter):
`test_def084_halal_flag_copy_guard.py test_safety_floor.py test_sim_engine.py
test_mandate_audit.py test_mandate_store.py` → **47 passed, EXIT=0** (a benign pytest
temp-dir `rm_rf` warning only; not a failure).

Full suite NOT run — justified: change is additive/relabel, signatures byte-stable, blast
radius is the deterministic halal copy which the targeted set covers. SUITE_EXIT: n/a
(full suite not required for this blast radius).

Blind-probe (RED reproduction against main): 2 failed as required; probe removed; re-check
of `git status` shows a clean tree (no probe left behind).
