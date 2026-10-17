<!--
CR261 — the manual-ops catalog for the subscription lifecycle (Saiful 2026-10-18:
"create a CR document that details the manual handling we need to do and the
cases that may trigger them").

Companion to, not a replacement for, CR084's provisioning runbook
(docs/forward_planning/CR084_revenuecat_integration/rc_production_runbook.md) —
that document gets billing *live*; this one covers what a human must do when the
automatic path (store → RevenueCat webhook → backend grant) breaks or hits a case
no code path handles. Each entry: trigger (what fires it), detection signal, and
the manual action.

Revenue state is server-authoritative (backend/app/api/webhooks.py); every
automatic transition writes one subscription_events row (source="revenuecat").
That ledger is the primary reconcile tool for most entries below.
-->

# CR261 — Subscription manual-ops catalog

**Status:** proposed · **Minted:** 2026-10-18 · **Author:** Kimi (AT:K6)
**Scope:** billing / subscriptions / entitlements (CR084 stack)

## Why this exists

The happy path is fully automatic: store flips a subscription → RevenueCat POSTs
to `/v1/webhooks/revenuecat` → the backend applies the plan in one DB
transaction. Nothing below should ever fire in steady state. Each entry exists
because the failure mode is either (a) a deliberate loud refusal (CR040 — refuse
rather than silently mis-grant), or (b) a store-side reality no webhook covers
(refunds, chargebacks, pauses). The loud refusals are the detection mechanism —
**every entry below announces itself in the api logs first.**

Baseline detection commands (run from the Mac):

```bash
ssh melehost "docker logs ami_api_alpha --since 24h 2>&1 | grep -i revenuecat"
```

## The catalog

### 1. Unmappable purchase — webhook 422

- **Trigger:** a subscription event whose `entitlement_ids` and `product_id`
  match neither `_ENTITLEMENT_TO_PLAN` nor the `trader_*` / `floor_manager_*`
  prefixes (`webhooks.py::_entitlement_plan`); or a `NON_RENEWING_PURCHASE`
  whose product_id is not in `_CREDIT_PACKS` (`_pack_credits`). Typical causes:
  an entitlement/product typo in the RC dashboard, or a new store product added
  without updating the code mapping.
- **Detection:** RC dashboard shows the delivery as failed; log line carries
  the offending ids; user paid and got nothing.
- **Manual action:** fix the mapping — dashboard side (wrong entitlement
  attachment) or code side (new product → update the dicts + promote). Then
  **resend the failed event from the RC dashboard** (each delivery can be
  replayed); do not hand-edit `users.plan` if replay is possible, so the
  `subscription_events` ledger stays single-sourced.

### 2. Webhook signature mismatch — 401

- **Trigger:** the RC dashboard Authorization header diverges from
  `REVENUECAT_WEBHOOK_SECRET` — most commonly a `Bearer ` prefix added by hand.
- **Detection:** every delivery 401s; RC retries for ~a week, then gives up.
- **Manual action:** correct the Authorization field in RC → Project Settings →
  Integrations → Webhooks (raw secret, no prefix). If the secret itself was
  rotated: update `infra/alpha.env`, re-promote/recreate the container, then
  update the dashboard value to match.

### 3. Webhook secret unset — 503

- **Trigger:** `REVENUECAT_WEBHOOK_SECRET` missing from the api container env.
  `docker-compose.yml` parity is test-enforced, so this means an env file
  regression or a manual container recreate without the env.
- **Detection:** `logger.error("revenuecat_webhook_secret_unset")` + all
  deliveries 503.
- **Manual action:** restore the var in `infra/alpha.env`, recreate
  `ami_api_alpha`, re-send RC's test event, confirm 2xx.

### 4. Sandbox transaction reaching production — 403

- **Trigger:** an event with `environment: "SANDBOX"` arrives while
  `settings.env == "prod"` (`webhooks.py` CR084-ALPHA guard). Legitimate during
  alpha (granted by design there); in production it means either a sandbox
  tester slipped onto the production app or a store/RC misconfiguration.
- **Detection:** `logger.error("revenuecat_webhook_sandbox_in_production")`.
- **Manual action:** identify the source (the log line carries app_user_id +
  product_id). If it was a real sandbox tester on the prod build — no state to
  fix, the refusal did its job. If a production user somehow holds a sandbox
  receipt, that's a store-side problem: reconcile with Apple/Google, and only
  then grant manually if the purchase is confirmed real.

### 5. Unknown user — 404

- **Trigger:** `app_user_id` is not a live `users.id` and the merge-alias chain
  (`_follow_merge_alias`, DEF099) finds no surviving adopter. Causes: a user
  deleted their account after paying, or an identity flow that minted a fresh
  id instead of logging in with `/v1/billing/identity`.
- **Detection:** `logger.error("revenuecat_webhook_unknown_user")` + 404.
- **Manual action:** reconcile identity first (find the paying user row, check
  `subscription_events` for prior rows under another id). If the account is
  genuinely gone, decide policy — refund via the store is the usual answer; a
  manual grant onto a new id strands entitlements on an orphan. Log the
  decision in `subscription_events` with `source="manual"`.

### 6. Event lost after RC retry exhaustion

- **Trigger:** the public tunnel or api container is down longer than RC's
  retry window, or repeated 5xx from a bug. The subscription flipped in the
  store; we never applied it.
- **Detection:** no automatic signal — this is the one case that fails
  *silently on our side*. Reconcile proactively: subscription_events ledger vs
  RC dashboard's customer history; or a user reports "I paid / I cancelled but
  the app disagrees."
- **Manual action:** from the RC dashboard, resend/replay the missed event for
  that customer. Verify the ledger afterwards (`subscription_events` row with
  `note=<rc event id>` appears).

### 7. Refunds and chargebacks — no webhook covers these

- **Trigger:** Apple/Google issue a refund or a chargeback wins. RevenueCat
  emits **no event** for either; our `CANCELLATION`/`EXPIRATION` handlers never
  fire. The user keeps the paid plan and credits they no longer paid for.
- **Detection:** store consoles (App Store Connect / Play Console orders),
  RevenueCat's charts (refund-adjusted revenue vs our ledger), support reports.
- **Manual action:** revoke manually — set `users.plan = floor_pass` and
  re-baseline the allowance through the same path `revoke_to_base()` takes, and
  write a `subscription_events` row (`source="manual"`, note=store order id).
  **Gap:** there is no admin endpoint for this today; the action is a
  DB/script step on melehost. A `/v1/admin/billing/revoke` route (static-bearer
  gated, like the rest of `/v1/admin/*`) is the natural follow-up CR.

### 8. Google Play pause (`SUBSCRIPTION_PAUSED`)

- **Trigger:** Play's pause feature, if ever enabled on the subscription base
  plans. Our webhook deliberately ignores the event type (`is_actionable`
  false → recorded + 200).
- **Detection:** ignored-event log lines; a paused subscriber still reads as
  entitled until `EXPIRATION` arrives at the pause boundary.
- **Manual action:** none if pauses stay disabled in Play Console (current
  posture — keep them disabled). If ever enabled, the correct handling is a CR
  (map pause → grace state), not an ops workaround.

### 9. Family Sharing / transfers (`TRANSFER`)

- **Trigger:** Apple Family Sharing sharing a subscription, or Play account
  transfers. Both arrive as `TRANSFER`, which we ignore.
- **Detection:** ignored-event log lines.
- **Manual action:** policy decision, not ops: sharing is not in the tier
  design (`tiers_and_pricing.md`). Keep Family Sharing off on the App Store
  product. If a transfer strands a payer, handle under entry 5/6.

### 10. Paid but still revoked after a billing recovery

- **Trigger:** a user hits `BILLING_ISSUE` (auto-revoked at expiry by design),
  then pays again inside the store's recovery window. The store resumes the
  subscription; `RENEWAL`/`INITIAL_PURCHASE` re-grants automatically — *unless*
  the resume event was one of the lost-event cases (entry 6).
- **Detection:** user report; ledger shows `plan_changed → floor_pass` with no
  later grant row while the store shows the subscription active.
- **Manual action:** confirm the subscription is active in the RC dashboard,
  then replay the missed event (entry 6 playbook). Never grant from the app's
  say-so alone.

### 11. Comp / support grants

- **Trigger:** a deliberate decision to give a user a paid tier (review
  outreach, service recovery, beta contributor).
- **Manual action:** set `users.plan` + allowance via the credit_service path
  on melehost and write a `subscription_events` row (`source="manual"`,
  note=reason). This bypasses RC — RC does not know about it, so a later real
  `EXPIRATION` from an unrelated sandbox/real purchase will still revoke
  correctly. Same gap as entry 7: no admin endpoint exists yet.

## Standing posture

1. **The ledger wins.** Before any manual mutation, read `subscription_events`
   for the user; after it, write a `source="manual"` row. Every entry above
   says so because the ledger is the only place a support engineer can see the
   full truth.
2. **Replay beats repair.** RC can resend any event; prefer that over
   hand-editing state so the audit chain stays store-sourced. Hand-edits are
   only for the no-webhook cases (7, 11).
3. **Watch the loud refusals.** Entries 1–5 each log an unmistakable error
   line. A daily grep (or the existing watchdog pattern) over
   `docker logs ami_api_alpha | grep revenuecat` turns all five into
   same-day tickets instead of silent drift.
4. **Known gaps to file as CRs (not fixed here):** admin revoke/grant endpoint
   (entries 7, 11); proactive ledger-vs-RC reconcile job (entry 6).

## Cross-references

- Provisioning runbook: [CR084 rc_production_runbook.md](../CR084_revenuecat_integration/rc_production_runbook.md)
- Webhook implementation: `backend/app/api/webhooks.py`
- Plan/allowance mechanics: `backend/app/services/credit_service.py`,
  `backend/app/services/entitlements.py`
- Tier design (upgrade/downgrade semantics): [tiers_and_pricing.md](../../initial_specs/06_monetization/tiers_and_pricing.md)
