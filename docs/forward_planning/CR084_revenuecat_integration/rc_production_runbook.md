<!--
CR084 / DEF100 — the live provisioning instruction for RevenueCat.

Written 2026-08-20 (AT:R73). SUPERSEDES rc_dashboard_config_prompt.md, which
targeted RevenueCat's Test Store — a route DEF282 proved unusable for us (the RC
SDK calls fatalError on a test_… key in any non-DEBUG build, and every build we
ship is a release build). This document is the real-store route: App Store
Connect + Play Console products, real appl_…/goog_… keys, and free purchases via
Apple Sandbox testers / Play license testers.

Saiful executes this. It is account + dashboard work; no code changes are part
of it. Every identifier below is a contract with shipped code — if this document
ever disagrees with backend/app/api/webhooks.py or
mobile/lib/services/billing/purchase_models.dart, the code wins and this doc is
stale; say so rather than making the code match the doc.
-->

# RevenueCat — production provisioning runbook (CR084 / DEF100)

**Status of the code (verified 2026-08-20, not read off a doc):**

| Thing | State |
|---|---|
| `POST /v1/webhooks/revenuecat` | Shipped, mounted, fails closed. [`backend/app/api/webhooks.py`](../../../backend/app/api/webhooks.py) |
| Webhook shared secret on alpha | **Present** — `docker exec ami_api_alpha printenv REVENUECAT_WEBHOOK_SECRET` returns 64 chars. A real RC test event would 2xx today, not 503 |
| SANDBOX-in-prod guard (CR084-ALPHA) | Landed — `webhooks.py:270-288` |
| Anon→claimed billing carry-over | DEF099 **fixed**; `backend/app/services/revenuecat_client.py` performs the RC alias transfer |
| Mobile SDK | `purchases_flutter ^10.4.3`, behind the `PurchaseService` seam |
| Mobile billing switch | **OFF** — `mobile/lib/state/purchase_providers.dart:42` returns `DisabledPurchaseService` (DEF282). The paywall renders the info-not-buy card |
| Keys in `infra/alpha.env` | All three SDK keys are `test_…` (Test Store) |
| **RevenueCat dashboard** | **Never configured.** Probing the offerings endpoint with our own public key returns RC's stock template — offering `default`, packages `$rc_monthly` / `$rc_annual` / `$rc_lifetime` → products `monthly` / `yearly` / `lifetime`. None of our seven product IDs exist; neither entitlement exists |

**Nothing is blocked on code.** What is missing is entirely account and dashboard work.

---

## Why this replaced the Test Store route

RevenueCat's SDK does **not** degrade on a `test_…` key outside a DEBUG build. It calls `fatalError`
on purpose, so a Test Store key can never reach the App Store. From the vendored source,
`mobile/ios/Pods/RevenueCat/Sources/Purchasing/Configuration.swift:517-532`:

```swift
// The `BYPASS_SIMULATED_STORE_RELEASE_CHECK` compilation flag opts out of the Release-build
// safeguard. …
#if !DEBUG && !BYPASS_SIMULATED_STORE_RELEASE_CHECK
…
// In release builds, we intentionally crash to prevent submitting an app with a Test Store API key.
```

Every build that reaches a device here is a release build — cable install, TestFlight, Play internal.
That is what killed the app on Saiful's iPhone (DEF282), on `0.1.0+87`, live on both stores.

The real-store route costs no extra dashboard work and is strictly better: with `appl_…` / `goog_…`
keys, **Apple Sandbox testers and Play license testers give free simulated purchases in release
builds** — no crash, no money moving, and it exercises real StoreKit 2 / Play Billing rather than
RevenueCat's simulator. RevenueCat's own crash message says the same thing: *"Please configure the
App Store app on the RevenueCat dashboard and use its corresponding Apple API key before releasing."*

---

## Stage 0 — money prerequisites. These block everything below.

- **Apple.** App Store Connect → **Business** → **Paid Applications Agreement**. Sign it, then
  complete the **banking** and **tax** forms. In-app purchase products cannot be created until this
  agreement shows *Active*.
- **Google.** Play Console → **Setup** → **Payments profile**. Create or link the merchant account.
  Google's verification is the slower of the two.

Do not start Stage 1 or 2 before the corresponding agreement is active — the product screens are
simply not available.

---

## Stage 1 — Apple: seven in-app purchases

App bundle: **`ai.agenticmarketintel.amiTrade`**

> **The product IDs below are contracts with shipped code.** They are matched literally in
> `webhooks.py::_CREDIT_PACKS` and `purchase_models.dart::PaywallProductIds`. A typo or a
> pluralisation fails **silently** — the product simply never classifies — rather than erroring.
> Re-read them character by character before saving. This is the single highest-risk part of the task.

### 1a. One subscription group

Create **one** subscription group (e.g. reference name *AMI Trade Access*) and put **all four**
subscriptions in it. Apple only permits upgrade / downgrade / crossgrade *within* a group, and a user
must be able to move between Trader and Floor Manager. Set **Floor Manager at the higher level**
(level 1) and Trader below it (level 2), so a Trader → Floor Manager move is an upgrade.

### 1b. The products

| Product ID | Type | Duration | Price (USD) |
|---|---|---|---|
| `trader_monthly` | auto-renewable subscription | 1 month | 14.99 |
| `trader_annual` | auto-renewable subscription | 1 year | 129.00 |
| `floor_manager_monthly` | auto-renewable subscription | 1 month | 34.99 |
| `floor_manager_annual` | auto-renewable subscription | 1 year | 299.00 |
| `credits_starter` | **consumable** | — | 4.99 |
| `credits_standard` | **consumable** | — | 19.99 |
| `credits_power` | **consumable** | — | 49.99 |

Reference names are free-form — only the product IDs are contractual.

> **If Apple offers no exact $129.00 / $299.00 price point**, take the nearest available one and
> **report the actual number**. The app always renders the store's own localized price string
> (`PaywallPackage.priceString`, never hard-coded), so a different price point breaks nothing in the
> client — it only makes `tiers_and_pricing.md` stale, which is a doc fix.

Each product also needs a localized **display name + description**, and a **review screenshot** on
first submission. Sandbox purchases work before App Review; the products only need to reach *Ready to
Submit*.

### 1c. The credential RevenueCat needs (StoreKit 2)

App Store Connect → **Users and Access** → **Integrations** → **In-App Purchase** → generate a key.

- Download the **`.p8` private key** — Apple allows this **once**. Store it safely.
- Note the **Key ID** and the **Issuer ID** shown on that page.

Also copy the **App-Specific Shared Secret** (App Store Connect → your app → **App Information** →
*App-Specific Shared Secret* → Manage). RevenueCat only needs it for the StoreKit 1 fallback path, but
having it costs nothing and closes a failure mode.

### 1d. Sandbox testers

App Store Connect → **Users and Access** → **Sandbox** → **Test Accounts**. Create one or two with
email addresses you control that are **not** Apple IDs already in use. On the device, sign into the
sandbox account under *Settings → App Store → Sandbox Account* (not the main Apple ID).

---

## Stage 2 — Google Play: seven products + a service account

App package: **`ai.agenticmarketintel.ami_trade`**

An internal-testing release already exists (`0.1.0+87` / `+89`), which is the prerequisite Play needs
before monetization screens work.

### 2a. Subscriptions

Play Console → **Monetize** → **Subscriptions**. Create **four separate subscription IDs** matching
the table in Stage 1b exactly, each with a **single base plan** (name the base plan `monthly` or
`annual`, auto-renewing, the matching billing period and price).

*Why four rather than two-with-two-base-plans:* both work. Play's RC product identifier takes the
form `<subscriptionId>:<basePlanId>`, and the client's prefix fallback
(`purchase_models.dart:96-103`) classifies `trader:monthly` and `trader_monthly:monthly` correctly
either way, while the backend keys subscriptions off the **entitlement**, never the product ID
(`webhooks.py::_ENTITLEMENT_TO_PLAN`). Four separate IDs simply mirror Apple 1:1 and leave nothing to
reconcile later.

### 2b. One-time products (the credit packs)

Play Console → **Monetize** → **In-app products**. Create three:

| Product ID | Price (USD) |
|---|---|
| `credits_starter` | 4.99 |
| `credits_standard` | 19.99 |
| `credits_power` | 49.99 |

These IDs must be **exact and unsuffixed** — one-time products carry no `:basePlan` suffix, and the
backend matches them literally against `_CREDIT_PACKS`.

### 2c. Service account for RevenueCat

In the **Google Cloud console** (the project linked to the Play developer account):

1. Enable these APIs: **Android Publisher API**, **Play Developer Reporting API**, **Pub/Sub API**.
2. Create a **service account**, and grant it the roles **Pub/Sub Editor** and **Monitoring Viewer**.
3. Create and download a **JSON key** for it.

Then in **Play Console → Users and permissions**, invite the service account's email address with
these account-level permissions:

- *View app information and download bulk reports (read-only)*
- *View financial data, orders, and cancellation survey responses*
- *Manage orders and subscriptions*

> **Allow up to 36 hours** for these credentials to start working against the Play Developer API —
> that is RevenueCat's own stated propagation window. Do not debug a failure inside it.

### 2d. License testers

Play Console → **Setup** → **License testing**. Add the Gmail accounts that will test. Their
purchases on the internal track are free and behave like real Play Billing.

---

## Stage 3 — RevenueCat dashboard

### 3a. Apps → the two public SDK keys

- Add an **App Store** app: bundle ID `ai.agenticmarketintel.amiTrade`. Upload the `.p8`, the **Key
  ID** and the **Issuer ID** (and the app-specific shared secret if prompted). RevenueCat issues the
  **`appl_…` public SDK key**.
- Add a **Play Store** app: package `ai.agenticmarketintel.ami_trade`. Upload the service-account
  JSON. RevenueCat issues the **`goog_…` public SDK key**.

Both keys are *public* by design — safe to compile into a shipped client. The sensitive one is the
webhook secret, which lives only on the backend.

### 3b. Products

Import or create the seven products **per platform**. Verify each identifier character by character
against Stage 1b / 2a / 2b.

### 3c. Entitlements — exactly two

| Entitlement ID | Attached products |
|---|---|
| `trader` | `trader_monthly`, `trader_annual` (both platforms) |
| `floor_manager` | `floor_manager_monthly`, `floor_manager_annual` (both platforms) |

**The three `credits_*` products attach to NOTHING.** They are one-off credit packs, not access
tiers — the backend handles them on a separate code path keyed to the product ID, and attaching one
to an entitlement would wrongly upgrade the user's plan.

### 3d. Offering

Create **one** offering, **set it as current**, and add all seven products to it as packages. The
client reads `offerings.current.availablePackages` and classifies each package by its **product**
identifier, so package identifiers are free-form — but anything outside the *current* offering is
invisible to the app.

### 3e. Webhook

Project Settings → **Integrations** → **Webhooks**:

- **URL:** `https://api-alpha.agenticmarketintel.ai/v1/webhooks/revenuecat`
- **Authorization header value:** the raw 64-character `REVENUECAT_WEBHOOK_SECRET` from
  `infra/alpha.env`. Not in this document by design; do not paste it into a chat log or commit it.

> **Enter the secret raw — no `Bearer ` prefix, no other decoration.** The endpoint does a
> constant-time comparison of the *whole* `Authorization` header against the secret. A `Bearer `
> prefix produces `401 invalid webhook signature`. This has already caught one person.

- **Events:** `INITIAL_PURCHASE`, `RENEWAL`, `PRODUCT_CHANGE`, `CANCELLATION`, `EXPIRATION`,
  `BILLING_ISSUE`, `NON_RENEWING_PURCHASE`. The first three grant or change a plan, the next three
  revoke it, the last is how credit packs arrive.
- **Do not filter to production-only events.** Sandbox and license-tester purchases arrive with
  `environment: "SANDBOX"`. The alpha backend accepts those by design; only `env == "prod"` refuses
  them (403 + logged, `webhooks.py:270-288`). Filtering them out would mean no test purchase ever
  reaches us.

---

## Stage 4 — report back

- The **`appl_…` and `goog_…` public SDK keys**.
- The **seven product IDs as actually created**, per store, **copy-pasted from the dashboard** — not
  retyped from this document. The point is to catch a divergence.
- The **two entitlement IDs** and which products are attached to each.
- The **offering identifier**, and confirmation it is set as current.
- The **HTTP status RevenueCat recorded** for its test event.
- The **actual Apple price points** if 129.00 / 299.00 were unavailable.
- **Anything that could not be done, and why.** A partial configuration reported honestly is far more
  useful than a complete one claimed.

---

## Verification

1. **Webhook reachable.** RevenueCat's "send test event" button records a **2xx**. A `401` means the
   Authorization field is wrong (almost always a `Bearer ` prefix). A `503` means the backend has no
   secret set — it does have one, so a 503 would be news.
2. **Offering resolves.** From the Mac (LAN or public, either):
   ```bash
   curl -s -H "Authorization: Bearer appl_…" -H "X-Platform: ios" \
     https://api.revenuecat.com/v1/subscribers/probe/offerings
   ```
   Should list the seven packages. **Today it returns RevenueCat's stock
   `$rc_monthly`/`$rc_annual`/`$rc_lifetime` template** — that response is the precise signal that
   the dashboard is still unconfigured.
3. **Backend saw the event.**
   ```bash
   ssh melehost "docker logs ami_api_alpha --tail 50 2>&1 | grep -i revenuecat"
   ```
4. **A sandbox `trader_monthly` purchase** →  `users.plan = trader`, `credit_balance = 150`
   (`credit_service.ALLOWANCE`), and exactly **one** `subscription_events` row with
   `source="revenuecat"`. Read it **from the database**, not from the app's own display.
5. **A `credits_standard` purchase** → **+300** credits, `plan` unchanged.
   (`credits_starter` +60 · `credits_power` +850.)
6. **Two renewals inside one calendar month grant the allowance once** — the period guard in
   `credit_service.set_plan_and_grant_allowance` (`credit_service.py:365-381`).
7. **Worth doing deliberately:** purchase **while anonymous**, then claim the account. That exercises
   the DEF099 anon→claimed alias hop, which has never run live.

---

## What happens after Stage 4 (code work, filed separately — not part of this runbook)

1. Swap the three `test_…` keys in `infra/alpha.env` for `appl_…` / `goog_…`.
2. Revert DEF282's off-switch — restore the commented block at `purchase_providers.dart:27-40`.
   `BillingConfig.usableKey` keeps the crash fence in place on its own, and the fence lifts
   automatically once the key no longer starts with `test_`.
3. Re-cut the billing gates in `scripts/build_testflight.sh` / `scripts/build_playstore.sh`. Today
   they only reason about the `test_…`-key case plus DEF290's `--no-billing` key-blanking; with a
   real key, `--no-billing` stops being the honest description of the build.
4. Build → TestFlight internal + Play internal → sandbox purchase → verify from the DB per above.

## Still owed before real money moves

Real-store provisioning closes most of DEF100, but not all of it: price localisation spot-checked per
region, restore-purchases verified across two real store accounts, and store-driven renewal and
cancellation observed against the live webhook. Those need the products live and out of sandbox.
