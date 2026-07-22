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
