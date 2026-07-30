<!-- lane assign — Architect-owned. CR052. -->
# BE-MANDATE — close the paywall bypass, and stop the mandate endpoint hiding a cap it already knows

KIND: code
INSTANCE: coder.api
GATE: none    <!-- Sprint mode (Saiful, 2026-07-30): lanes integrate on my verification; track U audits the whole sprint as one item at the end. -->
BUDGET: $12
DEPENDS-ON: none

## What and why

Two defects that both live in the mandate read/write path, batched because they touch the same files
and separating them would mean two builders fighting over `api/mandate.py`.

```
docs/defect/_registry/DEF179.row.md   paywall bypass — `plan` is client-writable via PATCH /v1/mandate/{user_id} (security review H1)
docs/defect/_registry/DEF193.row.md   GET /v1/mandate/{id} returns null for a cap that is real, binding and already served by another endpoint
```

**Read `docs/governance/security_review_2026-07-29.md` for DEF179's context** — it is the last
unfixed item from that review that is safely codeable (DEF178 and DEF182 are Saiful's).

**DEF179 is the priority.** `PATCH /v1/mandate/{user_id}` takes a raw `dict[str, Any]` and
shallow-merges it through the `Mandate` schema, so `{"plan":"floor_manager"}` validates and
persists. DEF062's re-validation blocks wrong *types*, not entitlement escalation. Two consumers
then read the stored mandate's plan rather than server-side `users.plan`: the 1-on-1 agent-lock gate
(`one_on_one.py:69-84` — patching unlocks all 12 agents free) and Brief edit-cap/retention
(`brief_engine.py:382-386` — bypasses the Floor Pass 3-edit cap). A second vector needs no PATCH at
all: `hydrate_brief_mandate` trusts the client's `mandate_override` body (`brief_engine.py:536`).
Money paths are unaffected — `credit_service` already goes through `effective_plan_for_user()`,
which is exactly the pattern the two broken consumers should adopt.

**DEF193 is a shown-vs-enforced problem, not a feature request.** For `sector_cap_pct` and
`single_name_cap_pct`, `None` does **not** mean "off" — CR101-BE1 kept a server-side preset fallback
that is a **real, binding cap**, but the GET echoes the raw stored value, so an un-overridden cap
comes back `null`, indistinguishable from the five CR101-BE2 fields where `null` genuinely means
unenforced. Meanwhile `GET /v1/portfolio/allocation` returns that same resolved number as
`max_allowed` and has been showing it to users for months. Two endpoints disagree about whether the
cap is knowable. **CR129-MOBILE is blocked on this** — it cannot render a risk-limits screen that
either invents a number or hides one.

## Fences

- **Do NOT touch `backend/app/services/sector_allocation.py`, `backend/app/agents/safety_floor.py`
  or `backend/app/agents/overlay_generator.py`** — lane `BE-MINOR` is live in a parallel worktree
  and owns them.
- **Do NOT touch `backend/app/services/sim_engine.py`** (lane `SIM-DEF166`) or
  `backend/app/services/room_runner.py` (lane `ROOM-MINOR`).
- **Do NOT touch `mobile/`.** CR129-MOBILE consumes DEF193's output but is a separate lane.
- **Do NOT rotate, revoke or regenerate any credential. Do not edit `infra/alpha.env`.**
- **Do NOT touch `SECRET_KEY` usage (DEF182)** — it needs a decision about existing encrypted
  Alpaca credentials that is not yours to make.
- **Do not redesign the preset tables.** DEF193 is about *surfacing* the resolved value the server
  already computes, not about changing what it computes.

## Acceptance

1. **DEF179: entitlement fields are unwritable from the client.** Strip `plan`, `credit_balance`,
   `credit_allowance`, `trial_expires_at`, `trial_started_at` in `mandate_store.patch()` **and** in
   the `hydrate_brief_mandate` override path. A test must prove that a PATCH carrying
   `{"plan":"floor_manager"}` leaves the effective plan unchanged — assert on the **downstream
   consequence** (agent lock still engaged, Brief edit cap still 3), not merely on the stored field.
   That is the difference between testing the fix and testing the code you just wrote.
2. **DEF179: both consumers switch to `effective_plan_for_user(user_id)`** like every other
   entitlement call site. Grep for any *other* reader of `mandate.plan` and report what you find in
   the hand-off, even if you do not change it.
3. **DEF179: silent-drop vs reject is a judgement call — make it deliberately and say which.**
   If a client PATCHes `plan`, does the request 200 with the field ignored, or 400? Pick one, state
   the reasoning in the hand-off, and pin it in a test. Do not leave it accidental.
4. **DEF193: the resolved values are on the wire.** Add a `resolved_*` sibling per preset-backed
   field (or a `resolved` sub-object) to the mandate GET response, sourced from the **same**
   server-side computation `GET /v1/portfolio/allocation` uses for `max_allowed`. A test must assert
   the two endpoints return the **same number** for the same user — that shared assertion is the
   whole point, because the defect is that they disagree.
5. **DEF193: do NOT compute presets client-side.** That is the hard-coded-constant defect CR046
   forbids. The number must come from the server.
6. **Mutations:** revert each fix in turn, show the corresponding test goes RED. Report honestly,
   **including any that come back GREEN**.
7. Full suite from repo root: `"./backend/.venv/bin/python" -m pytest backend/tests/unit/ -q`.
   **`python` is not on PATH. Never use `-x`.** Baseline **1743**; finish `>= 1743`, zero failures.
   **Do not pipe pytest through `tail`/`head` and read the exit code** — you get the pipe's exit
   code. Read the `N passed, M failed` line.

## Registers

Flip each row you closed to `fixed` in its own `docs/defect/_registry/DEF###.row.md`, then
`python3 scripts/registers/gen_registers.py gen def`, and commit the row files and the regenerated
table **in the same commit** (DEF159). **Explicit pathspec — never `git add -A`, never bare commit.**

## Hand-off delivery

**Write your hand-off file EARLY and keep updating it** — a budget cap that kills you mid-lane with
the hand-off unwritten is the worst place to stop, and it has already happened twice here.

Write `orchestration/dispatch/lanes/BE-MANDATE.coder.api.md` with `STATUS: READY_FOR_AUDIT (round 1)`;
get it onto `main` AND push your lane branch to origin (**DEF175**).

**No `.architect.md` submit file** — sprint mode, I integrate on my own verification and track U
audits the sprint as one batch afterwards.

**If you can measure that an instruction here is wrong, stop and disclose with the measurement.**

## INTEGRATION NOTE — Architect, added after launch (AT:R65)

**This lane's worktree was cut at `1e2336e7`, which is BEFORE the SEC-BATCH1 merge (`6c80ede0`).**
Measured: `backend/app/api/one_on_one.py` has **0** rate-limit references at that base and **2** on
current `main` — DEF186 added a per-user 12/min limiter to the exact file this lane edits, and
`brief_engine.py` is in the same position.

**Consequence if unhandled:** a 3-way merge of this lane could drop DEF186's limiter, reverting a
shipped security fix silently, in the file that most looks fine at a glance.

**Required at integration (mine, not the builder's):** after merging, assert the limiter still
exists in `one_on_one.py` and that `test_def186_llm_spend_limits.py` passes — not merely that the
suite count is unchanged, since a reverted limiter plus a lane's new tests can net to the same
number.

**Builder: merge `main` into your lane branch before you finish**, and say in your hand-off whether
the merge touched `one_on_one.py` or `brief_engine.py` and what you did about it.

ASSIGNED: coder.api round 1
DISPATCH: OPEN
