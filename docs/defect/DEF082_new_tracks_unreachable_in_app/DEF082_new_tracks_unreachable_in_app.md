# DEF082 — 6 new training groups (64 lessons) are unreachable in the app

**Source:** `prompt` (Saiful: *"CR059 added 6 new training groups. I cannot see them on android or ios"*) ·
**Filed:** 2026-07-22 (AT:R64) · **Severity:** high — 19% of the shipped corpus is dark on every platform ·
**Status:** open

## Symptom

The Lessons screen shows only the original 7 training groups. The 6 groups added by CR054 Wave-1 and
CR058 never appear, on **both** Android and iOS. Tapping through to them is impossible.

## Impact — measured against the live Alpha backend

`GET /v1/lessons?locale=en` on melehost returns **12 tracks / 334 lessons**. The app renders 7 of them.

| Track | Lessons | Reachable in app |
|---|---|---|
| foundations | 16 | ✅ |
| fundamentals_analysis | 66 | ✅ |
| technical_analysis | 45 | ✅ |
| news_macro | 19 | ✅ |
| sentiment_behaviour | 10 | ✅ |
| risk_portfolio | 16 | ✅ |
| edge_process | 98 | ✅ |
| **asset_classes** | **20** | ❌ |
| **economics_macro** | **12** | ❌ |
| **quant_methods** | **12** | ❌ |
| **ethics_integrity** | **10** | ❌ |
| **islamic_finance** | **10** | ❌ |
| **decision_evaluation** | **0** | ❌ (no content authored — see below) |

**Reachable 270 · unreachable 64 · served 334.** The reachable count is *exactly* the pre-CR054 corpus
size — i.e. **every lesson delivered by CR054 Wave-1 and CR058 is dark**, including all 10 SHARIA lessons
that CR058 shipped and the backend promote put live.

## Root cause

`mobile/lib/screens/lessons/lessons_screen.dart` renders the group cluster from a **hardcoded `origins`
map of exactly the original 7 tracks**, and the render loop iterates *that map* rather than the API
response — the backend list is used only as a filter:

```dart
final origins = {                                   // 7 hardcoded positions
  'technical_analysis':    Offset(hexW * 0.75, 0),          // N
  'news_macro':            Offset(hexW * 1.5,  hexH * 0.5), // NE
  'sentiment_behaviour':   Offset(hexW * 1.5,  hexH * 1.5), // SE
  'edge_process':          Offset(hexW * 0.75, hexH * 2),   // S
  'risk_portfolio':        Offset(0,           hexH * 1.5), // SW
  'fundamentals_analysis': Offset(0,           hexH * 0.5), // NW
  'foundations':           Offset(hexW * 0.75, hexH),       // centre
};
final trackMap = {for (final t in tracks) t.track: t};

for (final entry in origins.entries)          // ← iterates the hardcoded 7
  if (trackMap.containsKey(entry.key))        // ← API response only filters
    ... TrackHexButton ...
```

Any track the backend serves that has no `origins` entry is **silently dropped**. `_trackColor` and
`_trackLabel` (same file) are likewise 7-entry maps. The screen's own docstrings fix the shape:
*"Zone B: 7-hex honeycomb cluster (1 centre + 6 surrounding tracks)."*

**Only one entry point exists** — `TrackLessonsScreen` is constructed solely at `lessons_screen.dart:153`
from `onTrackTap`, which is wired exclusively to those hex buttons. So there is no alternate route to the
missing groups (no search, no list, no deep link surfaced in the UI).

### Why CR059-MOBILE did not fix it

CR059-MOBILE (`f188d7b`) added `islamic_finance` / `decision_evaluation` to `_trackShortLabel` in
`track_lessons_screen.dart` — the **detail** screen. That screen already handles all 13 correctly. The
**index** (`lessons_screen.dart`) was never in scope, so the groups remained unreachable and the label
work is currently unobservable.

### Why this is not a build-version issue

- **iOS `+46`** contains both CR059-MOBILE (`f188d7b`) and CR053-MOBILE (`921f15f`) and still cannot show
  them — proving the defect is in the code, not the build.
- **Android Play `+44`** predates all of it (`c926cc3`, the +44 bump, is the first commit in that range),
  so Android is additionally stale — but shipping a newer Android build alone would **not** fix this.

## Failure class — third repeat

This is the CLAUDE.md **degrade-loudly** class: a feature gated on a hardcoded config silently rendering
nothing instead of failing visibly. CLAUDE.md already records *"Twice now a shipped feature was dark for
months for want of that one line (DEF038, DEF063)."* This is the third, and the most expensive: a full
content programme (CR054 Wave-1 + CR058, 64 lessons) shipped to production and was never visible.

Per CLAUDE.md ("Second occurrence of anything ⇒ add an entry **with a guard**"), the fix must include a
guard, not just the missing entries.

## Fix direction

1. **Render from the API, not from a hardcoded map.** The track list must be driven by the response so a
   backend-added track can never be invisible again. Position/colour/label lookups may stay as styling
   hints, but an unknown track must still render (deterministic fallback colour + `track.title`, which the
   API already supplies).
2. **Layout decision required (Saiful's call).** The cluster is architecturally a 7-hex honeycomb; there
   are now 12–13 groups. This is a visible design change and needs a direction before implementation —
   options and trade-offs to be put to Saiful.
3. **Guard.** A test asserting every track in the catalogue fixture is rendered (or at minimum that the
   count of rendered groups equals the count served), so a future taxonomy addition fails the build rather
   than going dark.
4. **`decision_evaluation` has 0 lessons** — the 13th facet is wired end-to-end but unauthored. Content
   task, tracked separately; it must not block the layout fix.

## Cross-refs

- **CR059** — 13-facet taxonomy (backend `a63d1c5`, mobile labels `f188d7b`).
- **CR054 Wave-1** — ETHIC/ASST/MACRO/QUANT lessons (54 of the dark 64).
- **CR058** — 10 SHARIA lessons (the remaining 10 dark), shipped live in the AT:R64 promote.
- **DEF038 / DEF063** — prior degrade-loudly repeats named in CLAUDE.md.

---

## Resolution (AT:R64, 2026-07-22)

**Status: FIXED.** Layout direction approved by Saiful after reviewing a live mock —
*"how about this way"* (the 13-agent comb from the marketing site), then
*"colours look ok"*, then *"lets deploy the new 13 hex modules on both android and apple"*.

### What shipped

**1. The count comes from the API and nowhere else.** New file
`mobile/lib/screens/lessons/honeycomb_layout.dart` holds the slot geometry, the fill order,
the colour map and the label map. `_HexCluster` now does
`for (var i = 0; i < ordered.length; i++)` over `orderTracksForHoneycomb(servedTracks)` —
there is no literal position map left to iterate. `honeycombCentreCount(n)` sizes the comb
to `n`, so a 14th track grows the comb instead of falling off it. An unknown track renders
with a cycled fallback colour and `track.title` from the response.

**2. Layout — 3 columns, 4/5/4.** Transposed from `website/index.html`'s own 13-cell
honeycomb (the one that represents the 13 agents), so app and marketing site now share a
geometry. Three columns means `2.5 · hexW = maxWidth`, i.e. **hexW is unchanged at ~143 pt**
— all 13 fit at full prose labels, nothing shrank. Cost is height: 372 → 620 pt, so the
cluster scrolls. `foundations` keeps the visual centre (C2).

**3. Colour as the boundary layer.** Saiful: *"select the colours such that they are distinct
from the neighbours, so we can use the colours also as the design boundary layers."* Six new
tokens in `ami_theme.dart`, chosen by maximising the **minimum** OKLab ΔE across the comb's
26 adjacent pairs (max-min, not max-average — the weakest seam is what the eye finds):

| token | hex | track |
|---|---|---|
| `hexOrange500` | `#F97316` | `asset_classes` |
| `hexLime400` | `#A3E635` | `economics_macro` |
| `hexGreen400` | `#4ADE80` | `quant_methods` |
| `hexIndigo600` | `#4F46E5` | `ethics_integrity` |
| `hexFuchsia500` | `#D946EF` | `islamic_finance` |
| `hexRose400` | `#FB7185` | `decision_evaluation` |

Weakest seam **ΔE 0.3278** at 13 tracks, **0.3415** at 12 — against **0.1807** for the
shipped palette's own closest pair (`hexPink`/`hexRed`) and 0.2306 for `hexBlue`/`hexCyan`.
Global distinctness across 13 is not achievable in this palette; adjacency distinctness is,
which is exactly what was asked for.

**4. Slot order is fixed, and `decision_evaluation` is last.** The separation is a property of
the *placement*, not of the palette (`hexRose400` sits ΔE 0.12 from `hexRed` globally), so
re-sorting by lesson count or alphabetically would let near-identical colours touch. EVAL is
pinned to the final slot because it is registered with zero lessons until CR062 lands — the
live API serves 12 tracks, and an absent EVAL must end the comb early rather than punch a
hole in the middle of it.

**5. Contrast.** `readableOnCanvas()` in `ami_theme.dart` lifts any accent below 4.2:1 on
`slate900` (the floor set by the dimmest already-shipped token, `hexPurple`). Only
`hexIndigo600` trips it today at 2.84:1; the hex fill keeps the true brand colour, the label
and progress arc get the lifted ink. Deriving it means the next dark token is covered without
a code change.

### The guard (CLAUDE.md: second occurrence ⇒ add a guard)

`mobile/test/honeycomb_layout_test.dart`, 8 tests:

- every served track gets a slot, exactly once, for n = 1…16 — the direct
  rendered-count == served-count assertion the defect demanded;
- unknown tracks survive and never shift the known placements;
- every one of the 13 backend tracks has a slot order, a colour and a label;
- no two adjacent hexes fall below ΔE 0.30, at both 12 and 13 tracks — this is what catches
  a future reorder silently undoing the colour solve;
- every label ink clears the contrast floor;
- geometry: centre column one taller than the sides; columns at 0, ¾W, 1½W; an unauthored
  track empties the **last** slot, not a middle one.

### Verification

- `flutter test test/honeycomb_layout_test.dart` — 8/8.
- Live `GET /v1/lessons` returns 12 tracks / 334 lessons; the comb renders 12 with the 13th
  slot empty, and will render 13 the moment CR062 promotes.

### Regression introduced and fixed in the same round — `+47` shipped hexes at 2x

Saiful, on the `+47` build: *"the hexagons are far too large"*, then *"no way. they are HUMONGOUS in
android and IOS"*, then *"if you say that this was not changed, then something else went wrong
because each hex is MUCH bigger than before. you need to figure out why rather than just gloss it
over."* He was right and the first response — asserting the size was unchanged because the source
still read "⅖ × maxWidth" — was wrong.

The original line was:

```dart
final hexW = constraints.maxWidth * 2 / 5;                     // 0.40
```

The DEF082 refactor substituted the new named constant into it:

```dart
final hexW = constraints.maxWidth * 2 / honeycombWidthInHexes; // 2 / 2.5 = 0.80
```

The literal `5` was the denominator of the *fraction* `2/5`, not the cluster's width in hexes. They
are unrelated numbers that both describe the layout, which is exactly why the substitution looked
right. The comment immediately above it still read `// hexW = maxWidth * 2/5` — comment preserved,
code broken, and no test compared them. On a 358 pt content width every hex rendered at **286 pt
instead of 143**, a **716 × 1240** cluster inside a 358 pt column.

**Fixed** by making the fraction its own named constant at its true value,
`honeycombHexWidthFraction = 0.40` — the size the 7-hex flower shipped with, which is what Saiful
asked for (*"use the previous size please, just extended by two lines"*). Five rows at that size is
620 pt and scrolls; that is inherent to the layout he chose, not a sizing problem.

**Guard:** `honeycomb_layout_test.dart` now asserts
`honeycombHexWidthFraction * honeycombWidthInHexes <= 1.0` and that no slot's right edge exceeds the
box. The bad value is 2.0 against that bound, so the build fails instead of shipping. The lesson is
narrower than "degrade loudly" — a *dimensionless ratio* and a *count* are not interchangeable even
when both are literals in the same expression, and geometry needs at least one assertion tying the
rendered extent back to the space it was given.

Interim `0.1.0+48` (fraction 0.30) was built but **never shipped** — it was shrinking against the
wrong baseline. `0.1.0+49` carries the correct 0.40.
