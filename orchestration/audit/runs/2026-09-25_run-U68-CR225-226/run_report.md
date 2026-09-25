<!--
run_report.md: auditor run report for CR225-226 round 1 (U68, taken over from U67). It holds the
evidence behind orchestration/audit/cr/CR225-226.auditor.md.
-->

# 2026-09-25: CR225-226 round 1 (auditor U68)

**SHA audited:** lane `bb74e85b`, shipped in mobile `+111` (the `lib/` at `685dbdd0` is identical to
`5c751bb8`). **Verdict:** `COMPLETE`, with 0 BLOCKER, 0 MAJOR and 2 MINOR.

## Environment

- **Scratch worktree:** `.claude/worktrees/audit-U68-L`. `flutter test` ran on the Mac.
- **Pub cache read:** `google_mobile_ads-9.0.0/lib/src/request_configuration.dart`.
- **+111 build log** (`tf111.log`, in the session scratchpad): `--internal-only`, and
  GoogleMobileAds linked and archived.

## Tests and mutations (each reverted, tree re-checked clean)

| Run | Result |
|---|---|
| The lane's six test files | 68 passed, EXIT=0 |
| Full mobile suite at +111 | 1688 passed, EXIT=0 |
| M1: channel gate disabled | 3 failed |
| M2: banner skips `_ensureReady()` (consent) | 24 passed (survives, MINOR-2) |
| M3: `_tagFor(none)` becomes `yes` | 205 passed (survives, MINOR-2) |
| M4: banner exempt from the plan gate | 5 failed |

## Reads

- **Scripts that set `AMI_RELEASE_CHANNEL`:** only `build_testflight.sh` and `build_playstore.sh`.
  `install_iphone.sh` does not forward it.
- **Banner ad unit:** banner loads use `nativeAdUnitId` (MINOR-1).
- **SDK constants:** `TagForChildDirectedTreatment` and `TagForUnderAgeOfConsent` share -1/0/1 in
  9.0.0.

FOREIGN: not run.
