# Defect register — AMI Trade

The processed record of every **defect** — a thing that is broken or wrong versus the
spec. Two sources feed it:

- **User-reported** — filed in-app (`POST /v1/feedback/bug` → `bug_reports` table on
  melehost), triaged by [`/fix-bugs`](../../.claude/commands/fix-bugs.md). The DB is the
  intake queue; **this file is the processed record.** When a report is worked, it gets a
  `DEF###` here.
- **Prompt-reported** — a defect Saiful (or Claude) spots in a session with no in-app
  report behind it. No `bug_reports` row; still gets a `DEF###` here when processed.

Sibling register for *planned* change (new work, not fixes): [`../forward_planning/cr_list.md`](../forward_planning/cr_list.md).
Governance rationale: decision **D-058** in [`../initial_specs/11_decisions/decision_log.md`](../initial_specs/11_decisions/decision_log.md).

## How to add a defect

1. Assign the next free `DEF###` (zero-padded, sequential, never reused).
2. Add a row to the table. **Source** is `bug:<short-id>` (first 8 chars of the
   `bug_reports.id` UUID) for user-reported, or `prompt` for prompt-reported.
3. Fix it on a branch. The fix commit carries the tag `fix(bug:<short-id>): <summary> (AT:R<N> DEF###)`
   for user-reported, or `fix(<scope>): <summary> (AT:R<N> DEF###)` for prompt-reported.
4. Record the fix commit hash in the **Fix** column and set **Status**.
5. For a defect that needs its own root-cause / design write-up, create
   `docs/defect/DEF###_<snake_case_topic>/` and link it from the row.

**Status** mirrors the operational lifecycle: `resolved` · `wont_fix` · `closed` (fixed
out-of-band) · `open` (in the DB, not yet worked — not usually listed here until processed).

## Register

DEF001–DEF036 are the backfill of every processed in-app report as of 2026-07-05
(the `bug_reports` table had 32 `resolved`, 3 `wont_fix`, 1 `closed`, 0 `open`).

| DEF | Date | Source | Category | Title | Status | Fix | Session |
|---|---|---|---|---|---|---|---|
| DEF001 | 2026-05-14 | bug:2df75204 | ui_glitch | Selected option text unreadable (bright-on-bright) | resolved | — | AT:R33 |
| DEF002 | 2026-05-14 | bug:4e459d38 | other | AMI does not respond | resolved | — | AT:R33 |
| DEF003 | 2026-05-14 | bug:ee8cd51f | other | Watchlist add not reflected in ticker tape | resolved | — | AT:R33 |
| DEF004 | 2026-05-14 | bug:b5a7bfb4 | other | Initiating a trade should auto-add the stock to ticker tape | resolved | — | AT:R33 |
| DEF005 | 2026-05-14 | bug:73d40725 | ui_glitch | Room convene disrupted by connection break | resolved | — | AT:R33 |
| DEF006 | 2026-05-14 | bug:8b3849aa | ui_glitch | System/light/dark theme toggle has no visible effect | resolved | — | AT:R33 |
| DEF007 | 2026-05-14 | bug:1dea9c18 | ui_glitch | Deleting a journal entry is too easy | resolved | — | AT:R33 |
| DEF008 | 2026-05-14 | bug:1af38e7a | ui_glitch | Concierge could not open lesson | resolved | — | AT:R33 |
| DEF009 | 2026-05-14 | bug:b6e8c505 | ui_glitch | Convene failed | resolved | — | AT:R33 |
| DEF010 | 2026-05-14 | bug:278cbad8 | other | Stale room_runs never marked aborted | resolved | 49e88b0 | AT:R34 |
| DEF011 | 2026-05-14 | bug:eeeb866f | other | Room run must survive api-alpha container restart | closed | 3f4022a | AT:R34 |
| DEF012 | 2026-05-14 | bug:3ef7ca04 | ui_glitch | "Entry removed" snackbar persists until app backgrounded | resolved | f0063d6 | AT:R34 |
| DEF013 | 2026-05-14 | bug:f34cf7af | other | Journal Trash view to restore soft-deleted entries past UNDO | resolved | — | AT:R34 |
| DEF014 | 2026-05-14 | bug:2795baf2 | other | Agent response format (render as Markdown) | resolved | b389b2f | AT:R34 |
| DEF015 | 2026-05-14 | bug:90441819 | ui_glitch | Compliance list label unexplained | resolved | a9b3540 | AT:R34 |
| DEF016 | 2026-05-14 | bug:85469d8e | ui_glitch | Fund agent report on AAPL missing live fundamentals | resolved | 4c59f61 | AT:R34 |
| DEF017 | 2026-05-14 | bug:a606436f | ui_glitch | Fund agent report on AAPL (duplicate of DEF016) | wont_fix | — | AT:R34 |
| DEF018 | 2026-05-14 | bug:82cb07c6 | other | app_version constant drifts from pubspec.yaml | resolved | 918111c | AT:R34 |
| DEF019 | 2026-05-15 | bug:698a0fe6 | other | Convene report not stored | resolved | — | AT:R34 |
| DEF020 | 2026-05-15 | bug:f7c4d7e0 | ui_glitch | Screenshot attachment | resolved | — | AT:R34 |
| DEF021 | 2026-05-16 | bug:0bd88533 | ui_glitch | Disconnected room conversations not accessible from journal | resolved | 264fcf5 | AT:R35 |
| DEF022 | 2026-05-17 | bug:6f9b5ebd | ui_glitch | "Buy" journal record incorrectly formatted | resolved | c9f682f | AT:R36 |
| DEF023 | 2026-05-17 | bug:ce7146c8 | ui_glitch | Two "buy" orders placed from one verdict | resolved | 59acfe9 | AT:R36 |
| DEF024 | 2026-05-17 | bug:9b3a6c2f | ui_glitch | Successful trade gives no confirmation → duplicate trades | resolved | 1e69052 | AT:R36 |
| DEF025 | 2026-05-17 | bug:d5717660 | ui_glitch | Suggest convening the Room before an un-advised trade | resolved | a8ffafb | AT:R36 |
| DEF026 | 2026-05-17 | bug:1e645bca | feature_request | Journal filter for "trade" and "room" next to "all" | resolved | — | AT:R36 |
| DEF027 | 2026-05-17 | bug:7a9dd6b6 | feature_request | Journal search facility | wont_fix | — | AT:R36 |
| DEF028 | 2026-05-17 | bug:6fd4144d | ui_glitch | No way to exit bug-report screen without submitting | resolved | af01328 | AT:R36 |
| DEF029 | 2026-05-17 | bug:e2857081 | feature_request | Lessons layout — blank space, overlapping buttons | resolved | a51a75b | AT:R36 |
| DEF030 | 2026-05-17 | bug:cb81a6d8 | ui_glitch | Lesson from agent has no bottom menu / no exit | resolved | 75ba23a | AT:R36 |
| DEF031 | 2026-05-17 | bug:11fde6f6 | ui_glitch | Floor hex design should match lessons hex | wont_fix | 9a1c93d (reverted) | AT:R36 |
| DEF032 | 2026-05-19 | bug:325e0747 | ui_glitch | Verify Room runs asynchronously | resolved | — | AT:R37 |
| DEF033 | 2026-05-19 | bug:a84361f6 | ui_glitch | Apple ID registration glitching (503) | resolved | cd4a3f2 | AT:R37 |
| DEF034 | 2026-05-20 | bug:9b9d4790 | other | Lesson claims Room Q&A feature — does it exist? | resolved | — | AT:R37 |
| DEF035 | 2026-05-20 | bug:a19871c3 | ui_glitch | Bug-report "X" hard to trigger — need a better cancel | resolved | — | AT:R37 |
| DEF036 | 2026-05-20 | bug:e2a30a64 | ui_glitch | Apple sign-in failed | resolved | — | AT:R37 |
| DEF037 | 2026-07-06 | prompt | other | TestFlight upload broken — `xcrun altool --upload-app` error 19 on Xcode 26.5 | resolved | c079359 | AT:R49 |
| DEF038 | 2026-07-07 | prompt | config | GOOGLE_AUDIENCES never forwarded to api-alpha container (compose `environment:` omits it) — Google Sign-In verifies against empty audience list on Alpha; masked (no real Google traffic yet). Also: bare-CSV values crash pydantic-settings list fields | resolved | — | AT:R52 |
| DEF039 | 2026-07-09 | prompt | other | `reputation_events` has no DB partial-unique index on its `(user_id, event_type, ref_id)` dedup anchor — dedup is app-code-only, so concurrent same-ref awards can double-insert (defense-in-depth gap on a monetized currency). Needs migration 0015 + promote. (CR004 audit round-1 finding F2) | open | — | AT:R53 |
| DEF040 | 2026-07-09 | prompt | other | Account merge mid-week re-keys `reputation_events` and sums lifetime `reputation` but does not recompute the adopter's current-week `league_members.points` — a mid-week claim can undercount current-week league standing (lifetime reputation stays correct). (CR004 audit round-1 finding F5) | open | — | AT:R53 |
| DEF041 | 2026-07-09 | prompt | ui_glitch | Brief "Refine" button called `.reject()` — it discarded the proposal + diff instead of refining. Now Refine keeps the diff visible, prefills the composer with the proposal text, and focuses the input (no server-side reject). (Plan A #1, fixed under CR009 B4) | resolved | fb2e6e4 | AT:R53 |
| DEF042 | 2026-07-09 | prompt | security | `GET /v1/daily_challenge/today` returns the challenge `answer` (correct option index) pre-attempt — an API-direct user can read it, farm `challenge_correct`, and guarantee the streak → monetized credit milestones. Same monetized-currency exploit class as DEF-F1. Fix: drop `answer` from `/today`, return `correct_option` only in the attempt response; mobile highlights the correct option from the attempt result (already carries `correctOption`), not `ch.answer`. Needs backend + mobile change + promote. (CR010 audit finding O1) | open | — | AT:R53 |
| DEF043 | 2026-07-10 | bug:ea97081b | ui_glitch | HexBottomNav (CR016, shipped in `0.1.0+36`) looks wrong: (1) the active indicator is a cut-corner **octagon** (`FlatTopHexagonClipper`), not a hexagon, despite the "hex" brand mandate; (2) `PORTFOLIO` **wraps to two lines** because the nav `Text` overrode only `fontSize` and kept `labelMono`'s `letterSpacing: 1.8`, overflowing the ~66pt cell. Saiful: "the hex bottom nav looks ugly… actually use hex." Fix: rebuild the active indicator as a true flat-top **regular hexagon** (honeycomb-avatar geometry) with gradient fill + blue border + glow; make labels single-line (tight tracking + `FittedBox` scale-down). Mobile-only, no backend, no new dep. | resolved | — | AT:R53 |

*Backfill note: sessions before AT:R38 are approximate (dated by report, mapped to the
session that shipped the fix where a `fix(bug:…)` commit exists). Fix hashes are filled
where a `fix(bug:<short-id>)` commit was found; `—` means resolved out-of-band or on `main`
without a tagged fix commit. This is the historical seed — new entries carry exact data.*
