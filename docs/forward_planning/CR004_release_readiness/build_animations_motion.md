# Build spec — animations + motion identity (Plans D1–D4)

Part of [CR004](CR004_release_readiness.md). Implementation commits tag `(AT:R<N> CR004)`.
Decision D-061 locked 2026-07-07: coded Flutter (CustomPainter), no Lottie. Zero new dependencies in D1/D3/D4; D2 may take `flutter_native_splash` (flag at implementation).

---

## D1 — Seven animation primitives → 15 lesson slots

**Shared chassis** — `mobile/lib/widgets/lessons/ami_animation.dart` (new):

```dart
class AmiAnimation extends StatefulWidget {
  final CustomPainter Function(double t, AmiAnimTheme) painterBuilder;
  final Duration duration;        // default 2400ms
  final String? caption;          // labelMono under the canvas
}
```

- 200px-tall `AccentCard`-framed canvas; plays once when ≥60% visible (simple `ScrollNotification` visibility check — no new dependency), replay icon top-right, tap-to-replay. `AmiAnimTheme` bundles palette (role accents from `ami_theme.dart`), stroke widths, `labelMono` text style so all primitives render on-system.
- Curve default `Curves.easeInOutCubic`; keep every animation ≤3s, single controller.

**Primitives** (each a `CustomPainter` in `widgets/lessons/anim/`, params via constructor):

| # | Painter | Params | Slots (all `content/lessons/NNN.mdx:22`) |
|---|---|---|---|
| 1 | `CurveDrawPainter` — animated path reveal, optional area fill + annotation flags at t-stops | `points/generator, annotations[], accent` | `compounding_curve`(010), `fomo_curve`(048), `pump_dump_curve`(066), `drawdown_recovery`(018) |
| 2 | `ThresholdTriggerPainter` — price path approaches a dashed level; contact → flash + label | `level, path, triggerLabel, breach ? breakout : stop` | `stop_loss_trigger`(015), `support_resistance_test`(023), `breakout_pattern`(024) |
| 3 | `BalanceScalePainter` — two-pan scale animates to equilibrium as weights count up | `leftLabel/value, rightLabel/value` | `position_size_calc`(014), `risk_reward_scale`(016) |
| 4 | `OscillatorPainter` — main series + lagging companion; optional 30/70 band shading | `series, companionLag, band?` | `rsi_oscillator`(027), `moving_average_lag`(026) |
| 5 | `CandleAnatomyPainter` — one large candle assembles part-by-part with `labelMono` callouts (body, wicks, O/H/L/C) | `bullish: bool` | `candlestick_anatomy`(020) |
| 6 | `SequencePainter` — N staged scenes with crossfade; escalation variant grows size/red per step | `stages[], escalate: bool` | `bull_bear_states`(047), `revenge_position_escalation`(059) |
| 7 | `ConstellationPainter` — 12 role-colored hexes fly from edges into the honeycomb formation, Concierge pink lands last, connecting lines glow | — | `ami_constellation`(072) — **also reused as the Room-open moment (B3 upgrade, optional)** |

**Registry:** `widgets/lessons/animation_registry.dart` — fill the empty `_assets` map (`:22`) as `name → WidgetBuilder` returning the parameterized `AmiAnimation`. Unknown names keep the existing `AmiHexPlaceholder` fallback (`animation_block.dart:36`). Per-slot parameters (series shapes, labels, captions) are authored inline in the registry — content-accurate values checked against each lesson's MDX body during implementation.

Sizing: chassis + primitives 1–3 (1 session) · 4–6 (1) · 7 + registry param pass over all 15 + device check (0.5–1).

## D2 — Launch experience

- **Native splash:** hex logomark centered on `slate900 #0F172A`. iOS: replace default `LaunchImage` in `ios/Runner/Base.lproj/LaunchScreen.storyboard` + asset catalog. Android: `android12`-style splash (`windowSplashScreenBackground` + animated-icon-capable drawable). Prefer `flutter_native_splash` to hand-editing (one dev-dependency, generates both platforms consistently) — flag when taken.
- **`HexPulseLoader`** (new, `widgets/hex/hex_pulse_loader.dart`): one hex outline, scale 0.92↔1.08 + glow opacity 0.3↔0.7, 1600ms `easeInOut` repeat. Replace the bare cyan `CircularProgressIndicator` in `_AuthGate` (`app.dart:89`); reuse in Room footer while deliberating and chart loading states. This becomes the app-wide loading motif.
- **App icon — SHIPPED (AT:R54).** The stock Flutter logo is gone on both platforms. Saiful directed a from-scratch design (there was no pre-existing artwork anywhere — the iOS 1024 was still the stock logo, and the design-system mount only had a 30×26 in-app UI glyph). Concept chosen from a 5-option + C×D-mix study: **"Diagonal duo"** — two candlesticks whose bodies are the AMI point-up hexagon, green bull (`#10B981`) rising upper-left, red bear (`#EF4444`) falling lower-right, cyan (`#06B6D4`) wicks growing from the tips, on the slate-900 canvas with a soft blue radial glow. Rendered pixel-exact via a Pillow 4× supersampled script (no cairo/SVG dep on the Mac): 3 masters at `mobile/assets/icon/` (`ami_icon_hires` opaque · `ami_icon_foreground` transparent, sized so the tool's 16% inset lands the motif at ~64% of the adaptive cell · `ami_icon_background` slate+glow). iOS: all 15 `AppIcon.appiconset` sizes regenerated (RGB, no alpha, per Apple). Android: `dart run flutter_launcher_icons` → legacy mipmaps + adaptive `foreground`/`background` drawables + `mipmap-anydpi-v26`. Reproducible: `python3 scripts/render_app_icon.py` (regenerates the 3 masters + all iOS sizes) then `cd mobile && dart run flutter_launcher_icons` for Android — re-run both if the artwork ever changes. Ships on the next device build (`flutter build ios --release` / Android AAB) — no backend promote involved.

## D3 — HexAvatar pulse (the documented-but-missing motion)

`theme/hex_avatar.dart:6` documents `signal`/`attention` glow states as "pulsing glow"; no animation exists and nothing passes those states.

- Implement: when `glow == signal|attention`, drive the existing radial-gradient glow opacity with a low-frequency controller (2200ms, subtle — precision, not carnival). `attention` = slightly stronger amplitude + amber tint.
- **Wire on the Floor** (`floor_placeholder_screen.dart` honeycomb): `signal` for an agent with a fresh unlock not yet visited via 1-on-1; `attention` reserved for future nudges (mandate drift, league events) — plumb the prop, keep triggers minimal at first.
- **Room active speaker:** the currently-streaming agent's roster row (B3) pulses `signal`.
- Micro-motion: Portfolio total value animates count-up on change (`TweenAnimationBuilder`, 400ms). Ticker tape + chart crosshair stay untouched.

## D4 — Dark-only for v1.0 (D-062)

`settings_screen.dart:671-688`: delete the mode-coercing toggle; replace with a static row `DARK — FLOOR STANDARD` (`labelMono`) + one-line note. Keep `amiLightTheme` in the codebase; A29 (the 37 hard-coded slate sites) stays in the backlog for v1.1. Remove the dead `themeMode` persistence path if one exists.

## Verify

`flutter analyze` clean → release build to iPhone 13 (`scripts/install_iphone.sh`): all 15 lesson slots animate (no grey PLACEHOLDER anywhere — grep the app for `AmiHexPlaceholder` usages should show only the registry fallback), cold start shows branded splash → hex pulse (no default-Flutter white frame), an unlocked-agent pulse is visible on the Floor, Appearance section shows the static row. Then Galaxy A17 for the Android splash path.
