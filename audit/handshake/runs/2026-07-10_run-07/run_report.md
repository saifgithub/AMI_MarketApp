<!--
Auditor run report — CR013 round 1, run-07 (2026-07-10, session AT:U1).
E3/D1 lesson animation chassis + 7 CustomPainter primitives + 15-slot registry
(D-061: coded Flutter, no Lottie, zero deps). Flutter-only. Owner: AUDITOR.
-->

# CR013 — audit run-07 (round 1)

- **Auditor session:** AT:U1 (track U), 2026-07-10
- **Audited SHA:** `2eaf787` (CR013 head, on origin/main; built on CR012
  COMPLETE `7c1e764`). `depends-on: none`.
- **Equivalence:** `git diff 2eaf787..HEAD -- mobile/` empty + clean mobile tree
  → live `mobile/` == committed SHA. No backend change.

## D-061 compliance (locked decision: coded Flutter, no Lottie, zero deps)
- `git diff -- mobile/pubspec.yaml` across the CR013 range is **empty** → **zero
  new deps**. ✅
- `git grep -i lottie mobile/lib` finds only docstrings stating "no Lottie" — no
  import, no dep. ✅

## Correctness-critical: registry ↔ lesson content key coverage
The registry maps 15 keys → `AmiAnimation` builders; a lesson whose
`<Animation name="…">` isn't registered renders `AmiHexPlaceholder`. I extracted
the keys **independently from both sides** (not the test's list — non-circular):
```
$ grep -oE "'[a-z_]+':" animation_registry.dart      → 15 keys
$ git grep -rhoE '<Animation name="[a-z_]+"' content/lessons/*.mdx | ... | sort -u → 15 keys
$ comm -23 mdx registry   (in MDX, not registered → placeholder!)  → NONE
$ comm -13 mdx registry   (registered, unused → dead entry)        → NONE
```
**Exact match, both directions.** Every lesson animation slot resolves to a real
primitive; no placeholder in any of the 15 lessons; no dead registry entries.
(`risk_pyramid` from an earlier crude grep was a false hit — absent from all MDX.)

## Commands run + observed output
```
$ (cd mobile && flutter analyze) → 4 issues (all pre-existing infos, 0 new)
$ (cd mobile && flutter test)    → 8 passed
```
The new `lesson_animation_test.dart` asserts all 15 slots registered, each builds
its `AmiAnimation` (not the placeholder) with `takeException()==null` pumped
through the real `AnimationBlock`, and an unknown name → `AmiHexPlaceholder`. The
build sweep exercises all 7 painters' `paint()` paths. ✅ Matches claim.

## Chassis lifecycle (`ami_animation.dart`)
- `AnimationController` disposed in `dispose()`. ✅
- Scroll-into-view via `Scrollable.maybeOf(context)?.position` listener:
  attached in `didChangeDependencies` (removing the old listener before
  reassigning), removed in `dispose()` — no dangling listener / leak. ✅
- `_maybePlay` guarded (`_played`/`mounted`/`hasSize`), plays once at ≥60%
  visible; post-frame check covers slots already on-screen at first layout;
  tap/icon replay via `_controller.forward(from: 0)`. ✅

## Painter conventions (7 primitives in `anim/`)
- All 7 have a **const ctor** and **`shouldRepaint`**. ✅
- No raw `Color(0x…)` literals — colours are `AmiColors.*` (design-system
  palette: semantic bull/bear in candle, family palette in constellation) +
  `AmiAnimTheme`. On-system, per the stated convention. ✅

## Closure on the CR012 audit (verified in passing)
**CR012 O1 FIXED** `050eee4` — `_rasterize` now uses
`Directionality.maybeOf(context) ?? ltr`, so the share card follows the app
locale (RTL-ready for AR at v1.0). Addressed even the minor future note.

## Observations (trivial, non-blocking)
- The `'Replay'` `IconButton` tooltip (`ami_animation.dart:163`) is a hardcoded
  EN string — i18n debt for v1.0 (fine for the EN alpha).
- `candle`/`constellation` painters reference `AmiColors.*` directly for their
  fixed semantic/family palette rather than only through `AmiAnimTheme` — a
  pragmatic exception; still on-system, no literals.

## NEEDS-DEVICE-CHECK
The real verification surface: each of the 15 slots animating on scroll-into-view
+ tap-replay; motion reading as "precision, not carnival"; and **content-accuracy
of each primitive vs its lesson's concept** (params authored here, not derived).
Saiful's release build to device covers these — a wrong/janky slot reopens the
lane.

## Verdict
Zero BLOCKER + zero MAJOR. D-061 honoured; registry↔MDX coverage exact
(independently verified); chassis + painters clean. → **COMPLETE (round 1)**.
