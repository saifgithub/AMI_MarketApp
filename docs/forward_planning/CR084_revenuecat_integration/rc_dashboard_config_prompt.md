# Prompt — RevenueCat dashboard configuration for AMI Trade alpha (CR084 / DEF100)

Hand this to the agent that owns revenue management. It is self-contained: every
identifier, price and endpoint the task needs is below. The code side is already done and
verified — this is dashboard configuration only.

Written 2026-07-30 (AT:R65). If the values below disagree with
`backend/app/api/webhooks.py` or `mobile/lib/services/billing/purchase_models.dart`, the
code wins and this doc is stale — say so rather than making the code match the doc.

---

## The prompt

> You are configuring **RevenueCat** for **AMI Trade**, a simulation-only AI
> trading-education mobile app (Flutter + FastAPI) currently in closed alpha. Your task is
> dashboard configuration only — **do not write or modify any application code.**
>
> ### Context you need
>
> The app's billing code is complete and deployed. What is missing is the RevenueCat-side
> configuration, so no purchase can currently complete. Two things are unconfigured: the
> product catalog, and the webhook that tells our backend a purchase happened.
>
> We are using **RevenueCat's Test Store** for alpha. Purchases are simulated by
> RevenueCat — the paywall, the purchase, the webhook, the entitlement grant and the credit
> top-up all execute for real, but no money moves and no App Store Connect / Play Console
> product is required. The API keys already in place all begin with `test_`.
>
> **Do not create, request, rotate or use production keys (`appl_…`, `goog_…`), and do not
> touch App Store Connect or Google Play.** Those belong to a later phase, tracked
> separately.
>
> ### Task 1 — Products
>
> Create **seven** products in the Test Store. **The identifiers must match exactly** —
> both our backend and our mobile client key off these literal strings, so a typo or a
> pluralisation silently breaks the purchase rather than erroring.
>
> | Product ID | Type | Price (USD) |
> |---|---|---|
> | `trader_monthly` | auto-renewing subscription, 1 month | 14.99 |
> | `trader_annual` | auto-renewing subscription, 1 year | 129.00 |
> | `floor_manager_monthly` | auto-renewing subscription, 1 month | 34.99 |
> | `floor_manager_annual` | auto-renewing subscription, 1 year | 299.00 |
> | `credits_starter` | consumable / non-renewing | 4.99 |
> | `credits_standard` | consumable / non-renewing | 19.99 |
> | `credits_power` | consumable / non-renewing | 49.99 |
>
> ### Task 2 — Entitlements
>
> Create exactly **two** entitlements. The identifiers must match exactly; our backend maps
> entitlement → plan off these strings and rejects anything it does not recognise.
>
> | Entitlement ID | Attach these products |
> |---|---|
> | `trader` | `trader_monthly`, `trader_annual` |
> | `floor_manager` | `floor_manager_monthly`, `floor_manager_annual` |
>
> **The three `credits_*` products must NOT be attached to any entitlement.** They are
> one-off credit packs, not access tiers — our backend handles them on a separate code path
> keyed to the product ID, and attaching one to an entitlement would wrongly upgrade the
> user's plan.
>
> ### Task 3 — Offering
>
> Create one offering, set it as **current**, and add all seven products to it as packages.
> Our client reads `offerings.current.availablePackages` and classifies each package by its
> product identifier, so anything not in the current offering is invisible to the app.
>
> ### Task 4 — Webhook
>
> Under **Project Settings → Integrations → Webhooks**:
>
> - **URL:** `https://api-alpha.agenticmarketintel.ai/v1/webhooks/revenuecat`
> - **Authorization header value:** the shared secret held in `infra/alpha.env` as
>   `REVENUECAT_WEBHOOK_SECRET` (64 characters). Ask Saiful for it — it is not in this
>   document and must not be pasted into chat logs or committed anywhere.
>
> **Enter the secret raw, with no `Bearer ` prefix and no other decoration.** Our endpoint
> does an exact constant-time comparison of the whole `Authorization` header against the
> secret. A `Bearer ` prefix produces `401 invalid webhook signature` — this has already
> caught one person, so verify the field contains only the 64 characters.
>
> Send these event types at minimum: `INITIAL_PURCHASE`, `RENEWAL`, `PRODUCT_CHANGE`,
> `CANCELLATION`, `EXPIRATION`, `BILLING_ISSUE`, `NON_RENEWING_PURCHASE`. The first three
> grant or change a plan, the next three revoke it, and the last is how credit packs
> arrive.
>
> ### How to verify you are done
>
> 1. **Webhook reachable.** RevenueCat's dashboard has a "send test event" button. Fire it
>    and confirm RevenueCat records a **2xx**. A `401` means the Authorization field is
>    wrong (almost always a `Bearer ` prefix); a `503` means our backend has no secret set,
>    which is our problem, not yours — report it.
> 2. **Offering resolves.** Confirm the current offering returns all seven packages.
> 3. **Identifiers exact.** Re-read the seven product IDs and two entitlement IDs character
>    by character against the tables above. This is the single highest-risk part of the task
>    because every mistake in it fails silently rather than loudly.
>
> ### Report back
>
> - The seven product IDs as actually created (copy them from the dashboard, do not retype
>   from this prompt — the point is to catch a divergence).
> - The two entitlement IDs and which products are attached to each.
> - The offering identifier and whether it is set as current.
> - The webhook test-event HTTP status RevenueCat recorded.
> - Anything you could not do, and why. **A partial configuration reported honestly is far
>   more useful than a complete one claimed.** If a product type is unavailable in the Test
>   Store, say so rather than substituting a different type.
>
> ### Do not
>
> - Do not modify any application code, in this repo or elsewhere.
> - Do not create production (`appl_`/`goog_`) keys or touch App Store Connect / Play Console.
> - Do not rotate, regenerate or reveal any existing key or secret.
> - Do not attach `credits_*` products to an entitlement.
> - Do not rename or "tidy" the identifiers. They are contracts with shipped code.

---

## Reference — what happens after this lands (for the requester, not the agent)

Once configured, a `trader_monthly` purchase should produce:

| Step | Expected |
|---|---|
| Webhook received | `POST /v1/webhooks/revenuecat` → 200 |
| Plan | `Plan.TRADER` |
| Credit balance | reset to the plan allowance, **150** (`credit_service.ALLOWANCE`) |
| `credits_starter` purchase | **+60** credits, plan unchanged |
| `credits_standard` | +300 · `credits_power` +850 |

Verify from the Mac with:

```bash
ssh melehost "docker logs ami_api_alpha --tail 50 2>&1 | grep -i revenuecat"
```

Worth testing deliberately once the basics pass: purchase **while anonymous**, then claim
the account. That exercises the DEF099 anon→claimed alias hop, which has never run live.

Not covered by the Test Store, still owed by DEF100 before real money: real StoreKit / Play
Billing, receipt validation, price localisation, restore-purchases across real store
accounts, store-driven renewal and cancellation, and the Apple + Google paid-app agreements.
