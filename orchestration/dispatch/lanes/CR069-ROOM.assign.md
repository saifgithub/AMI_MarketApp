<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR069-ROOM — assign (render the sourced verdict into the 12 agents' overlays)

KIND: code
INSTANCE: coder.room
ACCEPTANCE: docs/forward_planning/CR069_sharia_compliance_indicator/CR069_sharia_compliance_indicator.md (§Acceptance 4, §Design constraints 1-2)
DEPENDS-ON: CR069-BE — its `ShariaVerdict` is what this lane renders.
GATE: independent    <!-- recorded upfront. Agent narration asserting a compliance screen is a user-facing claim about what the product does — and this is literally DEF084-ROOM's surface, where three narration sites asserted a screen no code computed. -->
HOT-FILES: backend/app/agents/overlay_generator.py (coder.room owns)

**This lane exists because the decomposition missed it.** `coder.api` flagged it in its own hand-off
rather than quietly leaving the gap, and it was right: `overlay_generator.py` is `coder.room`'s file,
outside `CR069-BE`'s HOT-FILES, so that lane could not touch it and correctly did not.

## What

After CR069-BE, `ctx.halal_universe` on the Room path is a full `HalalUniverse` and
`ComplianceResult.sharia_verdict` carries status + standard + source + as-of. **The data is
available to the agents; the prompts do not render it.** `overlay_generator.py` still emits the
generic DEF084 *"curated demonstration universe"* text.

Render the `ShariaVerdict` — standard, source, as-of date, and which of the three states applies —
into the overlays the 12 agents receive.

## Why it matters more than a wording change

DEF084-ROOM (`cef212f`) was exactly this surface: three narration sites told agents a Sharia screen
ran when no code computed one, so the deterministic path and the agent layer contradicted each
other. CR069-BE has now moved the deterministic path to a **real sourced screen** — which means the
contradiction is live again, pointing the other way: the code now runs a real AAOIFI screen while
the agents are still told it is a demonstration universe.

That lane also found and removed **fabricated ratio thresholds** the prompts were feeding agents
(a 33% debt-to-equity and 5% interest-income test, backed by dead constants, for a computation that
never ran). Do not reintroduce any threshold. This lane renders a **sourced verdict**, never a
computed one — `sharia_screen()` stays dormant (constraint 4).

## The three states, in agent-facing language

- **pass** — names the standard, source and as-of date.
- **screened out** — in the parent index, absent from the compliant set.
- **unknown** — outside the parent index. **G3: permitted, not blocked.** The agents must be told
  this is *not a ruling*, or they will narrate an unscreened ticker as though it passed. That is the
  DEF084 failure exactly, and unknown is the state where it is easiest to make.
- **paused / unavailable** — the screen could not refresh. Degrade loudly here too; an agent that
  says nothing about a paused screen is a silent fallback with a narrator.

## Constraints

- **AMI by name**, never "the AI".
- Do not touch `sharia_universe.py`, `safety_floor.py`, or any CR069-BE path — consume its types.
- Extend the DEF084 overlay-narration copy guard (`test_def084_overlay_narration_copy_guard.py`)
  rather than replacing it. The auditor noted those guards are **phrase-specific**, so a
  differently-worded claim can evade them; widen the check as you go.
- Commit incrementally.

**Self-test:** `cd backend && .venv/bin/python -m pytest tests/unit/ -q -k "overlay or room_runner or sharia or halal"`

## Delivery

Push to `lane/CR069-ROOM.coder.room`, never `main`. Hand-off:
`orchestration/dispatch/lanes/CR069-ROOM.coder.room.md` (`STATUS: READY_FOR_AUDIT (round 1)`) +
`orchestration/audit/cr/CR069-ROOM.architect.md` (`SUBMITTED: round 1`).
**Commit those two hand-off files.** The board derives from the working tree, so an uncommitted
hand-off looks identical to a delivered one and is invisible to an auditor in a fresh worktree —
see DEF087. Chunk evidence list, not the DoD. Commit tag `(AT:coder.room CR069)`.

<!-- Not ASSIGNED yet — depends on CR069-BE being merged. Renders UNASSIGNED until then. -->
DISPATCH: OPEN
