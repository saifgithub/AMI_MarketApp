<!-- lane assign — Architect-owned. CR052. -->
# BE-DEF160 — make "Restart onboarding" actually replace the mandate

KIND: code
INSTANCE: coder.api
GATE: none    <!-- Sprint mode (Saiful, 2026-07-30): lanes integrate on my verification; track U audits the sprint as one batch. -->
BUDGET: $12
DEPENDS-ON: none

## What and why

`docs/defect/_registry/DEF160.row.md` — **read it in full.**

"Restart onboarding" does nothing for any user who already has a mandate: the whole interview
re-runs, the readback preview is built, and the old mandate keeps governing. DEF158 already corrected
the dialog's copy so it stops promising otherwise. This lane is the other half.

**RULED by Saiful 2026-07-30: make the promise true** (option 1 in the row). The reasoning is his own
precedent on risk settings — *"a risk setting that a user cannot change violates the user's rights"* —
and the fact that the most discoverable route to "change my strategy" is currently a dead end while
the route that works (Settings → My Mandate) looks like housekeeping.

**Measured state — this is why it is not a one-liner:**

- A `mandates` row is created only by claim-binding (`_bind_onboarding_session`, `auth.py:78-90`) or a
  Settings edit. `get_or_default()` returns a default **without persisting**.
- The bind is guarded by `get_mandate_store().get(user_id) is None` and **that guard is correct for
  the case it was written for**: DEF060, re-auth replaying the same `onboarding_session_id`, which
  without the guard would silently overwrite a mandate the user had since edited. **Do not remove
  it.** The two cases are indistinguishable at that call site precisely because nothing tells the
  backend "this interview was a deliberate restart".
- `POST /onboarding/readback/confirm` (`onboarding.py:98`) currently takes **no authenticated user at
  all** — just a `session_id` — and its confirm path only marks the session complete.
- An already-signed-in user retaking the interview **never re-auths**, so the bind path is not even
  reached and the readback preview is built and dropped.

**So the fix is: an explicit restart signal, carried from the client through confirm, that authorises
replacing an existing mandate for an authenticated user — while leaving DEF060's replay guard intact
for every path that does not carry it.** A restart must be a *different operation*, not a relaxed
version of the same one.

## Fences

- **Yours:** `backend/app/api/onboarding.py`, `backend/app/api/auth.py` (the bind path only),
  `backend/app/schemas/onboarding.py`, the mandate store's version/upsert path, and their tests.
- **Do NOT remove or weaken `_bind_onboarding_session`'s `is None` guard.** It is DEF060's fix and it
  is right. Add a distinct authorised path; do not widen the existing one.
- **Do NOT touch `mobile/`.** The client must send the restart signal, so a mobile half almost
  certainly exists — **name it precisely in your hand-off** (file, widget, the call site that would
  set the flag) and say whether the backend half is useful on its own or inert without it. I need
  that answer to decide whether to lane the client half; ROOM-DEF161 answered this exact question
  well today and it saved a whole lane.
- **Do NOT touch** `backend/app/api/one_on_one.py` / `credit_service.py` (lane `BE-DEF113`).
- **Do not silently migrate or rewrite existing mandates.**

## Acceptance

1. **A test that FAILS against current code**: an authenticated user who already has a mandate
   completes a restarted interview, confirms the readback, and their stored mandate is **replaced**.
2. **DEF060's guard still holds.** A test proving that a *re-auth replaying the same
   `onboarding_session_id`* — no restart signal — still does **not** overwrite an edited mandate.
   **This is the criterion that matters most**: the defect being fixed and the defect not being
   re-opened are the same code path, and a fix that closes one by opening the other is a net loss.
3. **The mandate version is bumped** so the change is visible in history and journal replay. If no
   version field exists, say so and propose the smallest thing that makes the change auditable —
   do not invent a versioning scheme unasked.
4. **The restart signal is explicit and cannot be defaulted on.** A request that omits it behaves
   exactly as today. State in your hand-off where the signal lives (request field, session flag) and
   why that placement cannot be set accidentally.
5. **`confirm_readback` gains authentication without breaking the anonymous path.** Onboarding is
   anonymous-first by design (a locked decision); an anonymous user must still be able to complete
   the interview. Say how you kept both working.
6. **Mutations:** revert the fix, show the test in (1) goes RED; separately, remove the guard your
   fix relies on and show the test in (2) goes RED. Both directions.
7. Full suite from repo root: `"./backend/.venv/bin/python" -m pytest backend/tests/unit/ -q`.
   **`python` is not on PATH. Never use `-x`.** Baseline **1812**; finish `>= 1812` with zero failures
   **except** `test_cr084_revenuecat_webhook.py::test_test_store_expiration_revokes_to_floor_pass`,
   which is **another track's uncommitted work in the shared checkout, not yours** — verified passing
   23/23 at a clean HEAD. Do not touch `webhooks.py` or `scripts/`.
   **Do not pipe pytest through `tail`/`head` and read the exit code.** Read the `N passed, M failed` line.

## Registers

Flip `DEF160` to `fixed` only if the user-visible promise is genuinely true end to end; if the client
half is owed, leave it `open` and name exactly what remains. **Put the note in the DESCRIPTION column
— the status cell must stay a bare token** (DEF203). Then
`python3 scripts/registers/gen_registers.py gen def` and commit both **in the same commit** (DEF159).
**Explicit pathspec — never `git add -A`, never bare commit.**

## Hand-off delivery

**Write your hand-off file EARLY and keep updating it.** Write
`orchestration/dispatch/lanes/BE-DEF160.coder.api.md` with `STATUS: READY_FOR_AUDIT (round 1)`; get it
onto `main` AND push your lane branch to origin (**DEF175**).

**If you can measure that an instruction here is wrong, stop and disclose with the measurement.**

ASSIGNED: coder.api round 1
DISPATCH: OPEN
