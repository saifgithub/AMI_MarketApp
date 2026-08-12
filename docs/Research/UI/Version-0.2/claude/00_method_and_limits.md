# 00 — Method and limits

What this research measured, how, and what the numbers can and cannot say.

## Scope

Research only. No Flutter code changes, no CR minted, no register touched. The output is
evidence + two recommended redesign directions; building either is a future CR that Saiful
approves (or doesn't) with this folder as its evidence base.

## The two kinds of numbers

**Code-derived counts** — read directly from the shipped widget tree
(`mobile/lib/screens/floor/floor_screen.dart`, `home_shell.dart`,
`room_screen.dart`, `models/agent.dart`). These are exact: how many identity marks the Floor
renders, how many tour stops fire, what order the scroll column stacks in, how many seats the
live Room pins. Each is cited with file and line in `sources.md`.

**DOM-read measurements** — from `prototype/concepts.html` and `prototype/flows.html`,
following the CR120/CR133 house rule: *measurements are read live from the DOM, never
estimated*. Each 390px-wide, 720px-tall frame reproduces a screen using the app's own tokens
and shipped geometry (64px nav, 24px ticker tape, 64px header where one exists, hex avatar
sizes 110/72/56/40/28). A script in the page counts, per frame:

- **Identity marks** — hex avatars representing a *specific named agent*. Anonymous
  desk-colour cluster minis (the "YOUR FIRM" row's three overlapping hexes) deliberately
  don't count: they represent a group, not a person soliciting attention.
- **Tap targets** — everything interactive, including nav cells and chrome.
- **Above the fold** — top edge inside the visible scroll area at scroll position 0. The
  fold is the frame's scroll viewport (632px on tab screens: 720 − 64 nav − 24 tape;
  656px on pushed routes: 720 − 64 header).
- **CTA position** — the primary action's top edge in px from the top of the scroll column,
  also expressed in folds (below 1.0 = visible without scrolling).
- **Column height** — total scrollable px.

The numbers quoted in `01`/`05`/`06` were extracted from the built pages rendered headless
(Chrome, 2026-08-12) and match the stat strips the pages display live.

## Limits — read before quoting any number

1. **Mock-relative, not device-exact.** The HTML frames are a faithful proxy, not the Flutter
   renderer: hex avatars use the CSS flat-top aspect (72px wide = 63px tall, where Flutter's
   `HexAvatar(size: 72)` boxes 72×72), and card heights depend on mock copy length. Numbers
   are therefore only compared *between frames of the same page*, where geometry is
   identical. Baseline-vs-concept deltas are meaningful; "1027px" as an absolute iPhone
   measurement is not.
2. **Cognitive-load proxies, not usability results.** Identity-mark and tap-target counts
   operationalise "12 staff waiting for you"; they are supported by the cited external
   research (progressive disclosure, Hick's law, choice overload — `02_external_patterns.md`)
   but no user was tested on these mockups. The verdict on A vs E vs anything else belongs
   to real testers.
3. **One source of user feedback.** The complaint arrived via Saiful's summary of user
   feedback, 2026-08-12; it is not yet in `bug_reports` or any register (see
   `01_the_complaint_measured.md` §4). n is unknown. CR043 documents why qualitative gripes
   currently have no capture path.
4. **State assumptions.** All frames assume the same mid-journey account: 8 of 12 seats
   filled (analyst desk 4/4, research 2/3, execution 1/1, risk 0/3), one open position, a
   6-day streak. A day-one account (3 unlocked) and a complete firm (12/12) bound the range;
   neither changes the ordering of any comparison here.
5. **CR160 names are used in concept frames** (CIO, Technical Strategist, Macro & Events,
   Flow & Positioning, Risk Officer ×3, Execution Desk). CR160 is *proposed*, not landed —
   the frames treat it as a dependency and say so. The baseline frame uses shipped names.

## Blind-lane note

`docs/Research/UI/Version-0.2/` carries sibling lanes (a `kimi/` folder exists). Per the
benchmark-lane convention (`docs/Research/benchmark/`), this `claude/` lane was researched
and written **without reading any sibling lane**, so the two can be diffed as independent
opinions.
