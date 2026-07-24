STATUS: READY_FOR_AUDIT (round 1)

<!-- coder-owned lane file for CR084-MOBILE, written by the Architect on the coder.mobile build's behalf
(the ephemeral coder.mobile instance was briefed NOT to touch orchestration/). State machine driven by
the STATUS line above (byte-exact). -->

# CR084-MOBILE — coder.mobile lane (RevenueCat SDK + live paywall)

**Item:** GTM M1 final slice, mobile half. `purchases_flutter` + a live paywall replacing the dead 402
cooldown, wired to CR084-BE's server-authoritative grant. `GATE: independent` (D-5: money/store).

**Spec:** [`docs/forward_planning/CR084_revenuecat_integration/CR084_revenuecat_integration.md`](../../../docs/forward_planning/CR084_revenuecat_integration/CR084_revenuecat_integration.md) (§Scope → CR084-MOBILE, §Acceptance).

**Built SHA:** `b0d1e8bb5a771f0d7d55d49b502785f351148f3e` on `lane/CR084-MOBILE.coder.mobile` (from merge-base `70a0e14`).

**Changed (19 files, +1785 / −7 — all under `mobile/`):**
- `mobile/pubspec.yaml` / `pubspec.lock` — **new dep `purchases_flutter: ^10.4.3`** (RevenueCat SDK).
- `mobile/lib/services/billing/` — **NEW seam:** `purchase_service.dart` (store-agnostic interface),
  `revenuecat_purchase_service.dart` (the ONLY file importing `purchases_flutter` — `logIn(app_user_id)`
  from `GET /v1/billing/identity`; SDK result treated only as "go re-read from backend"), `purchase_models.dart`
  (offering/package/price from RC — `priceString`, never hard-coded), `billing_config.dart` (SDK keys via
  `--dart-define`; empty → never `configure`).
- `mobile/lib/state/purchase_providers.dart` — the controller; post-purchase `_refreshEntitlementFromBackend()`
  re-reads `GET /v1/mandate/{id}` (server-authoritative), never the SDK cache.
- `mobile/lib/widgets/paywall/upgrade_paywall.dart` — the live paywall; **degrade (DEF100):** no SDK key /
  no offering / fetch-failure all render `_Unavailable` (info card + Restore, **no buy button** — never a
  dead/broken checkout). Prices only from the RC offering.
- `mobile/lib/models/billing_identity.dart` — `BillingIdentity.fromJson` (contract with `billing.py`).
- `mobile/lib/screens/room/room_screen.dart` (+ `settings_screen.dart`) — mount the paywall at the 402
  wall (`state.paywall`) + a Settings upgrade entry; CR039 Winzip cooldown path preserved.
- `mobile/lib/services/api/api_client.dart` — one additive `getBillingIdentity()` (serialized internally).
- `mobile/lib/l10n/app_en.arb` + generated l10n — new paywall strings (ar/ms fall back to EN — expected,
  EN-at-alpha).
- `mobile/test/` — `upgrade_paywall_test.dart` + `purchase_controller_test.dart` (10 new tests).

**Contract re-verification (mandatory — done):** `BillingIdentity.fromJson` ↔ `billing.py::BillingIdentity`
(`user_id`, `app_user_id`); post-purchase refresh reuses `UserMandate.fromJson` ↔ `mandate.py::_with_plan_state`
(all 7 keys `plan`/`trial_expires_at`/`credit_balance`/`credit_allowance`/`credits_reset_at`/`room_cost`/
`room_cooldown_until` line up 1:1, no `?? default` masking a rename). CR084-BE did not alter the mandate shape.

**Known alpha caveat (coder-flagged, non-blocking):** RC grants server-side via the async webhook, so a
single post-purchase mandate refresh can momentarily race it; if credits still read short, the wall simply
**re-shows** — no fabricated unlock (degrade-loudly holds). No polling loop added (out of scope for alpha).

**Out of scope respected:** no `backend/**`, `orchestration/**`, `docs/**`, `mobile/ios`, `mobile/android`,
or forbidden-file edits. No native store config (coder.store / DEF100). SDK keys are `--dart-define` slots —
none fabricated.

**Tests:** coder ran `flutter test` → **70 passed** (10 new). **Architect re-ran independently** in the
worktree at `b0d1e8bb` (Flutter 3.41.9) → `flutter pub get` clean, **`flutter test` 70 passed** — incl.
purchase→backend-refresh→unlock, cancel-no-unlock, store-error, restore, and unconfigured-degrades-to-info.

## Definition of Done

| Item | Status |
|---|---|
| `purchases_flutter` added; `logIn(app_user_id == users.id)` via `/v1/billing/identity` | done |
| Live paywall with prices from the RC offering (never hard-coded) | done |
| Purchase + restore; post-purchase refresh reads BACKEND (not SDK cache) before unlock | done |
| Cancel / pending / store-error handled; no fake unlock | done |
| Unconfigured store degrades to info card, NO buy button (DEF100) | done |
| `fromJson` re-verified against real backend models | done |
| No forbidden-path / native edits; `flutter test` green (Architect-verified) | done (70 passed) |
| Live-device purchase smoke | **DEFERRED — DEF100 (Saiful RC keys + store products)** |
