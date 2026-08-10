# Intake — generated build artefacts leak between build types and break releases

**Handle:** `generated-artifacts-leak-between-build-types` (pre-triage; no
`DEF###` minted — the Architect is the single ID-minter and other tracks are
live on this checkout).
**Found:** 2026-08-10 (AT:R66), twice in one day, shipping CR109 builds 76–79.
**Severity:** medium. Not a product defect — a **release-pipeline** one. It
fails loudly, at the last step, after a ~12-minute build, and it will recur.

## The class

Flutter writes several **generated, gitignored** artefacts to **one path per
platform**, with no separation by build type. Whichever build ran last wins,
and the next build of a *different* type compiles against the wrong one.

Two instances, same shape, hours apart:

| Artefact | Poisoned by | Release symptom |
|---|---|---|
| `mobile/build/native_assets/ios/objective_c.framework` | an iOS **simulator** build | `Invalid executable … unsupported platform in the x86_64 slice` — rejected by App Store Connect at upload |
| `mobile/android/app/src/main/java/io/flutter/plugins/GeneratedPluginRegistrant.java` | a **debug / integration-test** build | `error: package dev.flutter.plugins.integration_test does not exist` — Gradle `compileReleaseJavaWithJavac` fails |

Nothing is misconfigured in either case. `integration_test` is correctly in
`dev_dependencies` and correctly flagged `dev_dependency: true` in
`.flutter-plugins-dependencies`; a simulator build is a legitimate thing to
run. The QA lane (CR162) is not at fault — it is doing exactly what it should.
The problem is that two lanes share one output path that cannot represent
both build types at once.

## What makes it nasty

**Flutter does not overwrite a stale registrant.** It writes the file when it
is ABSENT or when the plugin set changed. A registrant left by a debug build
therefore survives every subsequent release build and keeps failing.

Measured, not assumed (AT:R66):

```
registrant before: 2 references to integration_test  → assembleRelease FAILS
rm + flutter build apk --release
registrant after:  0 references                      → clean 78.8MB APK
```

The iOS one needed a five-path clear before it took, and the reason is worth
recording: dropping `build/native_assets` alone left the build system
believing native assets were already built, so it wrote a manifest naming
`objective_c` and never regenerated the framework — every rebuild then died
on *"references objective_c, which was not found"*. `.dart_tool/hooks_runner`
is the hook cache and `.dart_tool/flutter_build` is the state that decides
whether the hook runs at all; **both** are needed.

## Fixed in the release scripts

- `scripts/build_testflight.sh` clears `build/native_assets`,
  `build/ios/Release-iphoneos`, `build/ios/iphoneos`,
  `.dart_tool/hooks_runner`, `.dart_tool/flutter_build`.
- `scripts/build_playstore.sh` clears `GeneratedPluginRegistrant.java`.

Both verified by shipping: `0.1.0+79` reached TestFlight and the Play
internal track, and the automated-tester APK is current again.

## What is still worth doing

1. **Generalise the rule rather than patching the next instance.** These are
   the two that have bitten; the principle is that a release script should
   trust no generated artefact it did not produce in that run. A single
   `scripts/clean_generated.sh`, called by both release scripts, would stop
   the third instance from being discovered the same way — at upload.
2. **Fail early.** Both failures surface at the very end of a long build. A
   pre-flight that greps the registrant for dev-only plugins and runs
   `vtool -show-build-version` over embedded frameworks would cost seconds.
3. **`flutter clean` is NOT the answer.** On a shared checkout it destroys
   whatever other lanes have built. The targeted clears above are the right
   scope.
