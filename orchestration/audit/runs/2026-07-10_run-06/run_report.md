<!--
Auditor run report — CR012 round 1, run-06 (2026-07-10, session AT:U1).
C4 share cards (offscreen ShareCard → PNG → OS share sheet). Flutter-only.
Owner: AMI Trade AUDITOR (track U).
-->

# CR012 — audit run-06 (round 1)

- **Auditor session:** AT:U1 (track U), 2026-07-10
- **Audited SHA:** `4ff1005` (CR012 head, on origin/main; built on CR011
  COMPLETE `4bc2652`). `depends-on: none`.
- **Equivalence:** `git diff 4ff1005..HEAD -- mobile/` empty + clean mobile tree
  → live `mobile/` == committed SHA. Only lane-doc commit after. No backend change.

## Commands run + observed output

### 1. flutter analyze / test (re-run)
```
$ (cd mobile && flutter analyze) → 4 issues (all pre-existing infos, 0 new)
$ (cd mobile && flutter test)    → 5 passed (1 app-render + 4 ShareCard template tests)
```
Match the claim. ✅ The 4 new tests pump every template and assert build +
`takeException() == null`.

## Compliance-critical checks (simulation-only, not investment advice)

### No P&L on the verdict share card — SATISFIED BY DESIGN + at the call site
- **Type-enforced:** `VerdictShareData` (`share_card.dart:33-45`) has only
  `ticker` / `stanceLabel` / `reason` (+ kicker/accent). There is **no field**
  for price, size, quantity, or P&L — the type structurally cannot carry them.
- **API-enforced:** `ShareService.shareVerdict` (`share_service.dart:26-45`)
  accepts only `ticker / stanceLabel / isApprove / reason` — no numeric/P&L
  parameter exists.
- **Call-site confirmed:** `room_screen.dart` passes
  `shareVerdict(ticker: ticker, stanceLabel: l.roomVerdictHeading(verdict.action),
  reason: verdict.reason)` — ticker + stance + reasoning excerpt only. No
  price/qty/P&L. ✅
- The other three payloads (Streak days/unit, Unlock name/abbrev, Promotion
  tier/rank/week) carry no monetary data either.

### Disclaimer on every card — SATISFIED
- `ShareCard.build` (`share_card.dart:130`) renders `_DisclaimerStrip` as shared
  chrome outside the template `switch`, so **all four** templates carry it.
- Text: `disclaimerShort` = **"Educational simulation. Not investment advice."**
  (l10n comment instructs translators to keep the clause in every locale).
- `shareCaption` (share-sheet text) also carries "Educational simulation — not
  investment advice." Double coverage (image + caption). ✅

## New-dependency governance
- `share_plus ^10.1.4` — **pre-approved** in the CR004 build spec
  (`build_mobile_engagement.md:4`, `plan_c...:67`). ✅
- `path_provider ^2.1.5` — not named in the R52 plan but disclosed in the CR012
  doc, and it's the standard first-party plugin needed to obtain a temp path for
  the PNG the pre-approved `share_plus` flow shares. Reasonable + flagged. ✅

## share_service.dart lifecycle (read `share_service.dart:110-185`)
- OverlayEntry inserted off-screen, **removed in a `finally`** → no leak even on
  exception. `image.dispose()` after `toByteData`. Overlay/boundary-null →
  return null (guarded). ✅
- Context read **before** any await (`l`, `box`/`origin` captured up front;
  `_rasterize` uses `context` synchronously before its first await) — analyzer's
  0-new confirms no `use_build_context_synchronously`. ✅
- `MediaQuery(textScaler: linear(1))` pins text scale → deterministic 1080×1350
  layout regardless of device font scaling. ✅

## Deliberate deviation (assessed — acceptable, disclosed)
Streak share homed on the persistent `StreakChip` (tap → share) rather than the
transient 600ms B1 celebration burst, which carries no day-count payload and has
no persistent surface for a button. Sound call; the chip always has
`LeagueMe.streak.current`. Verdict/unlock/promotion wired as specced.

## Observation (minor, non-blocking / future)
**O1 — forced LTR on the share card.** `_rasterize` wraps the card in
`Directionality(TextDirection.ltr)`. Fine for the EN-only alpha, but when AR
(RTL) ships at v1.0 the share card will mis-layout Arabic text. Low-priority,
pre-v1.0 — derive directionality from the locale when AR lands.

## Closure on the CR011 audit (verified in passing)
**CR011 M2 FIXED** (`85259b0`): `releg = total >= 10 && member.rank > total - 5`
— the red relegation tint is now gated on `MIN_COHORT_FOR_RELEGATION`, exactly
as recommended. Confirmed by diff read.

## NEEDS-DEVICE-CHECK
Runtime: each entry point opens the OS share sheet with a rendered image (iOS +
Android); hex-mesh watermark + Plex fonts paint into the PNG (60ms settle
timing); verdict image carries no price/P&L; disclaimer legible. Engine +
platform channels required — Saiful's acceptance test covers; a blank/garbled
capture reopens the lane.

## Verdict
Zero BLOCKER + zero MAJOR. The compliance-critical property (no P&L on the
verdict card + "not investment advice" on every card) is satisfied by design and
at the call site. One minor future observation (O1, RTL). → **COMPLETE (round 1)**.
