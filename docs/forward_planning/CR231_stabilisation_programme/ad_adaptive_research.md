# Adaptive banner across form factors — the banner at true type size

Source: `/private/tmp/claude-501/-Volumes-Extreme-Pro-AMI-MarketApp/3b407fa5-.../scratchpad/ad-adaptive.html`
(claude.ai artifact + `/tmp` scratchpad, at risk of loss). Date: 2026-09-23.
**Internal research, not user-facing.** Backs [CR226](CR226_adaptive_banner_slot/CR226_adaptive_banner_slot.md)
(the anchored-banner option from [ad_placements_research.md](ad_placements_research.md)).
Converted to markdown and preserved here under [CR231](CR231_stabilisation_programme.md).
The original draws every frame at one shared scale (1dp = 0.46px) so type is the same
physical size across frames — how Flutter actually renders a fixed `fontSize`; a
larger screen shows more content, never larger text. Real sizes are from
`ami_theme.dart`: statBig 42 · h1 32 · h2/statMid 24 · h3 18 · h4/bodyLg/dataMd 16 ·
body 14 · bodySm/statSmall 13 · labelMono 12 · caption 11 · ticker 10 (inline
override).

## Phones — one slot, no adaptation

The banner is 50dp on all phone form factors; only the amount of visible content
changes, never the type size.

| Form factor | Logical size | Banner | 20% cap | Layout work |
|---|---|---|---|---|
| iPhone SE / mini | 375 × 667 | 50dp | 133dp | None |
| iPhone 13–17 | 390 × 844 | 50dp | 169dp | None |
| iPhone Pro Max | 430 × 932 | 50dp | 186dp | None |
| Pixel / Galaxy S | 412 × 915 | 50dp | 183dp | None |
| Z Fold 7 cover | 540 × 1260 | 50dp | 252dp | None |
| Z Fold 7 inner | 984 × 1092 | ~90dp | 218dp | **Two-pane** |
| iPhone Fold inner (rumoured) | ~1024 × 1450 | ~90dp | 290dp | **Two-pane** |

## Folding — the banner scales, the layout doesn't

- **Z Fold 7 cover (540 × 1260dp):** works unchanged — tall narrow phone, 50dp slot.
- **Z Fold 7 unfolded, today (984 × 1092dp, 1-pane):** this is what ships today —
  12pt type marooned in 984dp-wide cards. The 90dp banner is the best-composed
  element on the screen.
- **Z Fold 7 unfolded, two-pane (proposed):** same banner, same type — the fix is
  columns, not font size. A separate CR from the ad work.
- **iPhone Fold inner (rumoured, ~1024 × 1450dp):** taller, so the 20% cap never
  binds. Specs leaked, not announced — treat as directional only.

## Accessibility text scaling — the real finding

`app.dart:49` has no `builder:` and the app sets `textScaler` nowhere except
share-card export. So Flutter's default applies: **the OS font-size setting
multiplies every size in the app.** iOS Dynamic Type reaches ~3.1×; Android's slider
reaches 2.0×. The chrome heights are hard-coded — header 64, nav 64, tape 28 — and
do not grow with it.

- **iPhone 13, scale 1.0× (baseline):** everything fits as designed.
- **iPhone 13, scale 2.0×:** chrome breaks, banner doesn't. The 64dp header and 28dp
  tape are fixed; their text doubles inside them. The AdMob banner is unaffected —
  the SDK renders its own view outside Flutter's text scaling.
- **iPhone SE, scale 3.1× (worst case, 667dp tall):** pre-existing, ads or not.
  Smallest screen × largest scale. The nav's `FittedBox` saves its labels; the
  header title has no such guard.

## The banner is the least risky element here

AdMob renders its creative in a platform view the SDK owns, so Flutter's
`textScaler` doesn't reach it — a user at 3.1× Dynamic Type gets the same 50dp
banner. And the 20% cap is computed in dp, so font scale never enters that
calculation either.

Feed it width from a `LayoutBuilder`, not `MediaQuery`, and **dispose and reload on
resize** — a banner sized for 390dp is wrong the instant the device unfolds. That
single call covers every row in the table above.

## Two pre-existing gaps this exercise surfaced

1. **No text-scale clamp.** `app.dart` has no `builder:`, so the OS scale applies
   unbounded to the 64dp header, 64dp nav and 28dp tape. The nav has a `FittedBox`;
   the header title has none. Most apps clamp to ~1.3× on fixed chrome while leaving
   body text free.
2. **Portrait lock doesn't stop unfolding.** `main.dart:69` locks `portraitUp` —
   that prevents rotation, not a window resize to 984dp. An unfolded Fold gets the
   stretched 1-pane screen today.

Neither gap is caused by ads, and neither should be fixed inside an ads CR — but
both become more visible once a bordered ad sits in the chrome.
