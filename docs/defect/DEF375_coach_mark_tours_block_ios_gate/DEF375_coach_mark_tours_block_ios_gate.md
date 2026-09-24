# DEF375 — first-run coach-mark tours block the iOS UAT gate

**Source:** prompt-spotted, filed against the CR162 iOS gate results. **Area:**
mobile / QA harness. **Round:** AT:R85. **Status:** fixed.

Full incident history — five prior rounds (2026-08-25 → 2026-08-29, AT:R74) of
diagnosing why the harness could not dismiss a tour mid-run, ending in DEF382's
finding that tapping through a tour's own controls collapses the iOS accessibility
tree — lives in the row: [`docs/defect/_registry/DEF375.row.md`](../_registry/DEF375.row.md)
(rendered in [`def_list.md`](../def_list.md)). This doc is the short version of the
2026-09-24 resolution, for anyone who wants the fix without the five-round history.

## Symptom

The five first-run coach-mark tours (floor, portfolio, lessons, journal, you) are
modal — the tab behind one is unreachable until it is dismissed. The UAT harness
(`qa/appium/`, CR162) always drives a fresh install, so it meets a tour on every
run and 7 of the iOS gate's 19 `pytest -m phase1` tests never reached the screen
they test.

## Why not "wire the harness to dismiss it"

Tried five times across AT:R74. The addressability half was fixed and proven
(`MergeSemantics` around the Skip/Next buttons — DEF382, `ami.tour.skip` /
`ami.tour.next` in `mobile/lib/qa/semantics_ids.dart`). But every attempt to
actually *use* that from the harness — after every tab tap, on first visit only,
walking with Next instead of Skip — either made the gate worse or reproduced the
same failure: touching the coach-mark overlay collapses the whole iOS accessibility
tree, so the next module's onboarding check reads an empty tree and times out at
480s. That is a harness-side dead end, not a wiring bug to keep iterating on.

## Fix — skip the tours structurally, never touch them

`mobile/lib/qa/tour_qa_config.dart` (`TourQaConfig`) is a pure, channel-gated
resolver in the same shape as `AdMobConfig` (CR225):

- `AMI_QA_SKIP_TOURS` — a dart-define, read as a flexible truthy string (`1` /
  `true` / `yes` / `on`), same lesson `AMI_QA_SEMANTICS` already paid for in
  `main.dart` (`bool.fromEnvironment` silently reads `=1` as `false`).
- Honoured **only** when `AMI_RELEASE_CHANNEL` is not `production`. Unset
  (the conservative default — no channel forwarded at all, e.g. a hand build or
  `build_qa_ios_sim.sh`) and `internal` both count as skippable; `production`
  refuses the skip outright, unconditionally, regardless of the flag.

`TourService.hasSeen` (`mobile/lib/features/tour/tour_service.dart`) checks
`TourQaConfig.skipToursForQa` **before** touching `SharedPreferences` at all, and
returns `true` if it's set. Every one of the five tour screens
(`floor_screen.dart`, `portfolio_screen.dart`, `journal_screen.dart`,
`lessons_screen.dart`, `you_screen.dart`) gates on `hasSeen` before ever building
the overlay — so this one choke point covers all five with no per-screen change,
and no tour is ever shown to skip *around*.

Side effect worth naming, not a separate fix: the CR180 nav-change notice
(`shouldShowNavChange`) also never fires under the flag, because it triggers off a
pre-restructure `tour_*_seen` flag having been set — and under the QA flag nothing
ever marks a flag seen (the screen never gets far enough to call `markSeen`).

## What the harness must do

`scripts/build_qa_ios_sim.sh` — the script CR162's own README already documents as
the one the gate rebuilds with — now forwards `AMI_QA_SKIP_TOURS=true` by default
and deliberately still forwards no `AMI_RELEASE_CHANNEL` (matches
`install_iphone.sh`'s existing choice), so the QA Simulator build lands on the
unset/non-production default. **No `base_page.py` change, no per-tab dismiss call,
nothing to wire.** `dismiss_tour_if_present` stays in `qa/appium/pages/base_page.py`
exactly where DEF382 left it — unwired — because this fix removes the need to wire
it rather than finally wiring it.

If the harness ever builds by hand instead of through the script: add
`--dart-define=AMI_QA_SKIP_TOURS=true` to the `flutter build ios --simulator`
invocation. That's the entire integration surface.

## Can a production build ever skip tours?

No, structurally, on two independent levels:

1. `build_testflight.sh` / `build_playstore.sh` (the only paths that ship a real
   build) never pass `AMI_QA_SKIP_TOURS` at all — the define isn't part of their
   dart-define list.
2. Even if it were hand-added by mistake, `TourQaConfig.resolve` refuses to honour
   it once `AMI_RELEASE_CHANNEL=production` — and that channel value is derived
   structurally by those same scripts from `--production`/`--internal-only`, never
   hand-typed (CR225's existing guarantee, reused here rather than re-invented).

Proven directly in `mobile/test/qa/tour_qa_config_test.dart`
(`flag set, channel production => tours show (skip refused)`) and
`mobile/test/features/tour/tour_service_qa_skip_test.dart`
(`skipToursForQa: false` group — the production/no-define case).

## Tests

- `mobile/test/qa/tour_qa_config_test.dart` — the resolver: production always
  refuses regardless of the flag; internal/unknown skip when the flag is set;
  no flag never skips on any channel; flexible truthy string parsing; channel
  string parsing including the conservative fallback for an unrecognised value.
- `mobile/test/features/tour/tour_service_qa_skip_test.dart` — the wiring through
  `TourService.hasSeen`: all five sections report seen under the flag, on a section
  never marked seen; a QA run never writes `tour_*_seen` (so it leaves no residue a
  later real check could misread); the CR180 notice doesn't fire either; and the
  `false` branch behaves exactly as before DEF375 (markSeen/hasSeen round-trip
  unchanged).
- `mobile/test/qa/tour_ids_test.dart` (pre-existing, DEF382) — still green,
  unchanged: `ami.tour.skip`/`ami.tour.next` stay addressable for a real user or a
  future on-device harness that dismisses a tour by hand; this fix does not remove
  that control, it just stops relying on the gate ever tapping it.

`cd mobile && flutter analyze` — 11 issues, 0 errors (unchanged baseline).
`cd mobile && flutter test` — full suite green (1638 tests).
