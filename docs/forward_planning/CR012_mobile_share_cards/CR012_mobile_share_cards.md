# CR012 — C4: share cards (impl CR under CR004)

**Parent:** [CR004 release-readiness](../CR004_release_readiness/CR004_release_readiness.md) · design home
[build_mobile_engagement.md §C4](../CR004_release_readiness/build_mobile_engagement.md).

## What

Add shareable image cards. A new `ShareCard(template, payload)` widget renders **offscreen** at a
fixed 1080×1350 logical px inside a `RepaintBoundary`, is rasterised via `toImage`, written to a
temp file, and handed to the OS share sheet through `share_plus` `Share.shareXFiles`.

Four templates, all on `slate900` with a hex-mesh watermark, the AMI wordmark, and a disclaimer
strip (`disclaimerShort` — "Educational simulation. Not investment advice."):

| Template | Payload | Renders |
|---|---|---|
| `verdict` | ticker, stance, 2-line reasoning excerpt | ticker + stance chip + reasoning. **No prices / P&L.** |
| `streak` | day count | big hex + N-day streak |
| `unlock` | agent name + role colour | agent hex + name |
| `promotion` | tier + week | tier chip + week |

Entry points (share icon → build payload → `ShareService.share(...)`): the verdict card, the
streak-milestone celebration overlay, `AgentUnlockedScreen`, and league history rows.

## Why

Plan C4 (attractiveness / virality). Organic reach for a stealth alpha — a user sharing a streak
or an agent unlock is the cheapest install channel. Simulation-only framing enforced on every card
(disclaimer strip + no P&L on the verdict template) keeps us clear of investment-advice territory.

## Scope

- **New dependency:** `share_plus` (pre-approved in the R52 plan) + `path_provider` (temp dir) if not
  already present. Flag at implementation.
- New: `widgets/share/share_card.dart` (templates), `services/share/share_service.dart` (offscreen
  rasterise + share).
- Edits: add a share icon to the four entry points; ~6 l10n keys incl. `disclaimerShort`.
- No backend change.

## Acceptance

- `flutter analyze` clean (baseline 4 pre-existing infos, 0 new); `flutter test` green.
- **NEEDS-DEVICE-CHECK:** share sheet produces a real image on iOS + Android from each of the four
  entry points; verdict card carries no price/P&L; disclaimer legible.

## Governance

Commit tag `(AT:R53 CR012)`. One concern per commit (dep+l10n / share service+card / entry-point
wiring). Audit lane `audit/handshake/cr/CR012.*`.
