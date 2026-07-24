<!--
CR084-MOBILE.auditor.md — auditor lane file (track U owns). State derives from round numbers
here vs CR084-MOBILE.architect.md (see PROTOCOL.md).
-->

# CR084-MOBILE — audit lane (auditor)

**Item:** CR084-MOBILE — `purchases_flutter` + the live paywall replacing CR039's dead 402
cooldown, wired to CR084-BE's server-authoritative grant (GTM M1 final slice, mobile half).

**Gate:** independent (D-5 — money + App Store review-facing. The purchase→unlock path must never
fabricate an unlock the backend didn't grant.)

**Audited SHA:** `b0d1e8bb5a771f0d7d55d49b502785f351148f3e`, tip of `lane/CR084-MOBILE.coder.mobile`
(branched from merge-base `70a0e14`, not yet integrated to main). Audited in an isolated worktree
`.claude/worktrees/audit-CR084-MOBILE/`.

## Round 1

### Reproduced independently

| Check | Result |
|---|---|
| Scope | `git diff --stat 70a0e14..b0d1e8bb` — **19 files, +1785/−7**, exact match, all under `mobile/`. No `backend/**`/`orchestration/**`/native/forbidden-path touches. |
| Main divergence | 1 commit ahead of merge-base (dispatch/roster doc only). |
| `flutter pub get` | Clean; ar/ms untranslated 18 each (new paywall strings, EN-at-alpha — expected). |
| `flutter analyze lib/` | 4 pre-existing infos, none in touched files — matches prior lanes exactly. |
| `flutter test` | **70 passed**, exit 0. |
| `depends-on` CR084-BE | Confirmed integrated on main (`f6f4cfd` per the hand-off; my own CR084-BE round-1 audit — run-42 — independently verified the underlying webhook contract this lane builds against). |

### Focus #1 — "fake unlock" — the most safety-critical check, verified structurally AND by mutation

Traced `onPurchased`'s wiring at **both** entry points before assuming anything about
`PurchaseController.buy()`'s return value:

- `room_screen.dart`'s hard-wall `onPurchased` calls
  `ref.read(roomNotifierProvider(ticker).notifier).start()` — **the exact same server-gated call**
  (`RoomNotifier.start()` → `api.streamRoom(...)`) that produced the paywall in the first place via
  `InsufficientCreditsException` (pre-existing CR039 code, untouched by this diff — confirmed via
  `git diff` showing only the Winzip/hard-wall UI split, not `room_providers.dart`). So even though
  `PurchaseController.buy()`'s returned `outcome` is SDK-level (just "did the store transaction
  succeed"), **`onPurchased` never trusts it to grant anything** — it just retries the real
  protected action, which re-runs the actual server-side credit check unconditionally. There is no
  code path by which a client-side purchase signal alone unlocks the Room; the backend is the only
  thing that can ever let `streamRoom` proceed. This satisfies the coder's own flagged
  "webhook-race" caveat by construction, not by a timing assumption: if the webhook hasn't landed
  yet, `streamRoom` throws `InsufficientCreditsException` again exactly as before, and the same
  paywall re-renders — never a fabricated unlock.
- `settings_screen.dart`'s `onPurchased` is a bare `mandateNotifierProvider.notifier.refresh()` —
  not a gated action at all, just a display refresh. No unlock risk there since nothing is gated in
  Settings.
- Mutation-tested the backend-refresh mechanism itself (not just its wiring): disabled the
  `if (outcome.isSuccess)` guard in `PurchaseController.buy()` — `purchase_controller_test.dart`'s
  `successful buy re-reads entitlement from backend` went RED (spy mandate never captured/called).
  Reverted. Confirms the refresh call is real, not decorative — even though (per the structural
  point above) its absence wouldn't itself create a fake unlock, since `RoomNotifier.start()` is the
  actual gate.

### Focus #2 — degrade paths — coder's own suite covers 1 of 3 named conditions; independently verified the other 2

Read `upgrade_paywall.dart`'s `AsyncValue.when`: `error` → `_Unavailable`; `data` with
`null`/`isEmpty` offering → `_Unavailable`; only a non-null non-empty offering renders buy buttons.
The coder's `upgrade_paywall_test.dart` has one test named `'unconfigured store degrades to info'`,
which only exercises `configured: false` (no SDK key) — **it does not separately exercise
"configured but the RC offering is empty" or "a genuine fetch exception"**, the other two conditions
the architect's hand-off explicitly asked to confirm. Rather than take the source read on faith,
wrote a throwaway widget-test probe (not committed, deleted after use) with two services — one
returning `null` while `isConfigured == true`, one whose `fetchOffering()` throws — and ran both
against the real `UpgradePaywall` widget: **both rendered `_Unavailable` with zero BUY buttons**,
matching the source. Confirms the coder's disclosed 70-test run is functionally accurate, but its
own suite under-names its degrade coverage — see Findings.

### Focus #3 — price source

`purchase_models.dart`: `PaywallPackage.priceString` is documented and structurally the *only*
field ever rendered as a price (`_ProductRow` renders `p.priceString`, nothing else). Grepped the
whole `mobile/lib/services/billing/` + `widgets/paywall/` tree for `\$` literals used as a price —
none; the only dollar-sign strings are in test fixtures. `PaywallProductIds.packCredits` (60/300/850)
is a **credit-count** mirror, not a price, and matches CR084-BE's `webhooks.py::_CREDIT_PACKS`
exactly (verified against my own CR084-BE audit).

### Focus #4 — Restore

`RevenueCatPurchaseService.restore()` calls `Purchases.restorePurchases()` and returns success with
**no local entitlement read** — the caller (`PurchaseController.restore()`) is the one that calls
`_refreshEntitlementFromBackend()` on success, the identical code path `buy()` uses. Confirmed via
the existing `successful restore re-reads entitlement from backend` test (passed in the full run);
not separately mutation-tested since it's the same guard already proven for `buy()`.

### Focus #5 — CR039/Winzip preserved

`git diff` on `room_screen.dart` shows the Winzip branch (`_buildWinzip`) is a **verbatim extraction**
of the pre-existing shared-`build()` code (only the redundant `_isWinzip &&` in one conditional was
simplified, logically a no-op since `_buildWinzip` is now only called when `_isWinzip` is already
true) — the cooldown timer state (`initState`/`_tick`/`_remaining`/`_ready`/`_announceReady`) is
untouched, confirmed both by the diff and by reading the surrounding unchanged lines in full.

### Focus #6 — identity match

`RevenueCatPurchaseService._ensureConfigured()` calls `_api.getBillingIdentity()` (hits
`GET /v1/billing/identity`, confirmed the exact route string) and passes `identity.appUserId` —
not a locally-generated device id — to `Purchases.logIn(...)`. `BillingIdentity.fromJson` mirrors
`billing.py`'s two fields (`user_id`, `app_user_id`) exactly, direct-cast (throws loudly on a
renamed/missing key rather than silently defaulting).

### Findings

**MINOR — test-coverage gap, not a behavioral defect.** The hand-off's DoD row
("Unconfigured store degrades to info card, NO buy button (DEF100) — done") and its own test name
cover only the no-SDK-key condition by name, even though the architect's own hand-off asked to
confirm all three degrade triggers and the source code correctly handles all three. I independently
verified the other two (configured-but-empty-offering, genuine fetch error) behave correctly via a
throwaway probe — so this is not a functional defect, nothing renders wrong — but the coder's
in-repo test suite doesn't pin two of the three degrade conditions by name, so a future regression
in either path (e.g. someone "simplifying" the `AsyncValue.when` and collapsing `error` into
`data`) would not be caught by CI. Worth a follow-up test addition, not a blocker for this lane.

No BLOCKER, no MAJOR.

### Verdict

**VERDICT: COMPLETE (round 1)**

Run report: [`../runs/2026-07-24_run-43/run_report.md`](../runs/2026-07-24_run-43/run_report.md)
