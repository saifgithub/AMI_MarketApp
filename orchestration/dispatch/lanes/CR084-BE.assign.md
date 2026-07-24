<!-- dispatch assign lane — Architect-owned. CR052. CR084 backend sub-lane. -->
# CR084-BE — assign (RevenueCat webhook + server-authoritative entitlement/credit sync)

KIND: code
INSTANCE: coder.api
ACCEPTANCE: docs/forward_planning/CR084_revenuecat_integration/CR084_revenuecat_integration.md (§Scope → CR084-BE, §Acceptance)
DEPENDS-ON: —    <!-- contract PRODUCER; CR084-MOBILE depends on this, not the reverse. -->
GATE: independent    <!-- D-5: money + entitlements + store-facing. A wrong grant is real dollars and a real trust breach. Route to Saiful's pre-spawned independent auditor. -->
HOT-FILES: `backend/app/api/webhooks.py` (NEW router, mount in `main.py`), `backend/app/services/entitlements.py` + `credit_service.py` + `mandate_store.py` (all coder.api-owned), `backend/app/core/config.py` (new `revenuecat_webhook_secret` setting), `docker-compose.yml` api-alpha block (forward the secret — `test_config_compose_parity.py` gate), `backend/app/db/models.py` ONLY if a webhook-event dedup table is needed (coder.api is sole schema owner; add an Alembic migration). Does NOT touch the room cluster.

## Build (this is the M1 final slice — CR039 already landed the credit gate)

Read the CR084 spec §"Why now" first: CR039 (AT:R60) already built the credit ledger
(`credit_service.py` — `spend`/`refund`/`balance_for`), the 402 wall on Convene the Room, and
plan-drift re-grants (`effective_plan` at every `pick_tier()`). **Do not rebuild any of that.** This
lane adds only the RevenueCat → backend grant path.

1. **`POST /v1/webhooks/revenuecat`** (new `api/webhooks.py`, mounted in `main.py`). Verify RC's
   `Authorization` header against `settings.revenuecat_webhook_secret`. **Fail closed:** bad/absent
   signature → 401, never grant. Unset secret in a live (non-test) env → refuse loudly (503 + log), per
   CR040 degrade-loudly — NOT silent-accept, NOT silent-reject-all.
2. **Idempotency:** dedup on RC's event `id` via a DB constraint, not a SELECT-then-INSERT race
   (DEF039). RC retries on any non-2xx, so a replayed `INITIAL_PURCHASE` must not double-grant credits.
3. **Event → grant mapping** (spec §CR084-BE.2):
   - sub `INITIAL_PURCHASE`/`RENEWAL`/`PRODUCT_CHANGE` → set `users.plan` to the entitlement's tier
     (`trader`→`Plan.TRADER`, `floor_manager`→`Plan.FLOOR_MANAGER`); grant that tier's monthly credit
     allowance for the new period **through the existing `credit_service` allowance mechanism** (no
     parallel ledger). Don't double-grant if an active `trial_trader` already granted this period.
   - `NON_RENEWING_PURCHASE` (credit pack) → grant the pack's credits (`credits_starter` 60 /
     `credits_standard` 300 / `credits_power` 850). **No plan change.**
   - `CANCELLATION`/`EXPIRATION`/`BILLING_ISSUE` → revoke → effective plan falls back to `floor_pass`
     (or `trial_trader` if trial still active — resolve via `effective_plan`).
   - Every transition → a `subscription_events` row (`event_type`, `from_value`, `to_value`,
     `source="revenuecat"`, `note=<rc event id>`). Table exists (`models.py:580`).
4. **RC `app_user_id` = our `users.id` (UUID).** Expose an identity the mobile SDK logs in with (small
   `GET /v1/billing/identity`, or fold into auth/me — your call). Anonymous-first: a pre-claim anon
   purchase must survive claim/merge — check `MergeService` re-keys RC/`subscription_events` state, or
   note the gap in the hand-off.
5. **Entitlement read stays server-authoritative** — premium routes keep reading
   `entitlements.effective_plan_for_user(...)`; this lane makes the webhook the *writer*.

## Out of scope
Mobile SDK/paywall (that's CR084-MOBILE). Pricing decisions (locked in `06_monetization/`). Ads.
Winzip/Share-a-Premium funnel mechanics (separate CRs) — but don't break CR039's cooldown path.

## Saiful-liaison dependency (does NOT block reaching READY_FOR_AUDIT)
RC webhook secret + product IDs are Saiful's. **Do not fabricate them.** Build + unit-test against
**mocked RC webhook payloads** (one fixture per event type). Live-device verification waits on Saiful.

## Tests
`cd backend && "/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest tests/unit/ -q`
(worktrees have no `.venv`). New tests: signature fail-closed, idempotent replay, each event→grant
mapping, `subscription_events` written, compose-parity green for the new secret. Prove fail-closed RED
first (unsigned call must be refused), then the happy path.

## Delivery
Push to `lane/CR084-BE.coder.api`, never `main`. Hand-off:
`orchestration/dispatch/lanes/CR084-BE.coder.api.md` (`STATUS: READY_FOR_AUDIT (round 1)`) +
`orchestration/audit/cr/CR084-BE.architect.md` (`SUBMITTED: round 1`). Commit tag `(AT:coder.api CR084)`.

DISPATCH: OPEN

ASSIGNED: coder.api round 1
