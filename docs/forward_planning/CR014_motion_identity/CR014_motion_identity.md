# CR014 — E3/D2+D3: motion identity — pulse loader, avatar/chip/button glow, count-up (impl CR under CR004)

**Parent:** [CR004 release-readiness](../CR004_release_readiness/CR004_release_readiness.md) · design home
[build_animations_motion.md §D2–D3](../CR004_release_readiness/build_animations_motion.md) +
[design_system_audit.md §C6/C7](../CR004_release_readiness/design_system_audit.md). D-061 (coded
Flutter, no Lottie).

## What

The app-wide motion layer that makes the app read on-motif, not just on-palette:

1. **`HexPulseLoader`** (D2) — new `widgets/hex/hex_pulse_loader.dart`: one hex outline breathing
   scale 0.92↔1.08 + glow 0.3↔0.7, 1600ms easeInOut repeat. Replaces the bare
   `CircularProgressIndicator` at the auth gate, Room deliberation footer, and chart loading.
2. **`HexAvatar` pulse** (D3) — animate the documented-but-static `signal`/`attention` glow states:
   a low-frequency (2200ms) glow-opacity pulse; `attention` = stronger + amber tint. Wire `signal`
   on the Floor for an unlocked-but-unvisited agent and on the Room's active-speaker roster row.
3. **Portfolio count-up** (D3 micro-motion) — the total value animates a `TweenAnimationBuilder`
   count-up (400ms) on change.
4. **C6** — repair the dead `HexButtonVariant.glow`: render a real `AmiShadow.glowBlue/glowPurple`
   `BoxShadow` instead of falling through to `outlined`.
5. **C7** — `HexChip` status dot pulses for live/warn states instead of sitting static.

## Why

Plan D "attractiveness": the design-system audit found "promised-but-static motion" as the core gap.
These are the always-on-screen motifs (loader, avatar glow, nav-adjacent chips) — the highest-leverage
on-motif wins. No new dependency (D-061).

## Scope

- New: `widgets/hex/hex_pulse_loader.dart`.
- Edit: `hex_avatar.dart` (pulse), `hex_button.dart` (C6 glow), `hex_chip.dart` (C7 pulse-dot),
  `app.dart` + `room_screen.dart` + `ticker_chart.dart` (loader swap-ins), `floor_screen.dart` +
  Room roster (signal wiring), Portfolio total (count-up). No backend change, no new dep.

## Deferred (disclosed) — native splash + icon-regen (D2 remainder)

The **native splash** (iOS `LaunchScreen.storyboard` + asset catalog, Android 12 splash) and the
**icon-regen trap** (`pubspec.yaml` `flutter_launcher_icons`, Plan A DEF #8) are **deferred to their
own follow-up CR**: they need a hex-logomark source asset + the `flutter_native_splash` dev-dependency
+ platform-project edits + the DEF #8 restore-or-delete decision — all native config that only
verifies on a cold-start device build, distinct from this app-level motion layer. Filed as a note; a
CR will open when the logomark asset + decision are ready.

## Acceptance

- `flutter analyze` clean (baseline 4 pre-existing, 0 new); `flutter test` green (+ pulse/glow build tests).
- **NEEDS-DEVICE-CHECK:** loader breathes at every loading state; an unlocked-unvisited Floor agent +
  the Room active speaker pulse; portfolio value counts up on trade; glow button + pulse-dot read on-system.

## Governance

Commit tag `(AT:R53 CR014)`. Scope-clean commits. Audit lane `audit/handshake/cr/CR014.*`.
