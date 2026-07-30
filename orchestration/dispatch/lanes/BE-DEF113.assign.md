<!-- lane assign — Architect-owned. CR052. -->
# BE-DEF113 — give 1-on-1 a charging spine, priced 0 in alpha

KIND: code
INSTANCE: coder.api
GATE: none    <!-- Sprint mode (Saiful, 2026-07-30): lanes integrate on my verification; track U audits the sprint as one batch. -->
BUDGET: $10
DEPENDS-ON: none

## What and why

`docs/defect/_registry/DEF113.row.md` and
`docs/defect/DEF113_one_on_one_chat_is_never_billed/DEF113_one_on_one_chat_is_never_billed.md` —
**read both.**

`credits.md:18` prices a 1-on-1 turn at 1 credit and sizes the whole Floor Pass allowance against it
(*"13 (= 5 1-on-1s + 1 Room)"*). In code, `credit_service.spend()` has **exactly one call site in the
entire backend** — `room_runner.py:1464`. `backend/app/api/one_on_one.py` contains zero occurrences of
`credit`, `spend`, `402` or `Insufficient`. Unlimited free 1-on-1s on every plan including Floor Pass.

`spend()`'s own docstring already anticipates this lane: *"Callers with a fixed price (1-on-1, later)
pass an int."* CR039 closed with only the Room half wired.

**RULED by Saiful 2026-07-30: wire the spine now, price it 0 in alpha.** Reasoning: it unblocks
CR090's 1-on-1 half (a live-data surcharge cannot attach to a surface with no charging spine), and no
existing Alpha tester hits a paywall they have never seen mid-test, which would contaminate exactly
the feedback we are collecting right now. Flipping the price later becomes a config change rather
than a feature.

**The 0 is the dangerous part of this lane and you must not let it be silent.** A price of 0 that
quietly no-ops is precisely the CR040 shape this project keeps re-committing (DEF038, DEF063: shipped
but dark for months). Requirements:

- The price is a **declared configuration value**, not a literal `0` buried in the call site and not
  an `if alpha: return` early exit.
- The **full path executes at price 0** — `spend()` is called, the ledger row is written, the
  balance arithmetic runs. A 0-credit charge must be a charge of zero, not a skipped charge. That is
  what makes flipping the price to 1 a one-line change that is already tested.
- `GET /v1/admin/config-check` should be able to report the configured 1-on-1 price, so "what are we
  charging in production?" is one curl and not a code read. Add it if that is cheap; say so if not.

## Fences

- **Yours:** `backend/app/api/one_on_one.py`, `backend/app/services/credit_service.py`,
  `backend/app/config.py` (the new setting only), `docker-compose.yml`'s `api-alpha` env block if you
  add a setting, and their tests.
- **Adding an env-driven setting means adding it to `docker-compose.yml`'s `api-alpha` block** —
  `backend/tests/unit/test_config_compose_parity.py` fails the build otherwise. This is P1 in
  `failure_patterns.md` and it has cost this project two features that shipped dark for months.
- **Do NOT touch `backend/app/services/room_runner.py`** — the Room's charging path is settled and
  is not yours to refactor. Reuse `spend()`; do not generalise it.
- **Do NOT touch `mobile/`.** If the client needs to render a 402 differently, disclose it.
- **Do not change the deprecated `/v1/coach/*` shim's behaviour** beyond what it inherits by calling
  the same handler. DEF186 deliberately left it in place; breaking old TestFlight builds is a support
  call, not this lane's.
- **Do not implement the "5 free 1-on-1s per month" mechanic.** Whether that is a separate free-turn
  counter or just the credit allowance doing its job is **unresolved** — see acceptance 5.

## Acceptance

1. **A test that FAILS against current code** proving a 1-on-1 turn debits through `spend()`. Write
   it first, watch it go red.
2. **The 402 path exists and is tested at a non-zero price.** Parameterise the price in the test so
   `InsufficientCredits` → `402` is proven even though alpha runs at 0. **This is the criterion that
   makes the 0 safe** — without it, the whole spine is untested until the day someone flips the price.
3. **The alpha price of 0 is declared, discoverable, and exercised.** A test asserts that at price 0
   a turn still writes its ledger row and still returns 200 — a charge of zero, not a skipped charge.
4. **Idempotency/duplication:** state in your hand-off what happens if the LLM call fails *after* the
   spend. Charged-then-failed is a real user-visible wrong on a money path even at price 0, because
   the ledger row persists. Say what you did and why.
5. **Report, do not implement, on the "5 free 1-on-1s" question.** `credits.md:123` describes a
   mechanic that may be a separate counter or may just be the allowance. Read it, say which you
   believe it is and what the evidence is, and stop. It is Saiful's call and I will take it to him.
6. **Mutations:** revert the spend call, show the test goes RED. Report honestly if it comes back GREEN.
7. Full suite from repo root: `"./backend/.venv/bin/python" -m pytest backend/tests/unit/ -q`.
   **`python` is not on PATH. Never use `-x`.** Baseline **1812**; finish `>= 1812` with zero failures
   **except** `test_cr084_revenuecat_webhook.py::test_test_store_expiration_revokes_to_floor_pass`,
   which is **another track's uncommitted work in the shared checkout, not yours** — verified passing
   23/23 at a clean HEAD. Do not touch `webhooks.py` or `scripts/`.
   **Do not pipe pytest through `tail`/`head` and read the exit code.** Read the `N passed, M failed` line.

## Registers

Flip `DEF113` to `fixed` only if the spine is genuinely complete; if the "5 free" question leaves
residue, leave it `open` and name what remains. **Put the note in the DESCRIPTION column — the status
cell must stay a bare token** (DEF203). Then `python3 scripts/registers/gen_registers.py gen def` and
commit both **in the same commit** (DEF159). **Explicit pathspec.**

Note in the row that **CR090's 1-on-1 half is unblocked** by this landing — that dependency is why
the lane exists as much as the revenue is.

## Hand-off delivery

**Write your hand-off file EARLY and keep updating it.** Write
`orchestration/dispatch/lanes/BE-DEF113.coder.api.md` with `STATUS: READY_FOR_AUDIT (round 1)`; get it
onto `main` AND push your lane branch to origin (**DEF175**).

**If you can measure that an instruction here is wrong, stop and disclose with the measurement.**
This touches a money path; a confident wrong answer is worse than a disclosed gap.

ASSIGNED: coder.api round 1
DISPATCH: ACCEPTED
