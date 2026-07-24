<!-- dispatch assign lane — Architect-owned. CR052. CR084 mobile sub-lane. -->
# CR084-MOBILE — assign (RevenueCat SDK + live paywall/purchase flow)

KIND: code
INSTANCE: coder.mobile
ACCEPTANCE: docs/forward_planning/CR084_revenuecat_integration/CR084_revenuecat_integration.md (§Scope → CR084-MOBILE, §Acceptance)
DEPENDS-ON: CR084-BE    <!-- needs the app_user_id identity contract + the post-purchase entitlement-refresh JSON from the backend before it can verify a real grant. Do not START the fromJson re-verification until CR084-BE is READY_FOR_AUDIT; scaffold the SDK/paywall UI in parallel is fine. -->
GATE: independent    <!-- D-5: money + store-facing (Apple/Google review). -->
HOT-FILES: `mobile/pubspec.yaml` (add `purchases_flutter`), `mobile/lib/screens/room/room_screen.dart` (the `_Paywall` widget ~:384 fed by `state.paywall`), `mobile/lib/services/api/api_exceptions.dart` (`InsufficientCreditsException`), a new purchase/entitlement service + provider under `mobile/lib/services/` + `mobile/lib/state/`, `mobile/lib/screens/settings/settings_screen.dart` (upgrade entry). All coder.mobile-internal — serialize `api_client.dart` edits internally.

## Build (replace the dead paywall CR039 left with a real one)

1. **Add `purchases_flutter`** (RevenueCat SDK) to `pubspec.yaml` — currently NO IAP/RC dep (flag as a
   new dependency, CLAUDE.md lean-stack). Configure with RC **public SDK key** (iOS + Android);
   `Purchases.logIn(<our user UUID>)` so RC's `app_user_id` matches CR084-BE's identity contract.
2. **Live paywall:** `room_screen.dart:99` renders `state.paywall` (the `_Paywall` widget ~:384) today
   as a dead cooldown/countdown from `InsufficientCreditsException.fromJson`. Turn it into a live RC
   **offering** — Trader / Floor Manager (monthly + annual) + the 3 credit packs, **prices pulled from
   the RC offering, never hard-coded** (RC is the store/region price source of truth). Keep CR039's
   Winzip cooldown-countdown path working alongside it.
3. **Purchase + restore:** `Purchases.purchasePackage(...)`; on success, refresh entitlement **from the
   backend** (CR084-BE), not the SDK's local cache, before unlocking — the webhook is the grant
   authority, the SDK result just says "go re-read." "Restore purchases" button (App Store requirement).
   Handle user-cancel, pending, and store-error states.
4. **Contract re-verification (MANDATORY — CLAUDE.md degrade-loudly):** the backend↔mobile mirror is
   hand-written, NOT type-enforced; a backend rename silently breaks `fromJson` (masked by `?? default`).
   Before `READY_FOR_AUDIT`, re-verify the entitlement/credit refresh `fromJson` against **actual
   CR084-BE JSON**, not the spec.
5. **Upgrade entry points:** 402 wall (primary) + Settings. Your call how many ship here vs. a followup.

## Out of scope
Backend webhook/entitlement (CR084-BE). Pricing (locked). Ads. Web billing.

## Saiful-liaison dependency (does NOT block scaffolding)
RC public SDK keys + store product IDs are Saiful's (via `coder.store`). **Do not fabricate.** Build
the SDK wiring + paywall UI against a **mocked/configurable** RC key + a stub offering; the live-device
purchase smoke test waits on Saiful's App Store Connect / Play Console product config.

## Tests
Widget tests for the paywall states (offering shown, purchase success→unlock, cancel, error, restore).
Re-verify `fromJson` against real backend JSON before audit. Follow the existing mobile test pattern.

## Delivery
Push to `lane/CR084-MOBILE.coder.mobile`, never `main`. Hand-off:
`orchestration/dispatch/lanes/CR084-MOBILE.coder.mobile.md` (`STATUS: READY_FOR_AUDIT (round 1)`) +
`orchestration/audit/cr/CR084-MOBILE.architect.md` (`SUBMITTED: round 1`). Commit tag `(AT:coder.mobile CR084)`.

DISPATCH: ACCEPTED (round 1)

ASSIGNED: coder.mobile round 1

<!-- INTEGRATED 2026-07-24: coder.mobile build b0d1e8bb independently audited COMPLETE (round 1, no
BLOCKER/MAJOR; all three DEF100 degrade triggers verified). Clean checkout of the 19 mobile lane files
onto main at cddf7b4 (no divergence since merge-base 70a0e14), flutter test 70 passed. Lane closed.
Paywall ships DARK until DEF100 (RC keys + store products). Minor follow-up: pin the 2 unnamed
degrade-path tests. -->

