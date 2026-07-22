<!-- dispatch assign lane — Architect-owned. CR052. -->
# DEF084-ROOM — assign

KIND: code
INSTANCE: coder.room
ACCEPTANCE: docs/defect/DEF084_halal_flag_is_an_allowlist_not_a_screen/DEF084_halal_flag_is_an_allowlist_not_a_screen.md — Option 2 (Saiful decided 2026-07-22)
DEPENDS-ON: DEF084-BE (`bd5c74d`, branch `coder.api-DEF084`) — mirror its wording exactly
HOT-FILES: backend/app/agents/overlay_generator.py (room cluster — yours)

**Found by DEF084-BE's builder and confirmed independently by the Architect.** DEF084-BE relabelled
the *deterministic* halal path honestly, but the **agent-narration layer still asserts a screen**:

- `overlay_generator.py:88` — `"- HALAL / Sharia screen REQUIRED. Exclude interest-based banking, …"`
- `overlay_generator.py:157` — `"- Apply Sharia screen on every candidate (see compliance block above)."`
- `overlay_generator.py:300` — `"- Instrument must pass Sharia screen."`

These go into Room agent prompts, so the agents narrate a screen to the user that **no code
computes**. Half-relabelling is arguably worse than not relabelling: the deterministic rejection
now says "curated demonstration universe" while the agents keep saying "Sharia screen", so the two
surfaces contradict each other.

**What:** bring this narration in line with DEF084-BE's wording — the `halal` flag restricts
candidates to a curated demonstration universe; it is not a Sharia screen and no ratio is computed.

**Do NOT touch the ratio thresholds.** `trading_math/screening.py` defaults to 33/33/5, which
DEF084 identifies as the **wrong standard** (AAOIFI SS 21 is 30/30/5). That correction is a
religious-standards question reserved for Saiful/an SME — it is NOT in this lane and must not be
"fixed in passing". You are changing *claims about what the software does*, nothing else.

**Guard:** `backend/tests/unit/test_def084_halal_flag_copy_guard.py` (from DEF084-BE) binds the
deterministic copy. Extend the same principle to the narration surface so a future prompt edit
cannot silently re-assert a screen — and verify your extension RED before you fix, pasting the
failing output into your lane file.

**Scope:** room cluster only. Do not touch `backend/app/services/sim_engine.py`,
`safety_floor.py`, `content/**` or `mobile/**`.

ASSIGNED: coder.room round 1
DISPATCH: OPEN

DISPATCH: ACCEPTED (round 1)
