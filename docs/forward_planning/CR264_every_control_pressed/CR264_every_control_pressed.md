# CR264: Every screen reached, every control pressed

**Status:** in_progress · **Filed:** 2026-10-20 · **Track:** Q (UAT) · **Extends:** CR263, CR163

## What
Saiful asked on 2026-10-20: *"I want every menu item tested, every button pressed."* On the same day he chose "Crawler + coverage gate" and "Press on throwaway UAT users".

About 340 tap handlers (`onTap:`/`onPressed:`) sit across 104 files in `mobile/lib`. Writing one test per button would be brittle. Instead:

1. **Identity (app, QA-safe).**
   1. Every screen and sheet root gets `Semantics(identifier: 'ami.screen.<name>')`.
   2. Every icon-only control gets a semantic label or tooltip, so automation can see it.
   3. A Flutter guard test fails if a screen file lacks a root id, or an `IconButton` lacks a tooltip or label.
2. **Exhaustive crawl (harness).** CR163's crawler gains an exhaustive mode:
   1. The time budget is per screen, not global.
   2. It visits every reachable screen and presses every clickable element.
   3. Each press goes through four oracles: no crash, no new error-sink entry, no overflow or clipping, and something happened (navigation, a sheet, or a state change). A press with no visible effect is a "dead tap" finding.
   4. Results go to a per-control coverage file.
3. **Destructive controls.** Examples: reset portfolio, sign out/delete, submit bug report, send message, buy credits.
   1. They are pressed LAST in a session, on a QA build whose device user is tagged `device_model ami-uat-*` (excluded from real-user counts).
   2. The effect is checked, then the app is reset (pm clear or reinstall).
   3. Bug reports are auto-resolved. Purchases run in the store sandbox only.
   4. A small explicit list covers controls that can never be pressed automatically (e.g. a real App Store purchase sheet). Each entry carries a reason.
4. **Gate.**
   1. A new UAT area `controls` holds device case "every screen reached, every control pressed". Its test is the crawl.
   2. The test fails on any screen not reached, or any discovered control not pressed and not exempted.
   3. It goes through the CR263 ledger, so TestFlight and Play need it green on their platform.
   4. It also runs nightly.

## Phasing
1. A: screen root ids and icon labels, plus the Flutter guard (app code, mechanical).
2. B: crawler exhaustive mode, per-control coverage file, and destructive-last handling (harness).
3. C: the `controls` UAT area, gate wiring, and the first full crawl on iOS and Android. Findings are filed as DEFs.

## Acceptance
1. The Flutter guard is green, and every screen file has a root id.
2. A full crawl reaches every screen and presses every control on iOS (Simulator) and on Android (A17 rig), or each gap is listed with a reason.
3. The `controls` case is in the ledger and the release gate reads it.

## Phase D: control-intent catalogue (Saiful, 2026-10-20: "tapping on each button, also means you need to know what each button is supposed to do")
1. `qa/uat/controls/<screen>.yaml` is one file per surface. Each entry gives the control's label or id, kind, expected effect (`navigate|sheet|dialog|state|external|back|destructive|none`), the target root id, any precondition, and the source line.
2. The intent comes from the handler code and the label/spec. Where the code contradicts the label, the *supposed* effect is recorded and the contradiction is filed as a finding (the DEF457 class).
3. The crawler asserts each press's expected effect. A mismatch is a finding. A control discovered with no catalogue entry is an "unexplained control" finding. So a new button cannot ship without a stated purpose, and UAT-CTRL-001 fails on either kind of finding.

## Status 2026-10-20 (after Phases A, B and D)
1. A (merged): 57 root `ami.screen.*` ids, 25 icon controls labelled, and the Flutter guard. The full suite passes: 1897 tests.
2. D (merged): the catalogue covers 124 surfaces and 495 controls, and has a dangling-target guard. 19 verified findings were filed as DEF470–481.
3. B (merged): the exhaustive crawler with intent checking, `never_press.json`, `spend_limits.json`, and UAT-CTRL-001. The first real crawl reached 13 of 57 screens and pressed 57 of 61 controls it found. It produced 15 findings and one real overflow (DEF482).
4. UAT-CTRL-001 is **parked** (Saiful, 2026-10-20). It runs nightly and reports, but does not block releases until Phase C reaches every screen.

## Phase C (in progress)
1. App: root ids for the Floor tab content, the Portfolio and YOU segment panes, `locked_agent_sheet` and `push_soft_ask_dialog`.
2. Harness:
   1. Route-driving from the catalogue's target graph (a path from a root tab to every surface).
   2. Replay that waits on `ami.screen.*` ids.
   3. State seeding for the tagged device user before the crawl, via the admin/API layer: credits, a holding, Journal entries, a price alert and the watchlist. This makes `when:`-gated surfaces reachable.
3. Done when the crawl reaches every screen, or each unreachable one is listed with a reason. At that point UAT-CTRL-001 is un-parked.
