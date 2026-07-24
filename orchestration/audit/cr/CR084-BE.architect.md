<!--
CR084-BE.architect.md — architect lane file (Architect owns). State is derived from the round
numbers here vs CR084-BE.auditor.md (see orchestration/audit/PROTOCOL.md). Bump `SUBMITTED: round N`
on every resubmit. Do NOT edit CR084-BE.auditor.md — that is the independent auditor's file.

GATE: independent. Routed to the pre-spawned independent auditor (track U), NOT an architect-spawned
agent. If no independent auditor is running, the lane HOLDS here until one signs off (the Architect
does not spawn its own auditor — separation of duties).
-->

# CR084-BE — audit lane (architect)

**Item:** CR084-BE — the RevenueCat webhook that turns a verified store purchase into a
server-authoritative plan transition + credit grant, on top of the CR039 credit gate (GTM M1 final
slice, backend half).

**Gate:** independent (D-5 — money, entitlements, store-facing. A wrong or forged grant is real
dollars and a real trust breach. The security posture — signature verification, fail-closed, idempotent
— IS the deliverable; verify it adversarially.)

**Built SHA (round 1):** `f1e7a1613ba4eff25fa716daad7e34a8ec3034f7` on `lane/CR084-BE.coder.api`
(branched from merge-base `668c6c4`; **not yet integrated to main** — integration waits on COMPLETE).

**depends-on:** CR039 (credit gate — landed on main; this builds on `credit_service`'s allowance
mechanism). No un-landed dependency. CR084-MOBILE `DEPENDS-ON` *this* (identity + refresh contract).

## What changed / why

| SHA | Files | What |
|---|---|---|
| `f1e7a161` | `webhooks.py` (NEW 297L), `billing.py` (NEW 41L), `credit_service.py` (+104), `models.py` (+30), migration `a1c2e3f40020` (NEW), `config.py` (+11), `docker-compose.yml` (+6), `main.py` (+4), `test_cr084_revenuecat_webhook.py` (NEW 414L / 23 tests) | RC webhook: constant-time secret check (fail-closed 401 / unset→503 loud), single-transaction dedup+grant+audit (idempotent via `revenuecat_events` unique constraint), event→grant map (sub→plan+allowance, pack→credits, cancel/expire→revoke), `subscription_events` trail, `GET /v1/billing/identity` for RC `app_user_id`=users.id. |

## Architect pre-check (verification done before submitting — NOT the independence gate)

- **Scope / forbidden paths:** diffed against the true merge-base `668c6c4`. Real change set =
  **exactly 9 files, +956/−0**, all coder.api-owned. Grep-clean of room cluster
  (`room_runner`/`room_prompts`/`agent_*`/`overlay_*`/`brief_engine`), `trading_math/`,
  `orchestration/`, `settings.local.json`, `uv.lock`, `Archive.zip`, `qa/appium/`, `docs/`. Not pushed
  to `main`.
- **Full suite:** re-run independently from the worktree at `f1e7a161` with the main venv →
  **1099 passed, 4 warnings (pre-existing `HTTP_422` deprecations, not introduced here), exit 0**
  (131.7s). +23 over baseline, nothing broken.
- **Security core eyeballed:** `hmac.compare_digest` (constant-time), unset-secret 503+log (CR040),
  bad→401 (fail-closed), idempotency is an `IntegrityError`-on-unique-insert inside the grant
  transaction (not a check-then-act race — DEF039). Migration chained off head `c5d6e7f80019`.

**This pre-check is the *integrator's* readiness check, not independent verification.** Per the
standing rule (Architect spawns coders only; the independent auditor is Saiful-pre-spawned), the
COMPLETE that matters comes from the independent auditor's `CR084-BE.auditor.md`, not from here.

## Suggested adversarial focus for the independent auditor

1. **Forge a grant.** Can any code path reach `set_plan_and_grant_allowance` / `add_credit_pack`
   WITHOUT passing `_verify_secret` first? Confirm the secret check is unconditional and precedes every
   grant, and that a `""` secret cannot accidentally match a `""`/absent presented header (it returns
   503 before the compare — verify there's no env where an empty secret silently authorizes).
2. **Break idempotency.** Two concurrent deliveries of the same RC event id — does the DB unique
   constraint (not app-code) guarantee a single grant? Mutate the dedup to a SELECT-then-INSERT and
   confirm a test goes RED (prove the constraint is load-bearing, not decorative).
3. **Double-grant across trial.** A `trial_trader` user whose `INITIAL_PURCHASE` lands in the same
   period — is the monthly allowance granted twice? Verify the period guard.
4. **Revoke correctness.** `EXPIRATION` for a user whose trial is still active — does `effective_plan`
   keep them on `trial_trader` rather than dropping to `floor_pass` early? And does a credit-pack
   `NON_RENEWING_PURCHASE` correctly NOT touch `plan`?
5. **The MergeService gap** (coder-flagged): confirm it is genuinely out of THIS lane's scope (webhook
   grant path) and not masking a defect in the grant logic itself. It should become its own item before
   anon purchase ships — but it is not a CR084-BE blocker.
6. **Fail-closed 503-in-all-envs:** confirm the unit env sets the secret for happy-path tests and that
   removing it makes the endpoint 503 (loud), never 200.

## Tests run (architect)

- `pytest tests/unit/ -q` (worktree @ `f1e7a161`, main venv) → **1099 passed, exit 0.**

SUBMITTED: round 1
