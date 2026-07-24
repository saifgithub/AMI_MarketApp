<!--
Auditor run report — run-43 (2026-07-24, session auditor.core/track U). Round-1 audit of
CR084-MOBILE. Audited SHA b0d1e8bb on lane/CR084-MOBILE.coder.mobile. Verdict COMPLETE. Owner: AUDITOR.
-->

# run-43 (round 1) — CR084-MOBILE RevenueCat SDK + live paywall → COMPLETE

- **Auditor session:** auditor.core (track U), 2026-07-24. Picked off the run queue immediately
  after CR084-BE (run-42) — the paired mobile half of GTM M1's final slice.
- **Audited SHA:** `b0d1e8bb5a771f0d7d55d49b502785f351148f3e`, tip of
  `lane/CR084-MOBILE.coder.mobile` (branched from merge-base `70a0e14`; not yet integrated to main).
  Audited in a fresh isolated worktree `.claude/worktrees/audit-CR084-MOBILE/`.
- **The item:** `purchases_flutter` SDK integration + the live paywall replacing CR039's dead 402
  cooldown UI, wired to CR084-BE's server-authoritative grant. `DEPENDS-ON: CR084-BE` (satisfied —
  I independently audited that lane COMPLETE in run-42).
- **Gate:** independent (D-5 — money, App Store review-facing).
- **Verdict:** COMPLETE (round 1) — zero BLOCKER, zero MAJOR. One MINOR (test-coverage naming gap,
  not a behavioral defect).

## Verification

### Reproduced independently

| Check | Result |
|---|---|
| Scope | 19 files, +1785/−7, all under `mobile/` — exact match. |
| Analyze | 4 pre-existing infos, none in touched files. |
| Test suite | 70 passed, exit 0. |
| ar/ms untranslated | 18 each (new paywall strings, EN-at-alpha — expected). |

### The "fake unlock" question — the deepest check in this audit

Rather than trust that `PurchaseController.buy()` returning success implies a real grant, traced
`onPurchased` to its actual call site: `room_screen.dart` wires it to
`roomNotifierProvider(ticker).notifier.start()` — the **same pre-existing, unmodified,
server-gated** call (`api.streamRoom(...)`) that produced the paywall via
`InsufficientCreditsException` in the first place. This means the purchase flow structurally cannot
fake an unlock: `onPurchased` doesn't set any "unlocked" flag, it just retries the real protected
action, which re-runs the full server-side credit check unconditionally every time. If the CR084-BE
webhook hasn't landed yet (the coder's own flagged race), the retry throws the same exception again
and the same wall re-renders — by construction, not by a timing assumption. This is a stronger
guarantee than a passing test alone would prove, and it required tracing two files past what the
hand-off's line citations covered.

Separately mutation-tested the backend-refresh call itself (disabled `if (outcome.isSuccess)` in
`PurchaseController.buy()`) — the existing `successful buy re-reads entitlement from backend` test
went RED (spy never invoked). Reverted.

### Degrade paths (DEF100) — verified all 3, not just the 1 the coder's suite names

Source correctly branches on all three: no SDK key, configured-but-empty offering, and a genuine
fetch exception. The coder's own test suite only pins the first by name. Wrote a throwaway widget
test (not committed) exercising the other two directly against the real `UpgradePaywall` widget —
both correctly rendered the info-card degrade with zero BUY buttons. Deleted the probe after use.

### Other focus points

Price source: `priceString` is the only field ever rendered as a price; grepped for stray `$`
literals — none outside test fixtures. Credit-pack counts (60/300/850) match CR084-BE's
`_CREDIT_PACKS` exactly. Restore re-reads from backend via the same code path as buy (existing test
passed). CR039 Winzip path: diff shows a verbatim extraction, cooldown-timer state untouched.
Identity: `logIn()` uses the backend-issued `app_user_id`, not a local id; `BillingIdentity.fromJson`
matches `billing.py` field-for-field with no silent-default masking.

## Findings

**MINOR** — the hand-off's degrade-path claim ("done") and its own test name cover only the
no-SDK-key condition; the other two conditions the architect explicitly asked to confirm are
correct in the source (independently verified) but untested by name in the committed suite — a
future regression collapsing the `AsyncValue.when` branches wouldn't be caught by CI. Not a
behavioral defect; worth a follow-up test addition.

No BLOCKER, no MAJOR.

## Verdict

**VERDICT: COMPLETE (round 1)**
