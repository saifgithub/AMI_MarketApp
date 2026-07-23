# CR079 — Ship the release APK to the automated tester on every build path

**Filed:** 2026-07-23 · **Track:** `AT:architect` · **Status:** done · **Supersedes:** part of CR078

## Why

Saiful: *"we will need the APK and we must do `scp mobile/build/app/outputs/flutter-apk/app-release.apk
saiful@192.168.20.59:.../apk/` each time we build because that is our automated tester."*

CR078 put the melehost scp into `install_android.sh` only, and its "Not changed" note deliberately
kept the APK out of the Play scripts, reasoning that they build an **AAB** and only
`install_android.sh` produces an APK. **That reasoning is now void:** the melehost folder is not a
sideload hand-out, it is the input to an **automated test rig**. The rig must run the build we just
made. If a store release (AAB → Play) leaves the melehost APK stale, the rig silently tests code that
has moved and reports pass/fail against the wrong build — the CR040 "degrade loudly" failure with an
automated consumer that never reads the warning a human would.

So the APK copy must happen on **every** build path, not just the device-install one.

## What

**One shared step, two callers.** New `scripts/share_apk_to_tester.sh` is the single source of truth
for "get the current release APK onto the tester":

- With an APK path argument → scp that file (the caller already built it).
- With no argument → `flutter build apk --release` with the standard dart-defines, then scp.
- Destination `AMI_APK_SHARE_DEST` (default the melehost tester folder), `ConnectTimeout=10`.
- **Degrade loudly, never silently.** Exit non-zero on scp failure so a caller can react, and print a
  STALE warning that names the rig-is-testing-the-previous-build consequence regardless of caller.

Wired in:

1. `install_android.sh` — the CR078 inline build-guard + scp + summary block is **replaced** by a
   guarded call to the helper (passing the APK it already built). Behaviour preserved: the scp is
   loud on failure and **never aborts** the device install (`set -euo pipefail` would, so the call is
   guarded inside `if`). The final summary drops its duplicate shared-APK lines — the helper owns
   that messaging now.
2. `publish_playstore.sh` — after the `fastlane internal` upload, a guarded call to the helper (no
   arg → it builds the APK at the current `+N` and scps). A scp hiccup does **not** fail a release
   whose Play upload already landed, but the loud STALE warning still fires.

`build_playstore.sh` (build-only, no upload) is left alone — `publish_playstore.sh` is the release
entry point and wraps it; adding the copy to both would double-build the APK on every publish.

## Not changed

- The store artefacts. Play still gets the AAB through Google's pipeline; the APK is a **separate**
  artefact for the LAN rig only and never enters the store flow.
- CR078's core intent (a fresh APK on melehost) — CR079 widens *where* it fires and removes the
  duplicated scp, it does not reverse it.

## Acceptance

1. `scripts/install_android.sh` refreshes the melehost APK via the helper and still installs to
   devices without aborting when the scp fails. `bash -n` clean.
2. `scripts/publish_playstore.sh` refreshes the melehost APK after a Play upload; a scp failure warns
   loudly but does not fail the release. `bash -n` clean.
3. `scripts/share_apk_to_tester.sh` builds (when given no path) or reuses (when given one) and scps,
   exiting non-zero only on a real scp/build failure. `bash -n` clean.
4. The scp destination string exists in exactly **one** place (the helper's default), so the two
   callers cannot drift.
