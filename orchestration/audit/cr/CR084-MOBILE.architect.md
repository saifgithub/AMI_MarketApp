<!--
CR084-MOBILE.architect.md — architect lane file (Architect owns). State derives from the round
numbers here vs CR084-MOBILE.auditor.md. Bump `SUBMITTED: round N` on every resubmit.
Do NOT edit CR084-MOBILE.auditor.md — that is the independent auditor's file.

GATE: independent. Routed to the pre-spawned independent auditor (track U). If none is running, the
lane HOLDS here (the Architect does not spawn its own auditor — separation of duties).
-->

# CR084-MOBILE — audit lane (architect)

**Item:** CR084-MOBILE — `purchases_flutter` + the live paywall replacing CR039's dead 402 cooldown,
wired to CR084-BE's server-authoritative grant (GTM M1 final slice, mobile half).

**Gate:** independent (D-5 — money + App Store review-facing. The purchase→unlock path must never
fabricate an unlock the backend didn't grant, and must never ship a broken/dead checkout. Verify
adversarially.)

**Built SHA (round 1):** `b0d1e8bb5a771f0d7d55d49b502785f351148f3e` on `lane/CR084-MOBILE.coder.mobile`
(branched from merge-base `70a0e14`; **not yet integrated to main** — waits on COMPLETE).

**depends-on:** CR084-BE (integrated `f6f4cfd` — the `GET /v1/billing/identity` + mandate plan-state
contract this builds against). Satisfied.

## What changed / why

| SHA | Files | What |
|---|---|---|
| `b0d1e8bb` | 19 files under `mobile/` (+1785/−7): new `services/billing/` seam, `state/purchase_providers.dart`, `widgets/paywall/upgrade_paywall.dart`, `models/billing_identity.dart`, `room_screen.dart`/`settings_screen.dart` entry points, `api_client.getBillingIdentity`, l10n, 2 test files | `purchases_flutter` isolated to one file behind a store-agnostic `PurchaseService`; prices from the RC offering; post-purchase re-reads `GET /v1/mandate/{id}` (backend authority, not SDK cache); DEF100 degrade to info-not-buy when unconfigured. |

## Architect pre-check (verification done before submitting — NOT the independence gate)

- **Scope / forbidden paths:** diffed vs merge-base `70a0e14`. **19 files, all within
  `mobile/lib` / `mobile/test` / `pubspec.*`.** No `backend/**`, `orchestration/**`, `docs/**`,
  `mobile/ios`, `mobile/android`, or forbidden-file touches. Not pushed to `main`.
- **`flutter test`:** re-run independently in the worktree at `b0d1e8bb` (Flutter 3.41.9) →
  `flutter pub get` clean, **70 passed** (incl. purchase→backend-refresh→unlock, cancel-no-unlock,
  store-error, restore, unconfigured-degrades-to-info).
- **Money-path eyeballed:** prices only from `StoreProduct.priceString` (no hard-coded literals);
  `logIn(app_user_id)` binds RC customer to `users.id`; SDK result treated only as "go re-read from
  backend"; `_refreshEntitlementFromBackend()` re-reads the mandate endpoint (server-authoritative);
  `_Unavailable` degrade shows info + Restore, no buy button.
- **Contract:** `BillingIdentity.fromJson` ↔ `billing.py`; reused `UserMandate.fromJson` re-verified
  1:1 vs `mandate.py::_with_plan_state` (7 keys, no `?? default` mask).

**This pre-check is the integrator's readiness check, not independent verification.** The COMPLETE that
matters comes from the independent auditor's `CR084-MOBILE.auditor.md`.

## Suggested adversarial focus for the independent auditor

1. **Fake unlock.** Can the UI unlock the gated action on a `purchasePackage` SUCCESS **without** the
   backend mandate confirming the new plan/credits? Mutate `_refreshEntitlementFromBackend` to a no-op /
   make the mandate return the OLD plan and confirm the wall does NOT unlock (the whole server-
   authoritative claim). The coder flagged a webhook-race: verify the failure mode is "wall re-shows",
   never "unlocked on client optimism".
2. **Degrade path (DEF100).** With no SDK key AND with a configured-but-empty offering AND on a fetch
   error — all three must render info-not-buy, never a dead/tappable buy button. Confirm all three.
3. **Price source.** Confirm no code path renders a hard-coded price; prices come only from the RC
   offering (store/region correctness).
4. **Restore** actually re-reads entitlement from the backend (not just a local SDK `restorePurchases`
   with no backend refresh).
5. **CR039 preserved.** The Winzip cooldown-countdown path still works alongside the new paywall.
6. **Identity match.** `logIn(app_user_id)` uses the value from `/v1/billing/identity` (== `users.id`),
   so RC's later webhooks resolve to the same user CR084-BE's `_load_user` expects.

## Tests run (architect)

- `flutter test` (worktree @ `b0d1e8bb`, Flutter 3.41.9) → **70 passed.**

SUBMITTED: round 1
