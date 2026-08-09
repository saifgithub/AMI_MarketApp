# Intake — an iOS **simulator** build poisons the next TestFlight archive

**Handle:** `ios-sim-build-poisons-the-testflight-archive` (pre-triage; no
`DEF###` minted — the Architect is the single ID-minter and other tracks are
live on this checkout).
**Found:** 2026-08-10 (AT:R66), shipping CR109 build `0.1.0+76`.
**Severity:** medium. Not a product defect — a **release-pipeline** one. It
blocks shipping, loudly, at the last step of a ~12-minute build.

## What happened

`0.1.0+75` uploaded to TestFlight cleanly at 00:57. `0.1.0+76`, from the same
tree ~30 minutes later, failed at `xcodebuild -exportArchive`:

```
Invalid executable. The "Runner.app/Frameworks/objective_c.framework/objective_c"
executable references an unsupported platform in the x86_64 slice.
Simulator platforms aren't permitted.
Unsupported Architectures … contains unsupported architectures '[x86_64]'
```

Between the two, the QA lane (CR162) ran an iOS **simulator** build — a new
`scripts/build_qa_ios_sim.sh` appeared untracked in the same window.

## Root cause

Flutter's native-assets output directory is **not** keyed by platform:

```
mobile/build/native_assets/ios/objective_c.framework
```

One path, shared by the device build and the simulator build, last-writer-wins.
After the simulator build it held:

```
$ lipo -info  → x86_64 arm64
$ vtool -show-build-version → platform IOSSIMULATOR   minos 13.0
```

…stamped at 01:02. The device archive then copies whatever sits there into
`Runner.app/Frameworks/`, so the App Store upload correctly refused a binary
with a simulator slice in it.

## Why the obvious fix was not enough

Deleting `~/Library/Developer/Xcode/DerivedData/Runner-*` changed nothing —
the poisoned artefact is in the **Flutter** build tree, not Xcode's.

Deleting `build/native_assets/` alone then broke the build a different way:

```
The native assets specification at …/NativeAssetsManifest.json references
objective_c, which was not found in …/build/native_assets/ios/.
```

Flutter's build system had cached "native assets already built" and would not
regenerate them. The working sequence was:

```bash
rm -rf mobile/build/native_assets \
       mobile/build/ios/Release-iphoneos mobile/build/ios/iphoneos \
       mobile/.dart_tool/flutter_build mobile/.dart_tool/hooks_runner
```

`.dart_tool/hooks_runner` is the one that actually matters — it is the
native-assets hook cache. Without removing it, the manifest and the directory
stay out of sync and every rebuild fails identically.

## What a fix looks like

The cheap, correct one: **`scripts/build_testflight.sh` and
`scripts/build_playstore.sh` should clear the native-assets caches before
archiving.** Four `rm -rf` lines on a path that is pure build output. A release
build should not inherit whatever a developer or another lane last built for a
simulator — and on a shared checkout with several lanes live, "last build was
mine" is not an assumption a release script may make.

Worth pairing with a check that fails EARLY: `vtool -show-build-version` on
each embedded framework before the ~12-minute archive, rather than discovering
it from App Store Connect at the end.

## Cross-lane note

Not CR162's fault — a simulator build is a legitimate thing to run, and this is
a Flutter path-collision. But the two lanes now share a build directory that
cannot represent both platforms at once, so whichever runs second wins and the
other's next build is wrong. Fix it in the release scripts, which are the ones
with something to lose.
