# CR013 — E3/D1: lesson animation chassis + 7 primitives + registry (impl CR under CR004)

**Parent:** [CR004 release-readiness](../CR004_release_readiness/CR004_release_readiness.md) · design home
[build_animations_motion.md §D1](../CR004_release_readiness/build_animations_motion.md). Decision
**D-061** (2026-07-07): coded Flutter (`CustomPainter`), **no Lottie**, zero new dependencies.

## What

Replace the grey `AmiHexPlaceholder` in lesson animation slots with real motion. Three parts:

1. **Shared chassis** — `widgets/lessons/ami_animation.dart`: `AmiAnimation` — a 200px-tall
   `AccentCard`-framed canvas driven by a single `AnimationController` (default 2400ms,
   `easeInOutCubic`), plays once when ≥60% visible (a lightweight scroll-visibility check, no new
   dep), replay icon + tap-to-replay, optional `labelMono` caption. Bundles `AmiAnimTheme` (role
   accents from `ami_theme.dart`, stroke widths, label style) so every primitive renders on-system.
2. **7 `CustomPainter` primitives** in `widgets/lessons/anim/`, each parameterised via its
   constructor: `CurveDrawPainter`, `ThresholdTriggerPainter`, `BalanceScalePainter`,
   `OscillatorPainter`, `CandleAnatomyPainter`, `SequencePainter`, `ConstellationPainter`.
3. **Registry fill** — `animation_registry.dart`'s `_assets` map: `name → WidgetBuilder` returning
   the parameterised `AmiAnimation` for all 15 lesson slots. Unknown names keep the
   `AmiHexPlaceholder` fallback.

15 slots (per the D1 table): compounding_curve, fomo_curve, pump_dump_curve, drawdown_recovery,
stop_loss_trigger, support_resistance_test, breakout_pattern, position_size_calc, risk_reward_scale,
rsi_oscillator, moving_average_lag, candlestick_anatomy, bull_bear_states,
revenge_position_escalation, ami_constellation.

## Why

Plan D "attractiveness" — the app is on-palette but off-motif; the lessons show grey placeholders
where the spec promises motion. This is the single biggest content-quality gap in the education
surface. No new dependency (D-061).

## Scope

- New: `widgets/lessons/ami_animation.dart`, `widgets/lessons/anim/*.dart` (7 painters).
- Edit: `widgets/lessons/animation_registry.dart` (fill `_assets`).
- No backend change. No new dependency.

## Acceptance

- `flutter analyze` clean (baseline 4 pre-existing, 0 new); `flutter test` green (+ painter/registry
  widget tests where testable headless).
- **NEEDS-DEVICE-CHECK:** all 15 slots animate (no grey PLACEHOLDER remaining except the fallback);
  each plays on scroll-into-view + replays on tap; motion reads as "precision, not carnival".

## Governance

Commit tag `(AT:R53 CR013)`. Scope-clean commits (chassis / primitives / registry). Audit lane
`audit/handshake/cr/CR013.*`. Per-slot content-accuracy vs each lesson's MDX body is a device-check
item (the primitives are content-agnostic; the registry authors the params).
