<!-- lane assign — Architect-owned. CR052. -->
# CR129-BE — derive all seven risk limits from risk tolerance, backfill alpha, and close DEF187

KIND: code
INSTANCE: coder.api
GATE: independent    <!-- Inverts CR101-BE2's acceptance 4 on purpose and constrains 13 live users. A wrong table silently changes what the floor enforces for every account. -->
BUDGET: $20
DEPENDS-ON: none

## What and why

Read `docs/forward_planning/CR129_risk_limits_from_risk_tolerance/README.md` in full first. It
carries the measurements, the rulings, the sourced preset tables and the Day Trader preset design.
Do not re-derive any of it.

Saiful: *"The onboarding questions we already have is enough to determine the users risk tolerance…
we backfill them all based on the current risk tolerance scores."* Onboarding currently sets **none**
of the seven CR101 limits.

## What to build

1. **Preset tables + resolvers** for the five CR101-BE2 fields, keyed on `risk_score`, following
   CR101-BE1's existing `resolved_*` coalesce-at-read pattern. `None` now means **"follow my risk
   profile"**, not "off".
2. **THE BACKFILL IS STRUCTURAL, NOT A MIGRATION.** Because resolution happens at read time, every
   existing mandate is covered the moment this deploys. Do not write an UPDATE over `mandates`.
3. **Close DEF187** — unify the single-name cap so the trade-ticket path and the Room read the SAME
   resolver. CR101-BE1 refused this because it tightens existing users ~16.7x; **Saiful has
   explicitly authorised it** (13 mandates, alpha). Expect the ~43 tests that went RED in BE1 to go
   RED again — those are now *expected behaviour changes*, and each one you update must be updated
   because the new value is correct, not to make the suite pass. Say which ones you touched.
4. **Day Trader preset** — writes explicit permissive overrides. **NOT `risk_score = 6`** (the field
   is `ge=1, le=5` and feeds 12+ overlay sites). **No bypass flag** — the floor still runs, it just
   evaluates permissive numbers. Compliance / locale / halal / allow-blocklist are **untouched**.
5. **Loud backfill (CR040)** — a `MANDATE_EDIT` journal entry per user describing what changed and
   why. Also fixes **DEF197**: the two BE1 caps currently journal a bare "Mandate updated."

## Fences

- **Do NOT touch `mobile/`** — CR129-MOBILE.
- **Do NOT widen `risk_score`.**
- **Do NOT make compliance, locale, halal or allow/blocklist relaxable by any preset.**
- Registers: row file and regenerated table in the SAME commit (**DEF159**).

## Acceptance

1. Each of the five resolves from `risk_score` per the CR's table; `None` follows the profile.
2. **The inverted migration proof.** CR101-BE2 proved nobody's enforcement changed. Prove the
   opposite: for every `risk_score` 1–5, every limit changes to the documented value. This is the
   criterion I read first.
3. **The "nobody is forced to concentrate" guard** — for every risk score, names reachable after
   BOTH `max_open_positions` and `max_open_risk_pct` apply must be **>= 30**. Coupled to three
   numbers; a future tweak to any one could break it silently. Expected: 50/60/35/30/30.
4. DEF187 closed: one resolver, both paths, proven by a test that sets a value and observes both
   the ticket block and the Room clamp move together.
5. Day Trader preset sets all seven permissive, and a test proves a **compliance/halal block still
   fires** under it. That test is the whole boundary.
6. "Off" stays expressible — cooldown `0`, percentages `100`, counts high — all still settable.
7. Backfill journalling: a test asserts the entry names the change.
8. Mutations: revert the DEF187 unification → acceptance 4 RED. Break one preset value → acceptance
   2 RED. Report honestly, **including any that come back GREEN**.
9. Full backend suite green from repo root: `"./backend/.venv/bin/python" -m pytest backend/tests/unit/ -q`, ~250s. `python` is NOT on PATH. Never `pytest -x`. Baseline **1645**.

## Hand-off delivery

Write `orchestration/dispatch/lanes/CR129-BE.coder.api.md` with `STATUS: READY_FOR_AUDIT (round 1)`;
write `orchestration/audit/cr/CR129-BE.architect.md` with an explicit `SUBMITTED: round 1` line; get
BOTH onto `main` AND push your lane branch to origin. A live auditor watcher reads `main`; a lane
whose hand-off sits on its own branch is finished and invisible at once (**DEF175**), and a branch
that is never pushed leaves the auditor nothing to fetch.

**If you can measure that an instruction here is wrong, stop and disclose with the measurement.**
Three of the Architect's rulings were overturned that way on CR101 and each was the cheap outcome.

ASSIGNED: —
DISPATCH: UNASSIGNED
