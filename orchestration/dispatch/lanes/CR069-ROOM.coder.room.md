<!-- dispatch lane file — coder.room-owned. Shared-branch coordination state (DEF090). -->
# CR069-ROOM — coder.room

STATUS: READY_FOR_AUDIT (round 1)

ITEM: CR069-ROOM
INSTANCE: coder.room
BRANCH: `lane/CR069-ROOM.coder.room` (pushed — `eed49ef`)
GATE: independent
ACCEPTANCE: docs/forward_planning/CR069_sharia_compliance_indicator/CR069_sharia_compliance_indicator.md (§Acceptance 4, §Design constraints 1–2)
DEPENDS-ON: CR069-BE (merged `bdc410f`) — consumed `HalalUniverse` / `ShariaVerdict`, edited neither.

## What landed

The 12 agents now receive the sourced AAOIFI verdict instead of DEF084's
"curated demonstration universe" text. Three commits:

| SHA | Scope |
|---|---|
| `57f2c0f` | `overlay_generator.py` — the sourced narration + the four states |
| `08b0574` | `agent_prompts` / `room_prompts` / `room_runner` / `agent_runner` — thread the run's `HalalUniverse` to the overlay |
| `eed49ef` | `test_def084_overlay_narration_copy_guard.py` — widened guard |

No CR069-BE path touched: `sharia_universe.py` and `safety_floor.py` are unmodified
(`git show --name-only` on all three SHAs). `sharia_screen()` stays dormant — nothing
in this lane computes or narrates a ratio.

## Self-test

`cd backend && .venv/bin/python -m pytest tests/unit/ -q -k "overlay or room_runner or sharia or halal or room_prompt or agent_prompt"`
→ **242 passed, 794 deselected in 72.59s, exit 0**

Full suite: `pytest tests/unit/ -q` → **1036 passed, 2 warnings in 119.99s, exit 0**

Guard red-before-fix: with `overlay_generator.py` reverted to `9dcc750` and the new
guard in place → **67 failed, exit 1**. 12 of those are substantive content failures
(`test_missing_universe_degrades_loudly_*`, which calls the old two-arg signature and
still fails on what the copy says); the other 55 fail on the new `halal_universe=`
keyword the old signature rejects. Stated as measured, not as a stronger claim.

## Notes for the auditor

- The **paused** and **no-universe** states are rendered too, not just the three
  ticker states — a `HalalUniverse(stale=True)` and a missing/bare-set universe each
  get their own loud line (CR040).
- The per-ticker line is `ShariaVerdict.message()` **verbatim**, and a test asserts
  byte-identity. That is the anti-evasion move the assign asked for: rewording the
  surrounding prose cannot make the narration diverge from what enforcement decided.
- The 1-on-1 path (`agent_runner`) also attaches the universe now, without a ticker —
  it gets provenance + the three-state rules but no per-name verdict, because no
  ticker is known at prompt-build time on that path. Named here rather than omitted.
- Not verified by me: live smoke against `llm_audit` (CR069 §Acceptance 4 asks for a
  post-promotion read-back). That needs Alpha; this lane is Mac-side only.

ROUND: 1
