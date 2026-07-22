<!-- coder lane — coder.room-owned. DEF084-ROOM. -->
# DEF084-ROOM — coder.room

STATUS: READY_FOR_AUDIT (round 1)

ACCEPTANCE: docs/defect/DEF084_halal_flag_is_an_allowlist_not_a_screen/DEF084_halal_flag_is_an_allowlist_not_a_screen.md — Option 2
DEPENDS-ON: DEF084-BE (`bd5c74d`, MERGED to main) — mirrored its wording exactly
HOT-FILES: backend/app/agents/overlay_generator.py (room cluster — mine)

## What / why
DEF084-BE relabelled the *deterministic* halal path honestly (safety_floor, sim_engine)
but the **agent-narration layer** in `overlay_generator.py` still asserted a Sharia *screen*
at lines 88, 157, 300 — a screen no code computes. The two surfaces contradicted: the
deterministic rejection now says "curated demonstration universe" while agent prompts kept
saying "Sharia screen" (line 88 even narrated ≤33% D/E, ≤5% interest-income ratio cutoffs
that nothing checks). This lane brings the narration in line with BE's exact wording:
"curated demonstration universe", "not a Sharia screen", "no ratio is computed".

## Changes (owned paths only)
- `backend/app/agents/overlay_generator.py`
  - `_compliance_block` (was line 88): halal flag no longer says "HALAL / Sharia screen
    REQUIRED … Check debt-to-equity ≤33%, interest income ≤5%". Now: "only advocate names
    within AMI's curated demonstration universe (a fixed allowlist). This is NOT a Sharia
    screen and no ratio is computed — do not tell the user a screen was run or a ratio was
    checked."
  - `_fundamentals_block` (was line 157): "Apply Sharia screen on every candidate" →
    "restrict candidates to AMI's curated demonstration universe (a fixed allowlist; NOT a
    Sharia screen — no ratio is computed)."
  - `_trader_block` (was line 300): "Instrument must pass Sharia screen." → "Instrument
    must be within AMI's curated demonstration universe (a fixed allowlist; NOT a Sharia
    screen — no ratio is computed)."
  - Removed the now-dead narration constants `_HALAL_MAX_DEBT_TO_EQUITY_PCT` /
    `_HALAL_MAX_INTEREST_INCOME_PCT` (they only fed the false ratio narration) and rewrote
    the comment block. `_MICROCAP_FLOOR_USD_M` (liquidity, a separate concern) untouched.
- `backend/tests/unit/test_def084_overlay_narration_copy_guard.py` (NEW guard — my test space)
  - Companion to DEF084-BE's copy guard; binds the *narration* surface across all 12 agents.

## BOUNDARY respected
- `trading_math/screening.py` NOT touched (0 lines). No 33/33/5 → 30/30/5 change — that
  standards ruling is reserved for Saiful/SME and is explicitly out of this lane.
- Scope: room cluster only. sim_engine.py / safety_floor.py / content/** / mobile/** untouched.

## Guard verified RED before fix
`pytest tests/unit/test_def084_overlay_narration_copy_guard.py -q` on unfixed code:
```
FFF
E   AssertionError: AgentId.FUNDAMENTALS_ANALYST overlay claims a computed screen ['sharia screen'] but the halal flag is enforced by a curated demonstration universe (DEF084)...
E   AssertionError: AgentId.FUNDAMENTALS_ANALYST overlay narrates a ratio cutoff ['debt-to-equity', 'interest income'] for the halal flag, but no ratio is computed (DEF084)...
E   AssertionError: halal overlay must name the curated demonstration universe (DEF084)
3 failed in 0.55s
```

## Tests GREEN after fix
- New guard + BE guard: `5 passed`
- Affected suite (overlay_generator, room_runner, safety_floor, mandate_audit, sim_engine): `138 passed`
- Full backend unit gate: `pytest tests/unit/ -q` → `944 passed, 1 warning in 115.43s`
