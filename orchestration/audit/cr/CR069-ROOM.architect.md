<!-- audit bridge — builder writes, auditor reads. CR069-ROOM. -->
# CR069-ROOM — audit submission (coder.room → independent auditor)

SUBMITTED: round 1
GATE: independent
BRANCH: lane/CR069-ROOM.coder.room  (origin; nothing pushed to main)
ACCEPTANCE: docs/forward_planning/CR069_sharia_compliance_indicator/CR069_sharia_compliance_indicator.md (§Acceptance 4, §Design constraints 1–2)
DEPENDS-ON: CR069-BE — merged `bdc410f`. Consumed its types; edited none of its files.

## What / why

CR069-BE moved the deterministic path to a **real sourced AAOIFI screen**, but
`overlay_generator.py` was outside its HOT-FILES and still emitted DEF084's
*"curated demonstration universe … NOT a Sharia screen"* text. So the DEF084-ROOM
contradiction was live again, pointing the other way: the code ran a sourced screen
while the 12 agents were told it was a demonstration allowlist.

This lane renders the sourced `ShariaVerdict` — standard, source, as-of date and
which state applies — into the overlays the agents actually receive. It renders a
**sourced** verdict, never a computed one: `sharia_screen()` stays dormant
(constraint 4) and no threshold was reintroduced.

## SHAs (in order)

- `57f2c0f` — `app/agents/overlay_generator.py`: `generate_overlay()` takes
  `halal_universe` + `ticker`; new `_halal_narration()` renders provenance + the
  three states + the per-ticker verdict; the DEF084 comment block, the Fundamentals
  halal line and the Trader halal line rewritten off the demonstration-universe copy.
- `08b0574` — thread the run's universe to the overlay:
  `agent_prompts.build_agent_prompt` (+2 kwargs), `room_prompts.build_room_messages`
  (+`halal_universe`, passes the Room's `ticker` through), `room_runner`'s **two**
  `build_room_messages` call sites (`halal_universe=ctx.halal_universe`), and
  `agent_runner`'s 1-on-1 path (`default_halal_universe_async()` when the flag is set).
- `eed49ef` — `tests/unit/test_def084_overlay_narration_copy_guard.py`: the DEF084
  guard widened, not replaced.

All four files in `08b0574` plus `overlay_generator.py` are coder.room-owned per
`roster/coder.room.md`. `sharia_universe.py` and `safety_floor.py` are untouched —
verifiable with `git show --name-only 57f2c0f 08b0574 eed49ef`.

## What the agents now see

Four states, all rendered (paused and no-universe are loud lines, not silence):

| State | Narration |
|---|---|
| pass | provenance line + three-state rules + `"AAPL passes the AAOIFI screen (S&P 500 Sharia Industry Exclusions Index (via SPUS), as of 2026-07-22)."` |
| screened out | … + `"XOM is in the parent index but does not pass the AAOIFI screen (…), so this mandate won't trade it."` |
| unknown (G3) | … + `"ZZZZ isn't in the parent index, so the AAOIFI screen AMI uses hasn't reviewed it. That's not a ruling either way — AMI doesn't know."` and an explicit instruction that this is NOT a ruling, NOT a failure, and permitted |
| paused (`stale=True`) | `"HALAL constraint — PAUSED. AMI could not refresh the AAOIFI Sharia screen (last updated …). Tell the user the halal filter is paused; do NOT tell them a Sharia screen was applied…"` |
| no universe attached | `"…AMI's Sharia screen and its provenance were NOT attached to this briefing. Do not tell the user a Sharia screen was applied…"` |

AMI by name throughout; the string "the AI" appears nowhere in the block.

## Contract re-verification (the seam I crossed)

The seam is coder.room's overlay ↔ coder.api's `HalalUniverse`. I did **not** verify
by "it compiles": the per-ticker line is `ShariaVerdict.message()` **verbatim**, and
`test_per_ticker_line_is_byte_identical_to_the_sourced_verdict` asserts the real
`HalalUniverse.resolve(t).message()` output is a substring of the rendered overlay for
all three states. If CR069-BE rewords its message, this lane's guard goes red rather
than the narration silently drifting. Provenance is read off the same `resolve()`
return, and `stale` off the universe, duck-typed exactly as `safety_floor` does — a
bare `set`/`None` degrades loudly instead of raising.

## The guard — widened, not replaced

The auditor's note that these guards are phrase-specific was the design input. Kept:
the ratio/threshold blocklist (extended to 6 phrases). Added:

1. **Byte-identity to `ShariaVerdict.message()`** — the structural anti-evasion layer;
   no rewording can evade it.
2. **No percentage of any kind inside the HALAL block** (`\d+\s*(%|per ?cent)`) — a
   reworded "30% of market cap" slips past a phrase list, not past this.
3. **Retired-mechanism blocklist** — `demonstration universe` / `curated demonstration`
   / `fixed allowlist` / `DEFAULT_HALAL_DEMO_UNIVERSE` now fail, inverting the old
   `test_halal_compliance_block_names_the_demonstration_universe`, which asserted the
   opposite and would have pinned the lie in place.
4. **Per-state assertions** — unknown reads as no-ruling and never as a pass; screened
   out reads as a real exclusion; paused degrades loudly; no-universe degrades loudly;
   a non-halal mandate gets no Sharia narration at all.

Most run across all 12 agents (`@pytest.mark.parametrize(TWELVE_AGENT_IDS)`).

## Tests + observed output

```
cd backend && .venv/bin/python -m pytest tests/unit/ -q \
  -k "overlay or room_runner or sharia or halal or room_prompt or agent_prompt"
→ 242 passed, 794 deselected in 72.59s        exit 0

cd backend && .venv/bin/python -m pytest tests/unit/ -q
→ 1036 passed, 2 warnings in 119.99s          exit 0
```

**Red before the fix** (CR069 §Acceptance 1's posture): `git checkout 9dcc750 --
backend/app/agents/overlay_generator.py`, new guard in place →
`67 failed in 2.81s, exit 1`. Honest breakdown: **12** are substantive content
failures (`test_missing_universe_degrades_loudly_*`, which calls the old two-argument
signature and fails on what the copy says); the remaining **55** fail because the old
signature rejects the `halal_universe=` keyword. Working tree restored afterwards.

## What I could NOT verify

- **CR069 §Acceptance 4's live smoke** — convene a name inside and outside the set on
  Alpha and read the prompts back from `llm_audit`. That needs a promotion; the Mac is
  a pure editor. This lane proves the prompt text at the function boundary and at the
  two `room_runner` call sites, not that a deployed convene produced it.
- **Whether an LLM obeys the unknown-state instruction.** Prompt instructions are not
  controls (CR038: ~70% ignore rate). The structural control for unknown is CR069-BE's
  `is_blocking`, which this lane does not touch. This is narration, and it should be
  audited as narration.

REQUESTED: independent audit, round 1
