# CR016 — E4/D8: HexBottomNav (impl CR under CR004)

**Parent:** [CR004 release-readiness](../CR004_release_readiness/CR004_release_readiness.md) · design home
[design_system_audit.md §D8](../CR004_release_readiness/design_system_audit.md).

## What

Replace the stock Material `BottomNavigationBar` in `home_shell.dart` with the mobile kit's signature
`HexBottomNav`: five hex-clipped destination pills; the active pill fills with a purple→blue brand
gradient + glow (the "center brand cell" treatment), inactive pills are muted icon+label. **Material
semantics preserved** — same five destinations (Floor / Portfolio / Journal / Lessons / Settings),
full-cell touch targets, `Semantics(button, selected)` per cell — only the visuals change.

## Why

Plan D "attractiveness" — the audit called C2 "the single biggest on-system visual jump: the nav is
on screen 100% of the time." The stock Material bar was the most-seen off-motif element. No new
dependency.

## Scope

- New: `widgets/hex/hex_bottom_nav.dart` (`HexBottomNav` + `HexNavItem`).
- Edit: `home_shell.dart` — swap `BottomNavigationBar` → `HexBottomNav` (same `currentIndex`/`onTap`,
  same 5 destinations, unchanged `TickerTape` + `MediaQuery.removePadding` wrapper). No backend change.

## Acceptance

- `flutter analyze` clean (baseline 4 pre-existing, 0 new); `flutter test` green (nav renders 5 +
  taps route to the right index).
- **NEEDS-DEVICE-CHECK:** the five hex pills render; the active pill glows purple→blue; tab switching
  works with no touch-target regression; the TickerTape still sits below.

## Governance

Commit tag `(AT:R53 CR016)`. Scope-clean commits (widget / swap + test). Audit lane
`audit/handshake/cr/CR016.*`.
