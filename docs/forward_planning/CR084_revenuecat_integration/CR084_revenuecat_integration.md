<!--
CR084 — RevenueCat integration (GTM Milestone M1, final slice).
What/why/scope/acceptance for wiring real in-app purchases + server-authoritative
entitlement/credit grants on top of the CR039 credit gate. Architect-filed 2026-07-24
on the GTM manager's M1 follow-up. Cross-domain: coder.api (webhook + entitlement sync)
+ coder.mobile (SDK + paywall/purchase flow), joined by DEPENDS-ON.
-->

# CR084 — RevenueCat integration (GTM M1, final slice)

**Status:** proposed → laned (CR084-BE + CR084-MOBILE)
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

Seven RevenueCat products. Saiful configures the store-side product IDs + RC offerings/entitlements
(see **Saiful-liaison dependency** below); the IDs below are the proposed canonical keys.

| RC product (proposed id) | Kind | Price | Grants |
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

## Saiful-liaison dependency (BLOCKING for end-to-end, NOT for build)

RevenueCat + store config is Saiful's (CEO/board — accounts, money). **Do not fabricate keys or
product IDs.** Needed before a real purchase can complete on a device:

- RC dashboard: project + **public SDK keys** (iOS, Android) + **webhook auth secret**.
- 7 products created in **App Store Connect** + **Play Console**, mapped to RC offerings + the two
  entitlements (`trader`, `floor_manager`).
- Apple/Google paid-app agreements + banking (M1's stated blocker in `project_plan.md:182`).

Build proceeds against these as config placeholders (degrade-loudly if unset); the lanes can reach
`READY_FOR_AUDIT` with the webhook + SDK wired and unit-tested against **mocked** RC payloads. The
live-device purchase smoke test waits on Saiful (route via `coder.store` for the store side).

### Provisioning status — 2026-07-29

Saiful reports two RevenueCat keys added to `infra/alpha.env` (gitignored; canonical on the Mac,
scp'd to `melehost:~/ami_trade/.env` by `/promote-to-alpha`). Values not inspected. **Neither is
live yet** — three gaps between "in the file" and "working":

1. **Key names are lowercase** (`revenuecat_public_sdk_api_key`, `revenuecat_secret_api_key`); every
   other entry in the file is UPPERCASE. `docker-compose.yml:92` substitutes
   `${REVENUECAT_SECRET_API_KEY:-}`, and Compose variable substitution is **case-sensitive** — a
   lowercase name does not satisfy it, so the container still receives an empty value and the
   alias transfer keeps returning `not_configured` (CR040 degrade-loudly, working as designed and
   therefore easy to mistake for "not deployed yet"). Rename to `REVENUECAT_SECRET_API_KEY`.
2. **The public SDK key has no consumer.** No backend setting reads it (`config.py` defines only
   `revenuecat_webhook_secret` + `revenuecat_secret_api_key`); the app takes it at build time via
   `--dart-define=REVENUECAT_IOS_SDK_KEY` / `REVENUECAT_ANDROID_SDK_KEY`
   (`mobile/lib/services/billing/billing_config.dart:25-32`), and **no build script passes either
   flag** — `scripts/build_testflight.sh:108-109`, `scripts/build_playstore.sh:111-114`,
   `scripts/install_iphone.sh:97-98`. Until those are wired, every build ships with an empty
   `publicSdkKey` and the paywall stays in the out-of-credits info state. Also note RC issues one
   public key **per platform** (`appl_…` iOS, `goog_…` Android); a single stored value cannot serve
   both.
3. **`REVENUECAT_WEBHOOK_SECRET` is still absent** from `infra/alpha.env`. It is not issued by
   RevenueCat — generate it (`openssl rand -hex 32`) and paste the same string into the RC
   dashboard's webhook config. Until then `POST /v1/webhooks/revenuecat` refuses loudly (503), so
   no entitlement or credit grant can land.

Tracking stays on **DEF100** (`open`, Saiful-liaison) until a real purchase completes on a device;
this CR is the code, DEF100 is the provisioning. DEF099's live RC-alias hop is gated on gap 1.

---

## Acceptance

- [ ] `POST /v1/webhooks/revenuecat` verifies the shared secret, is idempotent on RC event id, and
      **fails closed** on a bad/absent signature (unit tests with mocked RC payloads for each event
      type).
- [ ] A verified `INITIAL_PURCHASE` of `trader_monthly` sets `plan=trader`, grants 150 credits for the
      period, and writes a `subscription_events` row (`source="revenuecat"`); a replay does **not**
      double-grant.
- [ ] A verified `credits_standard` `NON_RENEWING_PURCHASE` adds 300 credits and does **not** change
      `plan`.
- [ ] `EXPIRATION`/`CANCELLATION` drops the effective plan back to `floor_pass` (or `trial_trader` if
      trial active) via `effective_plan`.
- [ ] `revenuecat_webhook_secret` forwarded in `docker-compose.yml` api-alpha block →
      `test_config_compose_parity.py` green; webhook refuses loudly if unset in a live env.
- [ ] Mobile: the 402 wall shows a live RC offering with real prices; a completed purchase refreshes
      entitlement **from the backend** and unlocks; "Restore purchases" works; cancel/pending/error
      handled.
- [ ] Mobile `fromJson` re-verified against real CR084-BE JSON before audit (no silent `?? default`
      masking a rename).
- [ ] Full backend unit suite green; no room-cluster/forbidden-path edits from either lane.
- [ ] Independent auditor `VERDICT: COMPLETE` on both sub-lanes.

---

## Lanes

- **CR084-BE** → `coder.api`, `GATE: independent`, produces the entitlement/credit contract first.
- **CR084-MOBILE** → `coder.mobile`, `GATE: independent`, `DEPENDS-ON: CR084-BE`.
