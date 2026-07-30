<!-- lane assign — Architect-owned. CR052. -->
# BE-AGENTS — stop the agent layer describing things that do not exist

KIND: code
INSTANCE: coder.api
GATE: none    <!-- Sprint mode (Saiful, 2026-07-30): lanes integrate on my verification; track U audits the sprint as one batch. -->
BUDGET: $10
DEPENDS-ON: none

## What and why

Two defects, one family: **text an agent reads as authoritative that is not true.** Neither breaks a
test today; both change what a user is told.

```
docs/defect/_registry/DEF129.row.md   the Concierge is told it can mute/promote agents — no such capability exists (MUTE/PROMOTE HALF ONLY)
docs/defect/_registry/DEF188.row.md   SAFETY_FLOOR_BLOCK is exported as an unsubstituted template carrying a literal [[CAP]]
```

**DEF129 — read the row carefully, most of it is already DONE.** The briefing half was fixed
2026-07-29 and the row is long because it records that. **Your scope is the mute/promote half only**,
which is two lines in two layers:

- `content/agents/concierge.md:19-20` — "Schedule morning briefings and reminders (paid tiers only)"
  and "Mute / promote agents"
- `backend/app/agents/overlay_generator.py` — `_concierge_overlay`, the same claims in the **live
  injected prompt**

**Both layers, or the drift just moves** (failure_patterns **P4**). This has already fired on a real
user: of 30 Concierge turns, one invented a whole navigation path — *"Go to the Agents tab… Tap the
agent… you can Mute them (hide from the Room) or Promote them"* — and opened by asserting their
absence from Settings was "by design". That is the app's product-help surface confidently giving
directions to a screen that does not exist.

**Delete is not enough — replace with an explicit negative**, in the style the analysts already use
(`market_analyst.md`: "No MACD … do not cite them"; `social_media_analyst.md`: "No Twitter/X … they
simply don't exist"). CR038's finding is why: the model re-invents a feature from surrounding
product context unless told it is absent. A silent deletion leaves the same inference available.

**DEF188** is small and currently harmless — verified: no production path uses the raw template, and
`from app.agents import` appears **nowhere** in the tree, so the `__init__` export is dead. The row
asks for (a) stop exporting the raw template, (b) a guard test that no rendered prompt contains `[[`,
or (c) both. **Do (c).** (a) alone does not close it: `test_cr056_no_assumed_data.py` imports
`SAFETY_FLOOR_BLOCK` **from `app.agents.safety_floor` directly** and builds a PM prompt out of it, so
the shortcut is already being taken by a route removing the `__init__` export does not block.

## Fences

- **Yours:** `backend/app/agents/safety_floor.py`, `backend/app/agents/__init__.py`,
  `backend/app/agents/overlay_generator.py`, `content/agents/concierge.md`, and their tests.
- **Do NOT touch** `backend/app/schemas/mandate.py` (lane `BE-GUARD191`), `backend/app/api/journal.py`
  / `reputation_service.py` / `api/sse.py` (lane `BE-TRUST`), `backend/app/api/room.py` (lane
  `ROOM-DEF161`), or `mobile/` (lane `MOBILE-DEF189`).
- **Do NOT touch the briefing half of DEF129** — it is fixed and its guards are in place.
- Do not change what the safety floor *enforces*. DEF188 is about how the text is reachable.

## Acceptance

1. **DEF129: both layers carry an explicit negative**, not merely a deletion. A test asserts the
   assembled Concierge system prompt contains no "mute", no "promote" (agent sense) and no
   "schedule … briefing" capability claim — and **positively asserts the prompt is still non-empty
   and still describes the real capabilities**, so the guard cannot pass on a blank string. That
   positive leg is the one the briefing-half fix got right and is worth copying.
2. **DEF129: grep the whole tree for any third copy** of the mute/promote claim (other agent
   markdown, other overlays, lesson content, app copy) and report what you find even if you change
   nothing. P4 is the pattern where two copies were fixed and a third kept shipping.
3. **DEF188: the raw template is no longer exported from `app.agents`**, AND a guard asserts that
   no rendered agent prompt contains `[[` — run it over every prompt-assembly path you can reach,
   not just the safety floor.
4. **DEF188: fix `test_cr056_no_assumed_data.py`'s three raw-template usages** to render through
   `render_safety_floor_block`, or state in your hand-off why they must stay raw. As written they
   are the exact mistake the row predicts, already committed.
5. **Mutations:** revert each fix in turn, show the corresponding test goes RED. Report honestly,
   **including any that come back GREEN**.
6. Full suite from repo root: `"./backend/.venv/bin/python" -m pytest backend/tests/unit/ -q`.
   **`python` is not on PATH. Never use `-x`.** Baseline **1798**; finish `>= 1798` with zero
   failures **except** `test_cr084_revenuecat_webhook.py::test_test_store_expiration_revokes_to_floor_pass`,
   which is **another track's uncommitted work in the shared checkout, not yours** — I verified it
   passes 23/23 at a clean HEAD. Do not try to fix it and do not touch `webhooks.py` or `scripts/`.
   **Do not pipe pytest through `tail`/`head` and read the exit code** — you get the pipe's exit
   code. Read the `N passed, M failed` line.

## Registers

Flip `DEF188` to `fixed`. **`DEF129` stays `open` unless you are confident the mute/promote half is
fully closed** — it is a long row recording several passes; append a line naming exactly what this
pass cleared. Then `python3 scripts/registers/gen_registers.py gen def`, and commit row files and
the regenerated table **in the same commit** (DEF159). **Put the note in the DESCRIPTION column, not
the status column** — the status cell must stay a bare token (see DEF203; three rows were broken
that way today). **Explicit pathspec — never `git add -A`, never bare commit.**

## Hand-off delivery

**Write your hand-off file EARLY and keep updating it.** Write
`orchestration/dispatch/lanes/BE-AGENTS.coder.api.md` with `STATUS: READY_FOR_AUDIT (round 1)`; get
it onto `main` AND push your lane branch to origin (**DEF175** — `dispatch.sh inbox` now fails if you
leave it only on the branch).

**If you can measure that an instruction here is wrong, stop and disclose with the measurement.**

ASSIGNED: coder.api round 1
DISPATCH: ACCEPTED
