# CR015 — E4/D7: on-system components — glass sheets, hex period toggle, HexToast, logo (impl CR under CR004)

**Parent:** [CR004 release-readiness](../CR004_release_readiness/CR004_release_readiness.md) · design home
[design_system_audit.md §D7](../CR004_release_readiness/design_system_audit.md).

## What

Land the four "app uses stock Material where the DS ships a signature component" gaps:

- **C1 — glass sheets:** apply `GlassPanel` (the app's only `BackdropFilter`, currently used on the
  dev screen alone) to the three bottom sheets users actually stare at: trade-ticket, agent-action,
  watchlist. The signature glassmorphism look lands where it counts.
- **C3 — hex period toggle:** replace the chart's rounded `ChoiceChip` period selector with an
  elongated-hex toggle (`FlatTopHexagonClipper`, cornerCut 10; active = solid `hexBlue` + glow).
- **C4 — HexToast:** a bespoke hex toast (clip-path, mono, accent border, slide-in) + one helper that
  routes the ~11 `SnackBar` call sites through it.
- **C5 — logo:** drop the bundled-but-unused `assets/logo_hex.svg` into an app bar.

## Why

Plan D "attractiveness": the design-system audit found signature components rendered as stock
Material (toasts, period toggle) + glassmorphism built-but-shelved. These are the on-motif wins that
close the "on-palette but off-motif" gap. No new dependency (uses `flutter_svg`, already present).

## Scope

- New: `widgets/hex/hex_toast.dart` (widget + `HexToast.show(context, ...)` helper), a hex period
  toggle widget.
- Edit: 3 sheet files (GlassPanel wrap), `ticker_chart.dart` (period toggle), ~11 SnackBar call
  sites → HexToast, one app bar (logo). `GlassPanel` gains a light-aware fill (dark-only pinned today
  per D-062, so a minor forward-compat touch). No backend change, no new dep.

## Acceptance

- `flutter analyze` clean (baseline 4 pre-existing, 0 new); `flutter test` green (+ HexToast/toggle build tests).
- **NEEDS-DEVICE-CHECK:** the 3 sheets show the frosted-glass look; period toggle switches + the active
  cell glows; toasts slide in as hex-clipped mono cards; the logo renders in the app bar.

## Governance

Commit tag `(AT:R53 CR015)`. Scope-clean commits (HexToast / toggle / glass sheets / logo). Audit lane
`audit/handshake/cr/CR015.*`.
