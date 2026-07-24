STATUS: READY_FOR_AUDIT (round 1)

<!-- coder-owned lane file for CR084-BE, written by the Architect on the coder.api build's behalf
(the ephemeral coder.api instance was briefed NOT to touch orchestration/). State machine driven by
the STATUS line above (byte-exact). See orchestration/dispatch/loop_prompts/CODER.md. -->

# CR084-BE — coder.api lane (RevenueCat webhook → server-authoritative entitlement/credit sync)

**Item:** GTM M1 final slice, backend half. The RevenueCat webhook that turns a verified store
purchase into a plan transition + credit grant, on top of the CR039 credit gate. `GATE: independent`
(D-5: money/entitlements).

**Spec:** [`docs/forward_planning/CR084_revenuecat_integration/CR084_revenuecat_integration.md`](../../../docs/forward_planning/CR084_revenuecat_integration/CR084_revenuecat_integration.md) (§Scope → CR084-BE, §Acceptance).

**Built SHA:** `f1e7a1613ba4eff25fa716daad7e34a8ec3034f7` on `lane/CR084-BE.coder.api` (branched from merge-base `668c6c4`).

**Changed (9 files, +956 / −0 — all coder.api-owned):**
- `backend/app/api/webhooks.py` — **NEW (297L):** `POST /v1/webhooks/revenuecat`. `_verify_secret` fails
  **closed** (`hmac.compare_digest` constant-time; bad/absent header → 401) and **loud** (unset secret →
  503 + `logger.error("revenuecat_webhook_secret_unset")`, in ALL envs — stricter than the spec's
  "live-only", satisfies never-silent-accept / never-silent-reject-all). One DB transaction does dedup-
  insert + grant + `subscription_events` audit row together; a replayed RC event id hits the
  `revenuecat_events` unique constraint → `IntegrityError` caught → 200 no-op (idempotent, DB-constraint
  not a SELECT-then-INSERT race — DEF039). Event map: sub `INITIAL_PURCHASE`/`RENEWAL`/`PRODUCT_CHANGE`
  → plan+allowance; `NON_RENEWING_PURCHASE` → credit pack; `CANCELLATION`/`EXPIRATION`/`BILLING_ISSUE`
  → revoke-to-base; unmapped/unknown-user handled explicitly.
- `backend/app/api/billing.py` — **NEW (41L):** auth-gated `GET /v1/billing/identity` → `{user_id,
  app_user_id}` (both == `users.id`) so the mobile SDK's `Purchases.logIn(...)` sets RC `app_user_id`
  to our UUID. (Architect note: this is the CR084-MOBILE identity contract — MOBILE reads this.)
- `backend/app/services/credit_service.py` (+104) — `set_plan_and_grant_allowance(session, user, plan)`
  (Trader 150 / Floor Manager 500, period-guarded so an active `trial_trader` grant isn't doubled),
  `add_credit_pack(session, user, amount)` (60/300/850), `revoke_to_base(session, user)` → floor_pass
  (or trial if still active). Reuses the CR039 allowance mechanism — no parallel ledger.
- `backend/app/db/models.py` (+30) — new `revenuecat_events` dedup table (unique on RC event id) +
  the plan/credit fields it grants against. **coder.api is sole schema owner.**
- `backend/alembic/versions/a1c2e3f40020_revenuecat_events.py` — **NEW (49L):** migration for the above,
  chained off head `c5d6e7f80019`.
- `backend/app/core/config.py` (+11) — `revenuecat_webhook_secret: str = ""`.
- `docker-compose.yml` (+6) — `REVENUECAT_WEBHOOK_SECRET` forwarded in the `api-alpha` block
  (`test_config_compose_parity.py` gate — the DEF038/DEF063 shipped-dark trap avoided).
- `backend/app/main.py` (+4) — mounts both new routers.
- `backend/tests/unit/test_cr084_revenuecat_webhook.py` — **NEW (414L, 23 tests):** signature fail-closed
  (unsigned/bad-secret refused — proven RED-shaped), unset-secret 503, idempotent replay, each
  event→grant mapping, `subscription_events` written, unknown-user + unmapped-event paths.

**Key decisions (coder):**
- **Identity endpoint:** dedicated `GET /v1/billing/identity` over folding into auth/me — one
  purpose-named call, `app_user_id` explicit, unambiguous RC linkage contract.
- **Product IDs:** entitlement→plan and pack→credits maps kept as module constants in `webhooks.py`
  with the spec's canonical keys (subs key off the RC *entitlement* `trader`/`floor_manager`, packs off
  `product_id`), NOT 9 env settings — only the one secret is env-gated. Reasonable; the auditor should
  confirm this doesn't hide a config-parity gap (it does not — the secret is the only gated value).
- **Fail-closed 503 in all envs** (not just live) — strictly louder/safer.

**FLAGGED FOLLOW-UP (out of CR084-BE scope — needs its own item):** `MergeService.execute()` does NOT
carry RC/entitlement state on anon→claimed account merge. Three concrete gaps: (1) it doesn't re-key
`subscription_events` / new `revenuecat_events` rows (orphan `user_id` dangles after the orphan is
deleted); (2) it doesn't carry `plan`/`credit_balance`/period fields orphan→adopter, so a **pre-claim
anonymous purchase's plan+credits are lost on merge**; (3) RC's `app_user_id` is the deleted orphan
UUID, so post-merge `RENEWAL`/`EXPIRATION` webhooks arrive for a deleted user → loud 404. **Must be
resolved before anonymous purchase is enabled end-to-end** — Architect to mint a DEF/CR. Not a blocker
for this lane's own scope (the webhook + grant path).

**Out of scope respected:** no room cluster / `trading_math` / `orchestration/` / forbidden-file edits.
Built + tested against MOCKED RC payloads only — no fabricated keys/secrets/product IDs.

**Tests:** coder ran full `tests/unit/ -q` → **1099 passed, exit 0** (141s). **Architect re-ran
independently** from the worktree at `f1e7a161` with the main venv → **1099 passed, 4 warnings
(pre-existing FastAPI `HTTP_422` deprecations, not introduced here), exit 0** (131.7s).

## Definition of Done

| Item | Status |
|---|---|
| `POST /v1/webhooks/revenuecat` verifies secret, fails closed on bad/absent signature | done |
| Idempotent on RC event id via DB unique constraint (replay → single grant) | done |
| Sub purchase → plan + monthly allowance; credit pack → credits, no plan change | done |
| Cancellation/expiration → revoke to floor_pass (or trial via effective_plan) | done |
| Every transition → `subscription_events` row (`source="revenuecat"`) | done |
| `revenuecat_webhook_secret` forwarded in compose → parity test green | done |
| RC `app_user_id` = users.id identity contract (`GET /v1/billing/identity`) | done |
| No forbidden-path / room-cluster edits; full suite green (Architect-verified) | done (1099, exit 0) |
| Anon→claimed merge carries RC/plan/credit state | **DEFERRED — flagged follow-up, own item** |
