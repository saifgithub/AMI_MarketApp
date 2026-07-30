<!-- lane assign — Architect-owned. CR052. -->
# BE-GUARD191 — make the four-leg invariant derive its subjects instead of listing them

KIND: code
INSTANCE: coder.api
GATE: none    <!-- Sprint mode (Saiful, 2026-07-30): lanes integrate on my verification; track U audits the sprint as one batch. -->
BUDGET: $8
DEPENDS-ON: none

## What and why

`docs/defect/_registry/DEF191.row.md` — **read it in full.**

`test_cr101_be1_settable_risk_caps.py::test_every_enforced_limit_field_is_enforced_disclosed_and_settable`
was written in CR101-BE1 as *the* mechanism that stops the "settable but unenforced" class recurring.
The CR101 row calls it "the check that stops this recurring, and it is what CR101 exists for as much
as the fields are." **It enumerates its subjects by hand.**

**Measured one CR later:** CR101-BE2 added five new enforced-limit fields — `post_loss_cooldown_hours`,
`max_open_positions`, `max_trades_per_day`, `max_trades_per_week`, `max_open_risk_pct` — and the guard
picked up **none** of them. The builder had to append five blocks manually and disclosed it rather
than let it pass. The guard failed its own purpose on the very next change, which is
`failure_patterns.md` **P12** recurring inside the file written to catch P12.

**The failure mode is worse than having no guard.** A developer who adds a field and forgets the
checklist gets a **green suite** containing a test whose *name* asserts universality —
`every_enforced_limit_field` — while its body covers a frozen list. That is a positive, misleading
signal, not a missing one. Until this is fixed, the guard's green is evidence about the listed
fields only, never about the schema.

**This needs a design decision, which is why it is a lane and not a patch.** The guard must *derive*
its subject list from the schema. Two shapes named in the row:

- a class-level registry of enforced-limit fields, or
- `Field(json_schema_extra={"enforced_limit": True})` on each field, with the test iterating
  `Mandate.model_fields` and failing on any marked field missing a leg.

Either converts the rule into **"you cannot add an enforced limit without declaring it"**, which is
the make-it-structural discipline this project applies to anything that must hold (CR038: prompt
instructions are not controls — conventions are not controls either). **Pick one, and justify the
pick in your hand-off.** The second shape keeps the declaration next to the field, which is where
someone adding a field is already looking; the first keeps it in one greppable place. That tradeoff
is yours to make and to argue.

**Note what this is NOT.** It is a different defect from CR101-BE2's round-1 BLOCKER (three limits
silently unenforced on the Room path). That one was missing enforcement; this is the missing detector
that should have made it impossible — **and neither the guard nor the suite caught the other.**

## Fences

- **Yours:** `backend/app/schemas/mandate.py`,
  `backend/tests/unit/test_cr101_be1_settable_risk_caps.py`, and whatever new registry module you
  add.
- **Do NOT touch** `backend/app/agents/*` or `content/agents/*` (lane `BE-AGENTS`),
  `backend/app/api/journal.py` / `reputation_service.py` / `api/sse.py` (lane `BE-TRUST`),
  `backend/app/api/room.py` (lane `ROOM-DEF161`), or `mobile/` (lane `MOBILE-DEF189`).
- **Do NOT change what any limit enforces, resolves to, or discloses.** BE-MANDATE merged a
  `resolved` sub-object onto the mandate GET today (DEF193) — build on it, do not rework it.
- **Do not weaken the four legs to make derivation easier.** If a field genuinely cannot satisfy a
  leg, the answer is an explicit, justified exemption in the registry — not dropping the leg.

## Acceptance

1. **The guard iterates a derived list, and its subject count is asserted.** A test that walks
   `Mandate.model_fields` and happens to find nothing must FAIL, not pass — the vacuity leg is the
   whole point, since a silently-empty iteration is exactly the failure being fixed.
2. **All eight currently-enforced fields are picked up automatically** — the three from CR101-BE1
   (`max_drawdown_pct`, `sector_cap_pct`, `single_name_cap_pct`) and the five from CR101-BE2 — with
   the hand-written blocks deleted, not left alongside.
3. **Adding a marked field with a missing leg FAILS the suite.** Prove it: add a throwaway enforced
   field, watch the guard go red naming the missing leg, then remove it. Show that output in the
   hand-off — this is the acceptance criterion that actually tests the fix.
4. **Adding an UNmarked enforced field is also caught, or you have stated why it cannot be.** This
   is the harder half: a developer who forgets the marker is the same developer who forgot the
   checklist. If your design cannot catch that, **say so explicitly** rather than implying the class
   is closed — a partial fix disclosed is worth more than a total one claimed. (A cross-check
   against the deterministic enforcement sites is one way; there may be others.)
5. **Mutations:** revert the derivation and show the guard stops catching the throwaway field.
6. Full suite from repo root: `"./backend/.venv/bin/python" -m pytest backend/tests/unit/ -q`.
   **`python` is not on PATH. Never use `-x`.** Baseline **1798**; finish `>= 1798` with zero
   failures **except** `test_cr084_revenuecat_webhook.py::test_test_store_expiration_revokes_to_floor_pass`,
   which is **another track's uncommitted work, not yours** — verified passing 23/23 at a clean HEAD.
   **Do not pipe pytest through `tail`/`head` and read the exit code.** Read the `N passed, M failed` line.

## Registers

Flip `DEF191` to `fixed` only if acceptance 3 and 4 are genuinely met; if 4 is a disclosed partial,
**leave it `open`** and say what remains. **Put the note in the DESCRIPTION column — the status cell
must stay a bare token** (DEF203). Then `python3 scripts/registers/gen_registers.py gen def` and
commit both **in the same commit** (DEF159). **Explicit pathspec.**

Also add a line to `failure_patterns.md` **P12**'s enforcing-checks block recording that the guard is
now derived rather than enumerated — P12 currently cites this test by name as if it were sound.

## Hand-off delivery

**Write your hand-off file EARLY and keep updating it.** Write
`orchestration/dispatch/lanes/BE-GUARD191.coder.api.md` with `STATUS: READY_FOR_AUDIT (round 1)`; get
it onto `main` AND push your lane branch to origin (**DEF175**).

**If you can measure that an instruction here is wrong, stop and disclose with the measurement.**

ASSIGNED: coder.api round 1
DISPATCH: OPEN
