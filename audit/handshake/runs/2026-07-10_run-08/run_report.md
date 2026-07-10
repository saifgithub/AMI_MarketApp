<!--
Auditor run report — CR014 round 1, run-08 (2026-07-10, session AT:U1).
E3/D2+D3 motion identity (HexPulseLoader, HexAvatar pulse, count-up, C6/C7).
Flutter-only, no new dep. Owner: AMI Trade AUDITOR (track U).
-->

# CR014 — audit run-08 (round 1)

- **Auditor session:** AT:U1 (track U), 2026-07-10
- **Audited SHA:** `f3b3513` (CR014 head, on origin/main; built on CR013 COMPLETE
  `59b19ba`). `depends-on: none`.
- **Equivalence:** `git diff f3b3513..HEAD -- mobile/` empty + clean mobile tree
  → live `mobile/` == committed SHA. No backend change; pubspec unchanged across
  the CR014 range → **no new dep** (D-061). ✅

## Commands run + observed output
```
$ (cd mobile && flutter analyze) → 4 issues (all pre-existing infos, 0 new)
$ (cd mobile && flutter test)    → 14 passed
```
The new `motion_test.dart` covers HexPulseLoader / HexAvatar signal / attention
(badge) / status-switch-without-leak / HexChip pulse-dot / **HexButton.glow
renders a non-empty BoxShadow halo when enabled** (real C6 check); repeating
anims advanced via `pump(Duration)`. ✅ Matches claim.

## Controller lifecycle (riskiest dimension — read the source)
- **HexAvatar** (`hex_avatar.dart`): `_controller` disposed; `initState` +
  `didUpdateWidget(old.status != widget.status)` both call `_syncPulse`;
  `_syncPulse` starts `repeat(reverse: true)` **only if not already animating**
  and `stop()..value = 0` otherwise → repeats only while signal/attention,
  resets when idle, no leak; AnimatedBuilder subscribed only when `_shouldPulse`.
  Textbook-correct. ✅
- **HexPulseLoader** + **HexChip `_PulseDot`**: `SingleTicker`, `..repeat(reverse:
  true)`, `_controller.dispose()`. Unconditional repeat is correct — they're only
  *mounted* during loading / for LIVE-WARN pills, so there is no idle waste. ✅

## C6 — HexButton.glow repair (`hex_button.dart`, `3f524ee`)
`glow` was dead (fell through to `outlined`). Now `isFilled = filled || isGlow`
(renders filled) and, when `isGlow && _isEnabled`, the button is wrapped in a
`DecoratedBox` carrying the halo `BoxShadow` **behind** the `ClipPath` — so the
clip can't crop the shadow. Enabled-gated (no halo on disabled). The motion test
asserts a non-empty halo. Correct fix. ✅

## Portfolio count-up (`portfolio_screen.dart`, `7e78310`)
`TweenAnimationBuilder<double>(tween: Tween(end: portfolio.totalValue),
duration: 400ms)` — the **no-`begin`** idiom snaps to the value on first build
(no first-open sweep) and animates only when `end` changes. Correct, standard
Flutter idiom. ✅

## Deferrals (disclosed) — both accurate
1. **Native splash + icon-regen** — `flutter_native_splash` is absent from
   pubspec; genuinely deferred (needs a logomark asset + a dev-dep + cold-start
   device verify). ✅
2. **Floor unlocked-but-unvisited `signal`** — no `SeenAgents`/unseen-agent state
   exists (grep empty), so the Floor trigger genuinely needs new persistence. The
   `HexAvatar` gains the pulse capability and the **Room active speaker
   demonstrates it live** (`room_screen.dart` roster row now pulses `signal`). ✅

## Closure on the CR013 audit (verified in passing)
**CR013 replay-tooltip i18n FIXED** `8bfcbfc` — `tooltip: 'Replay'` →
`AppLocalizations.of(context).lessonReplay`. The observation is addressed.

## Register / scope
`cr_list.md:43` CR014 `in_progress`; folder doc present (with both deferrals).
One concern per commit: avatar `53904d1` / C6+C7 `3f524ee` / wiring `7e78310` /
test `f3b3513`.

## NEEDS-DEVICE-CHECK
Loader breathing at each loading state; Room active speaker pulsing while
streaming; portfolio value counting up after a trade (no sweep on first open);
glow CTA halo + pulse-dot reading on-system ("precision, not carnival"). Engine
required — Saiful's release build covers; a janky/absent motion reopens the lane.

## Verdict
Zero BLOCKER + zero MAJOR. No new findings — controller lifecycles clean, C6
repaired + tested, count-up idiom correct, deferrals accurate. → **COMPLETE
(round 1)**.
