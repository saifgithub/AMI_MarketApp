# Design-system audit — app vs `/Volumes/Extreme Pro/AMI AI Design System/`

Part of [CR004](CR004_release_readiness.md). Answers "did we look into improving the design?" with ground truth: the app was audited against the actual design-system mount (read-only) on 2026-07-07.

**Verdict:** color + typography discipline is genuinely strong — dark palette matches the v2 tokens to the hex, 408 `AmiTypography.*` references vs 24 hardcoded `TextStyle`, zero raw color literals in screens. The divergence is concentrated in four areas: **elevation/glow (entirely absent), glassmorphism (built but only used in the dev screen), signature components rendered as stock Material (bottom nav, period toggle, toasts), and promised-but-static motion.** That last cluster is exactly the "attractiveness weakness" — the app is on-palette but off-motif.

**Canonical source note:** the DS mount is internally inconsistent — `reference/hex-design-system.css` + the master md carry stale pre-v2 neutrals and Inter/JetBrains-first type. **`colors_and_type.css` is the v2 authority** (the app already tracks it). Audit was against v2.

---

## Token diff (fix-now items)

| # | Issue | App site | DS authority |
|---|---|---|---|
| T1 | `AmiMotion.slow = 350ms`, spec is 300ms | `ami_theme.dart:203` | `colors_and_type.css:90` `--dur-slow` |
| T2 | `AmiColorsLight.accentBlue = #1D4ED8`, spec is `#2563EB` (already in file as `hexBlue600`) | `ami_theme.dart:75` | `--accent-blue-text` |
| T3 | Default `fontFamily` is Inter — un-styled/Material text renders in the fallback face; DS: author against Plex, Inter is fallback-only | `ami_theme.dart:218,254` | DS `README.md:99,174` |
| T4 | Missing spacing steps `12` (+0, 64) — forces 8→16 jumps; missing radii `sm 4`/`md 6` | `ami_theme.dart:184-198` | `--sp-3`, `--radius-sm/md` |
| T5 | No shadow/glow tokens at all: `--shadow-card/modal`, `--glow-blue/purple` have no counterpart; **zero `BoxShadow` in the entire app** | `ami_theme.dart` (add `AmiShadow`) | `colors_and_type.css:80-83` |
| T6 | No `--border-light`/`--border-subtle` equivalents — every border is `slate700` | `ami_theme.dart` | `colors_and_type.css` |
| T7 | 4 type-ramp gaps: no 16px `body-lg`, no 13px sans `body-sm`, `caption` 12px vs spec 11px, `statSmall` w500 vs spec w400; no 16px mono `data-md` | `ami_theme.dart:103-178` | `colors_and_type.css:48-61` |

## Component gaps (DS defines → app uses stock Material)

| # | Gap | App today | DS reference |
|---|---|---|---|
| C1 | **Glassmorphism shelved**: `GlassPanel` (the app's only `BackdropFilter`) is imported by `dev_preview_screen.dart` alone; every real surface is flat opaque `slate800`. It also hardcodes the dark glass fill | `widgets/hex/glass_panel.dart:45`, `accent_card.dart:42` | "Backgrounds: never flat" — `README.md:102-106`, `hex-components.css:7` |
| C2 | **Bottom nav is stock Material** — the mobile kit's signature `HexBottomNav` (hex-clipped pills, center brand cell with purple→blue glow) never built | `home_shell.dart:55` | `ui_kits/mobile/README.md:17,25` |
| C3 | Chart period toggle is a rounded `ChoiceChip`, not the elongated-hex toggle (active = solid hexBlue + glow) | `widgets/ticker_chart.dart:144` | `hex-components.css:182-210` |
| C4 | Toasts are default `SnackBar` across 11 screens; DS ships a bespoke hex toast (clip-path, mono, accent border, slide-in) | brief/journal/portfolio/settings/trade-ticket… | `hex-components.css:212-289` |
| C5 | `logo_hex.svg` never used anywhere in-app; `HexMeshOverlay` texture used on exactly one screen (Floor) | `widgets/hex/hex_mesh_overlay.dart:24` | `assets/logo_hex.svg` |
| C6 | `HexButtonVariant.glow` is dead — declared, but `build()` only branches on `filled`, so `glow` renders as `outlined` | `widgets/hex/hex_button.dart:5,29-36` | glow motif, `colors_and_type.css:80` |
| C7 | `HexChip.showDot` status dot is static; mobile kit specs a pulse-dot for LIVE/WARN/OFFLINE | `widgets/hex/hex_chip.dart:86-91` | `ui_kits/mobile/README.md:22` |
| C8 | Mobile-kit atoms unbuilt: `MobKPI` tile, `ChatVizCard`, `SparkLine` ("where the agent shows its work") | — | `ui_kits/mobile/README.md:20,25` |

Motion gaps (HexAvatar static pulse, zero glow states) are already owned by [build_animations_motion.md](build_animations_motion.md) §D3 — C6/C7 above fold into that work.

## Execution — where this lands in the Engagement phase

**D0 — token-sync commit (~0.5 session, do FIRST — everything else builds on it):**
T1–T7 in one pass: fix the two wrong values, flip default family to Plex(+Inter fallback), add missing spacing/radius steps, add `AmiShadow` (shadowCard, shadowModal, glowBlue, glowPurple), add borderLight/borderSubtle, fill the type-ramp gaps. Pure `ami_theme.dart` + no visual regression risk beyond the font default (eyeball key screens after).

**Folded into existing build specs:**
- C6 (repair `glow` variant with real `BoxShadow`) + C7 (pulse-dot) → [build_animations_motion.md](build_animations_motion.md) §D3, alongside the HexAvatar pulse.
- Active period-toggle glow + Room roster glow states consume `AmiShadow` from D0.

**D7 — on-system components (~1 session, new D-item):**
- C1: `GlassPanel` gains a light-aware fill + use it on the three bottom sheets (`trade_ticket_sheet.dart`, `agent_action_sheet.dart`, `watchlist_sheet.dart`) — the signature look lands where users actually stare.
- C3: hex-clip the period selector (reuse `theme/hex_clipper.dart`, cornerCut 10).
- C4: `HexToast` widget + route the 11 `SnackBar` call sites through one helper.
- C5: `logo_hex.svg` into the app bar / splash (pairs with D2 branded splash).

**D8 — HexBottomNav (~0.5–1 session, RECOMMENDED but separable):**
C2. The single biggest "on-system" visual jump — the nav is on screen 100% of the time. Risk: touch-target regression; keep Material semantics (same 5 destinations), swap visuals only. If Engagement runs long, this is the first thing to cut.

C8 (KPI/sparkline atoms) — defer to Phase 2 alongside per-agent scorecards; no current screen needs them.

## Revised Plan D sizing

Plan D was ~4–6 sessions; +D0/D7/D8 ⇒ **~6–8 sessions**. Worth it: this doc is the concrete answer to objective (d) "attractiveness" — the palette was never the problem; the missing glow/glass/hex-component layer is.
