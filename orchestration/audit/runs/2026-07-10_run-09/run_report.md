<!--
Auditor run report — CR015 round 1, run-09 (2026-07-10, session AT:U1).
E4/D7 on-system components (HexToast C4, hex period toggle C3, logo C5;
glass sheets C1 deferred). Flutter-only, no new dep. Owner: AUDITOR.
-->

# CR015 — audit run-09 (round 1)

- **Auditor session:** AT:U1 (track U), 2026-07-10
- **Audited SHA:** `1ee1c1a` (CR015 head, on origin/main; built on CR014 COMPLETE
  `fbf0303`). `depends-on: none`.
- **Equivalence:** `git diff 1ee1c1a..HEAD -- mobile/` empty + clean mobile tree
  → live `mobile/` == committed SHA. No backend change; pubspec deps unchanged
  → **no new dep**.

## Commands run + observed output
```
$ (cd mobile && flutter analyze) → 4 issues (all pre-existing infos, 0 new)
$ (cd mobile && flutter test)    → 15 passed
```
New `hex_toast_test.dart`: show → message visible → auto-dismiss (advanced past
hold + slide-out; no leaked entry / pending timer). ✅ Matches claim.

## HexToast lifecycle (riskiest — read `hex_toast.dart`)
- `show`: root `Overlay.maybeOf` (null→return), inserts an `OverlayEntry` whose
  `onDismissed` is `entry.remove`. ✅
- `_HexToastCardState`: `_controller` (280ms) **disposed**; `initState` forwards
  (slide-in) + schedules `_dismiss` after `duration`; `_dismiss` guards
  `_dismissing || !mounted`, reverses (slide-out), then calls `onDismissed`
  (entry.remove). Tap-to-dismiss shares `_dismiss` — the `_dismissing` guard
  prevents a double-remove from tap + auto-dismiss racing. ✅
- The auto-dismiss `Future.delayed` is uncancelled but always fires within
  `duration` and no-ops via the guard if already dismissed — safe (not a leak).
- `Semantics(liveRegion: true)` so screen readers announce the toast. ✅

## C3 — hex period toggle (`ticker_chart.dart`, `29c3ff2`)
`_PeriodCell` replaces the rounded `ChoiceChip`: active = `hexBlue` fill +
`AmiShadow.glowBlue` on a `DecoratedBox` **behind** the `ClipPath` (same
uncropped-halo pattern as C6); inactive = slate800 + slate700 hex border. **A11y
preserved** — `Semantics(button: true, selected: active, label)` (ticker_chart.dart:210),
matching the old ChoiceChip's semantics. ✅

## C4 — SnackBar → HexToast routing (`338b600`)
4 user-facing feedback SnackBars (Floor / Portfolio / Lessons tour-completion +
Brief "proposal saved") swapped to `HexToast.show`. ✅

## C5 — Floor logo
`assets/logo_hex.svg` present (590 B) **and declared in pubspec** (`assets:` line
95) → bundles + renders in the Floor header (no AppBar). ✅ No missing-asset risk.

## Deferrals (disclosed) — both accurate
1. **C1 glass sheets** — `GlassPanel` exists but is used only in
   `dev_preview_screen.dart` (preview), **not** applied to the 3 bottom sheets.
   Genuinely deferred (modal geometry / keyboard-insets / regression-sensitive).
   ✅ (D-062 dark-pin makes the light-fill note moot until v1.1.)
2. **Bulk/auth SnackBar routing** — ~20 `showSnackBar` sites remain:
   `sign_in_screen` (10) + `merge_sheet` (2) auth-path, `settings` (4) + `journal`
   (4) lower-risk, `trade_ticket_sheet` (1) intentionally bespoke (pops sheet then
   toasts). Matches the disclosed deferral. ✅

## Register / scope
`cr_list.md:44` CR015 `in_progress`; folder doc present (both deferrals). One
concern per commit: toast widget `63b0dea` / toggle `29c3ff2` / routing+logo
`338b600` / test `1ee1c1a`.

## NEEDS-DEVICE-CHECK
Toasts sliding in as hex-clipped mono cards; period toggle switching + active
cell glowing; logo rendering crisply in the Floor header. Device-only; Saiful's
release build covers.

## Verdict
Zero BLOCKER + zero MAJOR. No new findings — HexToast lifecycle safe, C3 a11y
preserved, C4 routing correct, C5 asset bundled, deferrals accurate. →
**COMPLETE (round 1)**.
