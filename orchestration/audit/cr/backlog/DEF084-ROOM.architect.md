<!-- audit hand-off — coder.room → auditor.core. DEF084-ROOM. -->
# DEF084-ROOM — audit hand-off

SUBMITTED: round 1
SHA: cef212f (branch `coder.room-DEF084-ROOM`, pushed to origin)
DEPENDS-ON: DEF084-BE (`bd5c74d`, MERGED to main)
ACCEPTANCE: docs/defect/DEF084_halal_flag_is_an_allowlist_not_a_screen/ — Option 2 (Saiful, 2026-07-22)

## What / why
DEF084-BE told the truth on the *deterministic* halal path but the *agent-narration*
layer (`overlay_generator.py`) still asserted a Sharia **screen** at three sites, so the
two surfaces contradicted (deterministic: "curated demonstration universe"; agents:
"Sharia screen", plus a narrated ≤33% D/E, ≤5% interest-income ratio that nothing checks).
This lane relabels the narration to match BE's wording and adds a guard so a future prompt
edit cannot silently re-assert a screen.

## Files changed (all coder.room-owned)
| Path | Change |
|---|---|
| `backend/app/agents/overlay_generator.py` | 3 halal narration sites relabelled; dead `_HALAL_MAX_*` ratio constants removed; comment rewritten. +20 −13 |
| `backend/tests/unit/test_def084_overlay_narration_copy_guard.py` | NEW — narration copy/mechanism guard (3 tests). |
| `orchestration/dispatch/lanes/DEF084-ROOM.coder.room.md` | lane state. |

## Mirrored wording (matches `bd5c74d`)
"curated demonstration universe" · "NOT a Sharia screen" · "no ratio is computed".

## Tests + results
- Extension verified **RED** before the fix (3 failed) — output pasted in the coder lane.
- After fix: new guard + DEF084-BE guard `5 passed`.
- Full backend unit gate `pytest tests/unit/ -q` → **944 passed, 1 warning in 115.43s**.

## Revert-proof QA (independent checks for the auditor)
1. `git show cef212f -- backend/app/trading_math/screening.py` → **empty** (boundary held: no
   33/33/5 → 30/30/5 change; the standards ruling is Saiful/SME-only, out of lane).
2. `git show --name-only cef212f` → only the 3 owned paths above; no sim_engine/safety_floor/
   content/mobile.
3. Grep the fixed module for a re-asserted screen:
   `grep -nE "Sharia screen|debt-to-equity|interest income" backend/app/agents/overlay_generator.py`
   → only inside the honest disclaimer / comment, never as an affirmative claim.
4. Guard is genuinely RED on old copy: `git stash` the fix (or check out `bd5c74d`'s
   overlay_generator) and run the new guard → 3 failures.

## Definition of Done
| Criterion | Status |
|---|---|
| Narration sites 88/157/300 no longer claim a Sharia screen | ✅ |
| Wording mirrors DEF084-BE exactly | ✅ |
| No ratio cutoff narrated on the halal path | ✅ |
| Guard extends the copy-vs-mechanism principle to the narration surface | ✅ (new file) |
| Guard verified RED before fix | ✅ (pasted) |
| Ratio thresholds (33/33/5) untouched | ✅ (screening.py 0 lines) |
| Scope: room cluster only | ✅ |
| Full backend unit gate green | ✅ (944 passed) |
| Committed + pushed to origin | ✅ (cef212f) |
