<!-- dispatch assign lane — Architect-owned. CR052. QUEUED (no ASSIGNED line yet). -->
# DEF061-ROOM — assign (queued): custom_constraints — the PM explains what it can't hard-enforce

KIND: code
INSTANCE: coder.room
ACCEPTANCE: docs/defect/DEF061_mandate_compliance_toggles_not_enforced/ (+ def_list.md DEF061 row)
DEPENDS-ON: —    <!-- disjoint from DEF061-BE (safety_floor / classification_universe, coder.api) — this is room-cluster agent narration. Runs independently. -->
HOT-FILES: `backend/app/agents/overlay_generator.py` (narrates mandate/compliance fields into agent prompts) + the PM prompt (`room_prompts.py` / `agent_prompts.py`). Serialize internally with any other coder.room lane touching those (currently CR077-ROOM).

**Founder ruling (2026-07-25):** *"Keep [custom_constraints], and [the] PM can explain for any
conditions that cannot be met."* So `custom_constraints` stays a freeform list and is **NOT** a
deterministic hard filter (freeform text can't be structurally enforced — arbitrary NLP, DEF059 trap).
The honest behaviour is **transparency**: the PM (and the relevant agents) must **surface** each stated
custom constraint and, where it cannot be deterministically enforced, say so plainly in the Verdict /
narration — never silently drop it.

**Build:**
- `overlay_generator.py` already renders `custom_constraints` into agent prompt text — verify it does,
  and make the framing explicit: the constraints are the user's stated values the PM should honour in
  its reasoning AND flag when a proposed trade may conflict but cannot be hard-checked.
- The PM's prompt should instruct: for any active `custom_constraints`, name them in the Verdict and, if
  a constraint is not machine-checkable, state that AMI can't hard-enforce free-text constraints and
  that the user should review the position against it — a best-effort disclosure, not a silent pass.
- **Honest ceiling (CR038):** prompt instructions are ~30% reliable — this is defence-in-depth narration,
  the correct mechanism *because* custom_constraints is inherently not structurally enforceable. Do not
  present it as a guarantee. Pairs with `DEF061-MOBILE` relabelling the Settings copy to match.

**Gate:** independent (safety-adjacent honesty behaviour crossing to users) or content-review of the
prompt change — Architect to set on activation.

**Queued:** activate (write the assign round-1 signal line) after DEF061-BE lands, or in parallel if a
coder.room slot is free (wip_cap 2; CR077-ROOM holds one). (Prose omits the literal assign token so it
is not parsed as a live signal.)
