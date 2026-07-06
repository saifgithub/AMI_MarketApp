# Plan D — Attractiveness (visual appeal + motion identity + store presence)

Part of [CR004](CR004_release_readiness.md). Goal: close the gap between the design language on paper ("Hex-Reinforced Precision") and what the app actually shows. The bones are good — hex clippers, role-accent palette, IBM Plex type, glass panels. What's missing is **motion, finish, and the first impression**.

**Estimated effort:** ~4–6 sessions (D1 dominates). D5 belongs to the MVP phase but is planned here.

---

## D1 — Lesson animations: kill the 15 placeholders (~2.5–3 sessions) — DECISION #2

15 lesson MDX files carry `<Animation name="…"/>` slots; all render a grey 180px "PLACEHOLDER" hex (`mobile/lib/widgets/lessons/animation_block.dart:36`; registry empty at `animation_registry.dart:22`; `lottie` not even in pubspec).

**Recommendation: coded Flutter (CustomPainter), not Lottie.** The 15 named slots are financial-chart concepts — they collapse into **7 reusable animated primitives**, each themeable with the existing palette, no new dependency, no design-tool pipeline for a one-person team:

| Primitive | Covers slots |
|---|---|
| Curve-draw (animated path reveal) | `compounding_curve`, `fomo_curve`, `pump_dump_curve`, `drawdown_recovery` |
| Threshold-trigger (line approaches level, fires) | `stop_loss_trigger`, `support_resistance_test`, `breakout_pattern` |
| Balance/scale | `position_size_calc`, `risk_reward_scale` |
| Oscillator (value + lagging companion) | `rsi_oscillator`, `moving_average_lag` |
| Candlestick anatomy (labeled build-up) | `candlestick_anatomy` |
| State toggle | `bull_bear_states` |
| Escalation sequence | `revenge_position_escalation` |
| Bespoke one-off | `ami_constellation` (12 agent hexes assembling — reuse as the Room-open animation, double value) |

Slot list: `content/lessons/{010,014,015,016,018,020,023,024,026,027,047,048,059,066,072}.mdx`, all line 22. Registry pattern already exists — implement primitives, map names in `animation_registry.dart`. This closes the deferred decision in `memory/project_animations.md`.

## D2 — Launch experience (~0.5 session)

First impression today: default Flutter `LaunchImage` storyboard → bare `slate900` + small cyan `CircularProgressIndicator` (`app.dart:89`).

- Branded native splash: hex logo on slate900, iOS storyboard + Android 12 splash API (`flutter_native_splash` or hand-edit — flag the new dep if taken).
- Replace the auth-gate spinner with a **hex pulse loader** (one hexagon, scale+glow breathing) — becomes the app's standard loading motif (reuse in Room footer, chart loads).
- Fix the icon-regen trap: `assets/icon/` source dir referenced by `pubspec.yaml:79` doesn't exist (Plan A DEF #8).

## D3 — Motion identity (~1 session)

- **Implement the documented-but-missing HexAvatar pulse**: the enum documents `signal`/`attention` as "pulsing glow" (`mobile/lib/theme/hex_avatar.dart:6`) but no animation exists and the states are never passed. Wire on the Floor: agent with a fresh unlock, unread 1-on-1 reply, or league event pulses gently. One `AnimationController`, low frequency — precision, not carnival.
- Room active-speaker: the currently-streaming agent's hex pulses (pairs with Plan B3's roster).
- Micro-motion pass: animated count-up on Portfolio total value, ticker-tape stays as-is (already good), chart crosshair stays as-is.

## D4 — Theme decision (~0.25 session) — DECISION #3

A full light theme exists (`amiLightTheme`) but is unreachable — 37 hard-coded `slate900/slate800` sites (A29), and the Settings toggle silently coerces back to dark (`settings_screen.dart:688`). **Recommendation: dark-only for v1.0.** Dark IS the brand ("trading floor at night"); fixing 37 call sites buys nothing at launch. Action: delete the dead toggle, replace with a static "DARK — floor standard" row, keep A29 in the backlog for v1.1.

## D5 — Store presence (MVP phase, feeds M2; plan now ~1 session + Saiful review)

- Screenshot set per store (6.7"/6.1" iOS, phone+7" Android), staged on the best surfaces: Floor honeycomb, Room mid-deliberation (with B3 roster), verdict card, chart fullscreen, league standings (post-C3). EN first; AR + MS at listing time.
- 15–30s preview video: onboarding → convene → verdict → trade → league. Script by Claude, capture by Saiful.
- ASO copy per store_compliance.md constraints (17+, education category positioning, no advice claims).
- App icon audit at all rendered sizes once D2's source dir is restored.

## D6 — Sound (explicitly skipped)

No sound design for v1.0. Haptics (Plan B1) carry the feedback channel; sound adds asset pipeline + mute-state complexity for marginal gain in a finance app. Revisit post-launch only on tester demand.

## Strengths to preserve (do not "improve")

Trade-submit success moment; LIVE/MOCK honesty pills; swipe-delete with undo; coach-mark tour system; the honeycomb Floor layout; glass chrome + role-accent discipline.

## Acceptance

- Zero "PLACEHOLDER" hexes render in any lesson; all 15 slots animate.
- Cold start shows branded splash → hex pulse → Floor; no default-Flutter frames.
- At least one live pulse state reachable on the Floor per session.
- Appearance section has no dead toggle.
- M2 asset checklist exists with owner marks (Claude produces, Saiful approves).
