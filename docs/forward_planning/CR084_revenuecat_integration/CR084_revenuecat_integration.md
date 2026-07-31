<!--
CR084 — RevenueCat integration (GTM Milestone M1, final slice).
What/why/scope/acceptance for wiring real in-app purchases + server-authoritative
entitlement/credit grants on top of the CR039 credit gate. Architect-filed 2026-07-24
on the GTM manager's M1 follow-up. Cross-domain: coder.api (webhook + entitlement sync)
+ coder.mobile (SDK + paywall/purchase flow), joined by DEPENDS-ON.

AMENDED 2026-07-30 (AT:R66): alpha now runs on RevenueCat's Test Store, not on real
App Store Connect / Play Console products. Requirements re-cut into an alpha phase and
a production phase; CR084-ALPHA added for the two enforcement gaps that switch opened
(SANDBOX events in prod, and test-keys escaping internal distribution tracks).
-->

# CR084 — RevenueCat integration (GTM M1, final slice)

**Status:** CR084-BE + CR084-MOBILE integrated & audited COMPLETE → **CR084-ALPHA laned** (2026-07-30,
requirements re-cut around the RevenueCat Test Store — see *Two provisioning phases*)
**Milestone:** GTM **M1** (`project_plan.md:182`) — *"RevenueCat integration. Pricing tiers wired to backend (mandate.plan transitions); receipt validation; entitlement checks on premium routes."*
**Requester:** `noncoder.gtm` (GTM manager follow-up, relayed by Saiful 2026-07-24).
**Gate:** `independent` (D-5: money, entitlements, store-facing — a wrong grant is real dollars and a real trust breach).

---

## Why now

M1 is the last unstarted MVP-gating milestone with code in it. Per `project_plan.md:182`, **CR039
(AT:R60) already pulled the entitlement half forward** — the credit-spend/refund ledger
(`credit_service.py`), the real **402 wall** on Convene the Room (`InsufficientCreditsException` →
HTTP 402 with a `balance`/`cost` body), and plan-drift re-grants (`effective_plan` at every
`pick_tier()` callsite). **Charging is still off.** M1 therefore reduces to exactly three things:

1. **RevenueCat SDK** in the mobile app (purchase + restore + entitlement read).
2. **Receipt/webhook validation** on the backend — the *server* is the authority on what a user
   owns, never the client's word (structural, per CR038: an instruction to "trust only verified
   purchases" is not a control; the webhook + signature check is).
3. **Wire the existing 402 upgrade sheet to a real purchase** — today `room_screen.dart:99` renders
   `state.paywall` as a dead cooldown/countdown; it must become a live buy button.

This CR does **not** re-decide pricing — that is locked in
[`../../initial_specs/06_monetization/tiers_and_pricing.md`](../../initial_specs/06_monetization/tiers_and_pricing.md).

---

## Product catalog (locked — from `tiers_and_pricing.md`)

Seven RevenueCat products. **The IDs below are contracts with shipped code** — `webhooks.py`
(`_CREDIT_PACKS`, the `trader_*` / `floor_manager_*` prefix fallback) and `purchase_models.dart`
(`PaywallProductIds`) both key off these literal strings, so a typo fails silently rather than
loudly. They are created **in the RevenueCat Test Store at alpha** (no App Store Connect / Play
Console product needed — see *Two provisioning phases* below) and in ASC + Play Console at
production. Same IDs both times.

| RC product id (canonical) | Kind | Price | Grants |
|---|---|---|---|
| `trader_monthly` | auto-renew sub | $14.99/mo | entitlement `trader` → `Plan.TRADER` + 150 credits/mo |
| `trader_annual` | auto-renew sub | $129/yr | entitlement `trader` → `Plan.TRADER` + 150 credits/mo |
| `floor_manager_monthly` | auto-renew sub | $34.99/mo | entitlement `floor_manager` → `Plan.FLOOR_MANAGER` + 500 credits/mo |
| `floor_manager_annual` | auto-renew sub | $299/yr | entitlement `floor_manager` → `Plan.FLOOR_MANAGER` + 500 credits/mo |
| `credits_starter` | consumable | $4.99 | +60 credits (one-time) |
| `credits_standard` | consumable | $19.99 | +300 credits (one-time) |
| `credits_power` | consumable | $49.99 | +850 credits (one-time) |

- **RC entitlements:** `trader`, `floor_manager`. Floor Pass = no entitlement (default `Plan.FLOOR_PASS`).
- **Credit packs are consumables**, NOT entitlements — they add credits via `credit_service`, never
  change `plan`.
- `Plan` enum already exists (`schemas/mandate.py:43`: `FLOOR_PASS`, `TRADER`, `FLOOR_MANAGER`,
  `TRIAL_TRADER`). The 7-day trial (`TRIAL_TRADER`, `effective_plan`) is orthogonal — a paid purchase
  supersedes an active trial; do not double-grant the monthly credit allowance on the same period.

---

## Scope

### CR084-BE — backend webhook + entitlement sync (`coder.api`)

Owns `backend/app/` (entitlements, credit, mandate). Lands **first** (contract producer).

1. **RevenueCat webhook endpoint** — new router `backend/app/api/webhooks.py` (mounted in `main.py`),
   `POST /v1/webhooks/revenuecat`. Verify RC's `Authorization` header against a configured shared
   secret (`settings.revenuecat_webhook_secret`) — **reject unsigned/mismatched with 401, fail
   closed** (never grant on an unverified call). Idempotent on RC's event `id` (RC retries on non-2xx;
   a replayed `INITIAL_PURCHASE` must not double-grant credits) — dedup on a stored event id, same
   shape as `ReputationEventRow`'s `(user_id, event_type, ref_id)` anchor (DEF039 lesson: dedup must be
   a DB constraint, not a SELECT-then-INSERT race).
2. **Event → grant mapping.** Map RC event types to state:
   - `INITIAL_PURCHASE` / `RENEWAL` / `PRODUCT_CHANGE` (sub) → set `users.plan` to the entitlement's
     tier via the existing mandate/plan path; grant the tier's monthly credit allowance for the new
     period (reuse `credit_service`'s allowance mechanism — do not hand-roll a parallel ledger).
   - `CANCELLATION` / `EXPIRATION` / `BILLING_ISSUE` (grace) → revoke entitlement → `plan` falls back
     to `floor_pass` (or `trial_trader` if trial still active — resolve via `effective_plan`).
   - `NON_RENEWING_PURCHASE` (credit pack) → `credit_service` grant of the pack's credit count. No
     plan change.
   - Write every transition to **`subscription_events`** (`event_type`, `from_value`, `to_value`,
     `source="revenuecat"`, `note=<rc event id>`) — that table already exists (`models.py:580`) and
     is the audit ledger; account-adoption already writes to it.
3. **RC customer ↔ user linkage.** RC `app_user_id` MUST be our `users.id` (UUID). Expose it so the
   mobile SDK logs in with the same id (a `GET /v1/billing/identity` or fold into the existing
   auth/me payload — coder.api's call). Anonymous-first (CLAUDE.md): pre-claim anon users can purchase;
   the purchase must survive account claim/merge (`MergeService` already re-keys `subscription_events`
   — confirm it also carries RC state, or note the gap).
4. **Entitlement read stays server-authoritative.** Premium-route checks continue to read
   `entitlements.effective_plan_for_user(...)` — this CR makes the webhook the thing that *writes* the
   plan; nothing downstream should trust a client-asserted entitlement.
5. **Degrade loudly (CR040).** `revenuecat_webhook_secret` (+ any RC server key) is config-gated —
   forward it in `docker-compose.yml`'s `api-alpha` block or `test_config_compose_parity.py` fails the
   build (this is the exact DEF038/DEF063 "shipped dark for months" trap). If the secret is unset in a
   non-test env, the webhook must **refuse loudly** (503 + logged), not silently accept or silently
   reject every event.

### CR084-MOBILE — SDK + paywall/purchase flow (`coder.mobile`)

Owns `mobile/lib/`. `DEPENDS-ON: CR084-BE` (needs the `app_user_id` contract + the post-purchase
entitlement-refresh endpoint shape before it can verify a real grant).

1. **Add `purchases_flutter`** (RevenueCat SDK) to `pubspec.yaml` (currently no IAP/RC dep — flag as a
   new dependency per CLAUDE.md "lean stack"). Configure with the RC **public SDK key** (iOS + Android),
   `Purchases.logIn(<our user UUID>)` so RC's `app_user_id` matches the backend.
2. **Real paywall.** Replace the dead `state.paywall` cooldown at `room_screen.dart:99` (the `_Paywall`
   widget ~`:384`, fed by `InsufficientCreditsException.fromJson`, `api_exceptions.dart`) with a live
   offering: show Trader / Floor Manager (monthly+annual) + the three credit packs, prices pulled from
   the RC **offering** (never hard-coded — RC is the price source of truth for store/region parity).
3. **Purchase + restore.** `Purchases.purchasePackage(...)`; on success, refresh entitlement from the
   **backend** (not from the SDK's local cache) before unlocking — the webhook is the grant authority,
   the SDK result only tells the client to go re-read. "Restore purchases" button (App Store
   requirement). Handle user-cancel, pending, and store-error paths.
4. **Contract re-verification (mandatory, CLAUDE.md "degrade loudly").** The backend↔mobile mirror is
   hand-written and NOT type-enforced — a backend field rename silently breaks `fromJson` (masked by
   `?? default`). Before `READY_FOR_AUDIT`, re-verify the entitlement/credit refresh `fromJson` against
   **actual backend JSON** from CR084-BE, not the spec.
5. **Upgrade entry points.** The 402 wall is the primary trigger; also surface upgrade from Settings
   (`settings_screen.dart` already grep-matches "upgrade"/"credit") — coder.mobile's call on how many
   entry points ship in this CR vs. a followup.

---

## Out of scope

- **Pricing / offer decisions** — locked in `06_monetization/`. This is wiring, not re-deciding.
- **The "Winzip" / "Share a Premium" funnel mechanics** (CR045/CR047, gtm-001 intake) — separate CRs;
  this CR just must not break the cooldown-countdown path CR039 built for Winzip.
- **Ads / Floor Pass ad monetization** (`ads.md`) — separate track.
- **Web/desktop billing** — mobile stores only at MVP.
- **Leaderboard/cosmetic Phase-2 entitlements** — the tier table lists them; not gated until Phase 2.

---

## Two provisioning phases (amended 2026-07-30, AT:R66)

The original requirement made **App Store Connect + Play Console products and the Apple/Google
paid-app agreements a prerequisite for any purchase at all** — which put a months-long liaison
dependency in front of ever exercising the webhook, the grant, or the paywall. That is no longer
the alpha path.

| | **Alpha — RevenueCat Test Store** | **Production — real stores** |
|---|---|---|
| Keys | `test_…` (one key, both platforms) | `appl_…` (iOS) + `goog_…` (Android) |
| Products | 7, created **inside RevenueCat** | 7, created in ASC + Play Console |
| Money | none moves; RC simulates the transaction | real |
| Paid-app agreements | not required | required (M1's blocker, `project_plan.md:182`) |
| Webhook / entitlement / credit grant | **all execute for real** | same |
| Distribution | internal tracks only (see below) | any |

Alpha is therefore unblocked on Saiful entirely except for the dashboard configuration itself,
which is handed off as [`rc_dashboard_config_prompt.md`](rc_dashboard_config_prompt.md).

**Still Saiful's, never fabricated:** every key and product ID, in both phases.

### Alpha distribution constraint (Test Store)

RevenueCat's own rule, verbatim:

> Never submit an app to the App Store or Google Play that is configured with a Test Store API key.

Our narrowing of it: a `test_…` key may reach **TestFlight *internal* groups and the Play
*internal testing* track only** — neither is store-reviewed and neither reaches a member of the
public. Never an external TestFlight group, never a closed/open Play track, never production.
Enforced at build time by `build_testflight.sh` / `build_playstore.sh` (which refuse a `test_` key
without an explicit `--internal-only`) and `publish_playstore.sh` (which refuses any lane other
than `internal`). A production build with a `test_` key is a hard block — every user would receive
paid entitlements without paying.

### Test Store behaviours alpha must expect (NOT defects)

1. **Purchases are a modal**, not a store sheet: RC presents product metadata with *simulate
   success* / *simulate failure* / *cancel* buttons. All three map onto our existing
   `PurchaseStatus` handling.
2. **Subscriptions self-terminate.** Test Store subs renew on accelerated timers (~5 min for a
   weekly product to ~1 hr for a yearly one) and **hard-cancel after 5 renewals**, firing a real
   `EXPIRATION` → `revoke_to_base` → `floor_pass`. A tester loses Trader within hours and re-buys.
   Deliberately left live: it is the only way the revoke path gets exercised before real money.
3. **Accelerated renewals do not multiply credits.** The allowance is calendar-month
   period-guarded in `credit_service.set_plan_and_grant_allowance` (`credit_service.py:365-381`) —
   a second `RENEWAL` in the same month re-tags the period without re-granting, so a tester does
   not accrue 150 credits per hour. Pinned by test.
4. **Every event carries `environment: "SANDBOX"`.** The alpha backend accepts it by design; in
   `prod` it is refused (see CR084-ALPHA below).
5. **The catalog may legitimately be smaller than 7.** RevenueCat's Test Store documentation does
   not confirm consumable / one-time product support. If the three `credits_*` packs cannot be
   created, the current offering returns **4 packages**, `PaywallOffering.creditPacks` is empty,
   and the paywall renders subscriptions only — a handled state, not a bug. The dashboard prompt
   asks for that to be reported rather than worked around.

### Provisioning status — 2026-07-30

The three gaps recorded on 2026-07-29 are **all closed**:

1. ~~Key names lowercase~~ → `infra/alpha.env` now carries `REVENUECAT_IOS_SDK_KEY`,
   `REVENUECAT_ANDROID_SDK_KEY`, `REVENUECAT_SECRET_API_KEY`, `REVENUECAT_WEBHOOK_SECRET`, all
   UPPERCASE, so Compose's case-sensitive substitution resolves them.
2. ~~Public SDK key has no consumer~~ → `63598c82` wired `--dart-define=REVENUECAT_IOS_SDK_KEY` /
   `REVENUECAT_ANDROID_SDK_KEY` into both build scripts, sourced from `infra/alpha.env`, with a
   loud refusal to build a store release that cannot charge (`--no-billing` to override).
3. ~~`REVENUECAT_WEBHOOK_SECRET` absent~~ → present (64 hex chars, `openssl rand -hex 32`).

**Remaining for alpha:** the RevenueCat dashboard itself — 7 Test Store products, 2 entitlements,
1 current offering, 1 webhook. Handed off as
[`rc_dashboard_config_prompt.md`](rc_dashboard_config_prompt.md).

Tracking stays on **DEF100** (`open`, Saiful-liaison), now with a split DoD: the alpha half closes
when a simulated `trader_monthly` purchase grants `Plan.TRADER` + 150 credits end-to-end; the
production half stays open until real money moves.

---

## Acceptance

### Code acceptance — CR084-BE + CR084-MOBILE (both **met**, audited COMPLETE r1)

- [x] `POST /v1/webhooks/revenuecat` verifies the shared secret, is idempotent on RC event id, and
      **fails closed** on a bad/absent signature (unit tests with mocked RC payloads for each event
      type).
- [x] A verified `INITIAL_PURCHASE` of `trader_monthly` sets `plan=trader`, grants 150 credits for the
      period, and writes a `subscription_events` row (`source="revenuecat"`); a replay does **not**
      double-grant.
- [x] A verified `credits_standard` `NON_RENEWING_PURCHASE` adds 300 credits and does **not** change
      `plan`.
- [x] `EXPIRATION`/`CANCELLATION` drops the effective plan back to `floor_pass` (or `trial_trader` if
      trial active) via `effective_plan`.
- [x] `revenuecat_webhook_secret` forwarded in `docker-compose.yml` api-alpha block →
      `test_config_compose_parity.py` green; webhook refuses loudly if unset in a live env.
- [x] Mobile: the 402 wall shows a live RC offering with real prices; a completed purchase refreshes
      entitlement **from the backend** and unlocks; "Restore purchases" works; cancel/pending/error
      handled.
- [x] Mobile `fromJson` re-verified against real CR084-BE JSON before audit (no silent `?? default`
      masking a rename).
- [x] Full backend unit suite green; no room-cluster/forbidden-path edits from either lane.
- [x] Independent auditor `VERDICT: COMPLETE` on both sub-lanes.

### Alpha acceptance — CR084-ALPHA (Test Store)

- [ ] Test Store catalog configured per [`rc_dashboard_config_prompt.md`](rc_dashboard_config_prompt.md):
      products, the two entitlements, one **current** offering, and the webhook. Product/entitlement
      IDs verified character-by-character against the catalog table above.
- [ ] RC's "send test event" records a **2xx** (a 401 = wrong Authorization value, a 503 = our
      secret is unset).
- [ ] A simulated `trader_monthly` purchase from a device grants `Plan.TRADER` + 150 credits and
      writes one `subscription_events` row — verified from the DB, not from the app's own display.
- [ ] A SANDBOX event is **refused (403 + logged)** when `settings.env == "prod"`, and accepted
      everywhere else.
- [ ] `build_testflight.sh` / `build_playstore.sh` refuse a `test_…` key without `--internal-only`
      and refuse it outright on `--production`; `publish_playstore.sh` refuses any lane but
      `internal` while a `test_…` key is in play.
- [ ] Two `RENEWAL`s inside one calendar month grant the allowance **once** (pins the accelerated
      Test Store renewal behaviour).
- [ ] Whatever the dashboard agent could **not** do is written down here — particularly whether the
      three `credits_*` consumables exist. A 4-product offering is an acceptable alpha outcome.
- [ ] Independent auditor `VERDICT: COMPLETE`.

### Production acceptance (NOT gating alpha — tracked on DEF100)

- [ ] 7 products live in App Store Connect + Play Console under the same IDs, mapped to the two
      entitlements.
- [ ] Apple + Google paid-app agreements and banking active.
- [ ] Real StoreKit / Play Billing receipt validation observed end-to-end; price localisation
      correct per region; restore-purchases verified across two real store accounts.
- [ ] Store-driven renewal and cancellation observed against the live webhook.
- [ ] Production builds carry `appl_…` / `goog_…` keys — no `test_…` key can reach a production
      build (already a hard block).

---

## Lanes

- **CR084-BE** → `coder.api`, `GATE: independent`, produces the entitlement/credit contract first.
  *Integrated `f6f4cfd`, audited COMPLETE r1.*
- **CR084-MOBILE** → `coder.mobile`, `GATE: independent`, `DEPENDS-ON: CR084-BE`.
  *Integrated `cddf7b4`, audited COMPLETE r1.*
- **CR084-ALPHA** → `coder.api` + build scripts, `GATE: independent` (still D-5 — money and
  entitlements). Closes the two enforcement gaps the Test Store switch opened: the `SANDBOX`
  guard in `webhooks.py`, and internal-track-only gating in the three build/publish scripts.
  No mobile change — the paywall deliberately stays visually identical to production so alpha
  pricing reactions are real; testers are briefed out-of-band that purchases are simulated.
