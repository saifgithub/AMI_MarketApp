<!-- lane assign — Architect-owned. CR052. -->
# ROOM-DEF161 — an all-gutter comb claims everyone abstained; the Journal says "NOT RECORDED"

KIND: code
INSTANCE: coder.room
GATE: none    <!-- Sprint mode (Saiful, 2026-07-30): lanes integrate on my verification; track U audits the sprint as one batch. -->
BUDGET: $6
DEPENDS-ON: none

## What and why

`docs/defect/_registry/DEF161.row.md` — **read it in full.**

Reconnecting to a run persisted **before** the CR106-B2 stance envelope draws an **all-gutter stance
comb** in the Room, while the Journal renders **"NOT RECORDED"** for the same run. Two surfaces, one
run, two different answers.

**Mechanism:** the `agent_done` replay always emits the three stance keys
([`api/room.py:226-231`](../../backend/app/api/room.py)), so a pre-B2 run deserialises with
`stance=None` defaults and the live-reconnect path renders them as an empty comb. The Journal mapper
for the identical run resolves the same absence to an explicit not-recorded state
(`room_board_mappers.dart:183`).

**Why it matters more than its size.** An all-gutter comb reads as **"everyone abstained"** — a
*wrong claim*, not a missing one. That inversion is what CR040 exists to catch: the absence of data
rendered as a confident statement about the data. And it is the **DEF098 class** (two renderers of
one rule, neither a superset), surviving on the one narrow path CR106's one-widget consolidation does
not cover — reconnecting to a run that predates the deploy.

Scope is bounded and shrinking: only runs persisted before B2. DEF147 made new runs immune.

**Fix shape (from the row):** make the replay path distinguish **absent-from-snapshot** from
**recorded-neutral**, the way the Journal mapper already does — rather than defaulting the three keys
at the wire boundary. The wire should be able to say "I do not know", and today it cannot.

## Fences

- **Yours:** `backend/app/api/room.py` and its tests.
- **Do NOT touch `mobile/`.** If the honest fix requires a client change to render the third state,
  **stop and disclose it in your hand-off with the specific widget and line** rather than reaching
  into `mobile/` — a separate mobile lane will take it. Say clearly whether the backend half alone
  is a real improvement or whether it is inert without the client half; I need that answer to decide
  whether to lane the other half.
- **Do NOT touch** `backend/app/agents/*` (lane `BE-AGENTS`), `backend/app/schemas/mandate.py` (lane
  `BE-GUARD191`), or `backend/app/api/journal.py` / `reputation_service.py` / `api/sse.py` (lane
  `BE-TRUST`).
- **Do not migrate or rewrite persisted run snapshots.** The fix is in how absence is *read*, not in
  back-filling history.

## Acceptance

1. **A test that FAILS against current code**, replaying a pre-B2-shaped snapshot (no stance
   envelope) and asserting the wire distinguishes absent from neutral. Write it first, watch it red.
2. **A recorded-neutral stance still round-trips as neutral** — the fix must not collapse a genuine
   abstention into "not recorded". A test for both directions; this is the pair that makes the
   distinction real rather than a renamed default.
3. **The two surfaces agree.** State explicitly in your hand-off what the Journal mapper resolves the
   same input to, and confirm the replay path now produces something that maps to the same user-
   visible answer. The defect is the disagreement, so "my side is now correct" is only half a fix.
4. **Mutation:** revert the fix, show the test goes RED. Report honestly if it comes back GREEN.
5. Full suite from repo root: `"./backend/.venv/bin/python" -m pytest backend/tests/unit/ -q`.
   **`python` is not on PATH. Never use `-x`.** Baseline **1798**; finish `>= 1798` with zero
   failures **except** `test_cr084_revenuecat_webhook.py::test_test_store_expiration_revokes_to_floor_pass`,
   which is **another track's uncommitted work in the shared checkout, not yours** — verified passing
   23/23 at a clean HEAD. Do not touch `webhooks.py` or `scripts/`.
   **Do not pipe pytest through `tail`/`head` and read the exit code.** Read the `N passed, M failed` line.

## Registers

Flip `DEF161` to `fixed` only if the two surfaces genuinely agree; if the client half is still owed,
leave it `open` and name what remains. **Put the note in the DESCRIPTION column — the status cell must
stay a bare token** (DEF203). Then `python3 scripts/registers/gen_registers.py gen def` and commit
both **in the same commit** (DEF159). **Explicit pathspec — never `git add -A`, never bare commit.**

## Hand-off delivery

**Write your hand-off file EARLY and keep updating it.** Write
`orchestration/dispatch/lanes/ROOM-DEF161.coder.room.md` with `STATUS: READY_FOR_AUDIT (round 1)`;
get it onto `main` AND push your lane branch to origin (**DEF175**).

**If you can measure that an instruction here is wrong, stop and disclose with the measurement.**

ASSIGNED: coder.room round 1
DISPATCH: ACCEPTED
