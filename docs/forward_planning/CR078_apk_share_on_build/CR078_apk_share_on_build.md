# CR078 — Publish every release APK to melehost's shared folder

**Filed:** 2026-07-23 · **Track:** `AT:architect` · **Status:** done

## Why

Saiful: *"I need to include `scp mobile/build/app/outputs/flutter-apk/app-release.apk
saiful@192.168.20.59:.../apk/` each time the apk is created. it should replace the copy that is
there already. include this in our shell scripts."*

That folder is the sideload hand-out path — it already held a `69 MB app-release.apk` from
`Jul 23 14:40`. Doing the copy by hand means it is current only when someone remembers, and a
**stale APK is worse than no APK**: it looks like the build you just made and isn't. Whoever
installs from it gets a silently older app and reports bugs against code that has moved.

## What

One site. `scripts/install_android.sh` is the **only** script that produces an APK —
`build_playstore.sh` and `publish_playstore.sh` both build an **AAB** (`flutter build appbundle`),
which is not what gets sideloaded — so the copy goes there and nowhere else.

Between the build and the device install:

1. **Guard the artefact.** `[[ -f "$APK" ]]` or hard-fail. The old script passed `$APK` straight to
   `adb install` without ever checking it existed.
2. **`scp` with `ConnectTimeout=10`**, destination in `AMI_APK_SHARE_DEST` (env-overridable, LAN
   IP by default per `feedback_lan_route`).
3. **Degrade loudly, don't abort.** A failed copy sets `SHARE_OK=0` and prints
   `⚠ scp FAILED — the shared copy is now STALE` plus the hand-run command in the final summary.
   It does **not** `exit`: a LAN hiccup must not cost an otherwise-good device install, and
   `set -euo pipefail` would have made it do exactly that.

The final summary now states the shared copy's status either way — CR040's rule applied to a
convenience step, because "silently skipped" and "succeeded" previously looked identical.

## Not changed

The Play Store scripts. They ship an AAB through Google's own pipeline; adding a LAN copy there
would put a second, differently-signed artefact in circulation for the same version.

## Acceptance

1. A successful run leaves the destination holding the APK just built and prints `✓ shared APK is
   current`.
2. Destination unreachable ⇒ the device install still completes, and the summary says `✗ shared APK
   is STALE` with the hand-run command.
3. `bash -n` clean.
