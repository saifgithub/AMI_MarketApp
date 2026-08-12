# VERIFICATION — claim audit

Every load-bearing quantitative claim, traced. PROVEN = read from code, register, or the
rendered DOM this session. ASSERTED = reasoned but not independently executed. Anything
found neither is listed under "corrections".

## Code-derived claims

| Claim | Where used | Status |
|---|---|---|
| Floor renders 13 identity marks at rest (Concierge + 12) | 01 §1, 04 | **PROVEN** — `kAllAgents` (13 entries, `agent.dart:45-159`); all rendered `floor_screen.dart:383-429` |
| Wrap lays out 3 tiles/row → 4 rows at 390pt | 01 §1 | **PROVEN** — tile 88pt + 16pt spacing in 358pt content (`_AgentTile:522`, padding `:357`); confirmed visually in baseline frame render |
| Tour = 5 stops, 3 introduce agents | 01 §1 | **PROVEN** — 5 GlobalKeys `floor_screen.dart:49-53` (concierge, agent0, agent4, challenge, convene) |
| Live Room pins 12 seats from first frame | 01 §2, 04 E | **PROVEN** — `room_screen.dart:399` `kAllAgents.sublist(0, 12)`; CR112 comment `:382-388` |
| Four live seat states | 03 §3.4 | **PROVEN** — `room_screen.dart:408-421` |
| CR106 board default persisted, single writer | 03 §3.1 | **PROVEN** — `room_view_mode_provider.dart:20-57` |
| Six phases exist client-side (`kAgentPhase`) | 03 §3.4, 04 E | **PROVEN** — `agent.dart:173-188` |
| Baseline frame copy is the shipped copy | prototypes | **PROVEN** — `app_en.arb` `floor*` keys, quoted verbatim |
| `floor_screen.dart` is 541 lines | 05 table | **PROVEN** — file read this session ends at line 565 total incl. `_AgentTile`; the 541 figure is CR159's count of the file at filing. Kept with CR159 attribution. |

## DOM-read claims (headless Chrome 2026-08-12; regenerable via `prototype/build.py` + opening the pages)

| Claim | Where used | Status |
|---|---|---|
| Baseline: 13 marks (10 above fold) · 23 taps (16 above) · CTA 1027px = 1.63 folds · column 1178px | 01, 04, 06 | **PROVEN** — frame `0-baseline` stat strip |
| A: 1 mark · 13 taps · CTA 269px = 0.43 folds · column 717px | 04, 05 | **PROVEN** — frame `A-concierge` |
| B: 1 · 10 · CTA 0.59 folds | 04 | **PROVEN** — frame `B-briefing` |
| C: 1 · 10 · CTA 0.16 folds | 04, 05 | **PROVEN** — frame `C-tasks` |
| D: 1 · 11 · CTA 0.83 folds | 04, 05 | **PROVEN** — frame `D-collapsed` |
| E: live marks 12 → 2 · 6 taps | 04, 05 | **PROVEN** — frame `E-room` vs shipped roster count |
| Flows: A2 9 marks · A3 2 · E2 4 · E3 12 | flows page | **PROVEN** — stat strips. Superseded for A3 by the 09 flows rewrite (below): the greeting bubble was cut when the omnibox carry-over replaced it, so A3 now reads 1 mark |
| Built pages contain no external references | 00 method | **PROVEN** — `grep http` over both built files: only `data:font` URIs |

## External-quote claims

All 13 cited sources fetched live this session by the research pass; each quote in
`02_external_patterns.md` was extracted from fetched page text. **PROVEN at fetch-level**,
with one honesty note: extraction ran through an automated fetch pipeline — before quoting
any line in *user-facing product copy* (not this research), re-check against the live page.
Perplexity/Inc/Columbia pages: **NOT VERIFIED**, not cited (recorded in `sources.md`).

## Alpha-data claims (added with 08; queried live 2026-08-12)

| Claim | Status |
|---|---|
| 172 real users after the standing exclusion filter | **PROVEN** — query run this session on melehost |
| 125/172 (73%) no core action; 32 convened; 9 convened 3+; 11 used 1-on-1; 5 reached a trading agent; 9 messaged Concierge; 30 did lessons; 8 traded; 4 did challenges | **PROVEN** — same aggregate query |
| 0 Brief Your Agent edits | **PROVEN** — `sum(overlay_edit_counts.count)` = 0 across real users |
| 28 mandates persisted; 84/172 accounts <14 days old; range 2026-05-13→08-12 | **PROVEN** — second query |
| Post-DEF060-fix cohort: 18/84 mandates (21%), 7/84 convened (8%) in last 14 days | **PROVEN** — third query. DEF060 confirmed **fixed** (AT:R59) in `docs/defect/_registry/DEF060.row.md` before this was framed — an earlier draft of 08 wrongly treated it as open; corrected same session |
| The four personas (P1–P4) | **ASSERTED** — evidence-weighted synthesis of specs + segments; not interviewed humans (08 §8.5) |
| "Counts include founder test devices" | **PROVEN in kind** (exclusion memo documents iPhone18,1/emulator rows) — exact split not derived |

## Asserted (not independently executed)

- "Rewrite of `floor_screen.dart` body" as A's main cost, and "extend enum + provider +
  stage widget" as E's (05) — engineering judgement from reading the files; no build was
  attempted. **ASSERTED.**
- Zero-LLM-cost status line (A) — composition from streak/verdict/challenge state the
  client already holds; claim is about *possibility*, not an implementation. **ASSERTED.**
- "No prior written record of the complaint" (01 §4) — negative claim from a docs-tree
  grep for overwhelm-class terms; a differently-worded record could exist. **ASSERTED
  (bounded).**
- The choice-overload analogy (12 seats ≈ the jam study's extensive array) — an analogy,
  not a measurement on this app. Labelled as such where used. **ASSERTED.**

## Added with 09 (Floor-header revision, 2026-08-12 review session)

| Claim | Where used | Status |
|---|---|---|
| A′: 1 mark · 12 taps · CTA 294px = 0.47 folds · column 632px (= exactly one fold) | 09 §9.3 | **PROVEN** — frame `A-rev-carousel` stat strip, headless Chrome this session, re-read after the omnibox merge (review round 2 replaced the two inputs with one; an earlier draft measured 13 taps · 0.46 · 655px with separate ticker + ask fields). Honesty note stated in 09: the counter checks vertical position only, so the 2 off-canvas carousel cards count among the 12 taps; visually at rest = 10 targets, 1 card |
| Runyon: 1.07% of 3.76M interacted; 89.1% of clicks on slide 1; slide-1 share 55–89% across 5 sites | 09 §9.2 | **PROVEN at fetch-level** — primary page fetched this session (#17) |
| NN/g / Baymard / Friedman carousel quotes | 09 §9.2 | **PROVEN at fetch-level** — #14/#15/#16 fetched this session; same re-check caveat as the other external quotes |
| CR109 Amendment A removes the league (incl. the Floor's league card); slices 1–3 dark behind `kGamesEnabled`; no D-060 amendment exists | 09 §9.1 | **PROVEN** — spec sweep this session read `CR109.md` (Amendments A/F, removal scope), `games_gate.dart:33-36`, `decision_log.md` D-060; league removal is Saiful's recorded instruction, not this lane's proposal |
| No league-usage number was ever measured (`league_members` never queried in research) | 09 §9.1 | **ASSERTED (bounded)** — negative claim from a corpus search; a measurement outside `docs/` could exist |
| "$100,000 ready to deploy" day-0 card copy | 09 §9.3, frame A′ note | **ASSERTED** — illustrative; the actual sim starting stake must be read from code before any build copies it |
| Flows rewrite: A1 (A′) 1 mark · 12 taps · CTA 0.47 folds · 632px — identical to the concepts-board A′ strip; A3 1 mark · 3 taps; A4 0 marks · 6 taps; A5 0 marks · 4 taps | flows page, 09 §9.6 | **PROVEN** — stat strips re-read after the A1/A3/A4/A5 rewrite, headless Chrome this session |
| CR133 phase 1 = four tabs with the Journal moved inside YOU (a JOURNAL segment), phase 2 gives GAME the old Journal slot and its pointers | 09 §9.6, flows A4 note | **PROVEN** — `CR133.md` read this session (tab tables, "The Journal is not missing — it moved inside YOU", inheritance table) |
| A4's calls list is backed by existing `room_runs` rows | 09 §9.6 | **ASSERTED** — run history is stored server-side and the Journal reads it; the exact list query for "delta since verdict" needs a price lookup at read time, not verified as an existing endpoint |
| "Restart onboarding moves to YOU" | 09 §9.6 | **ASSERTED** — CR133 moves Settings under YOU; the restart link's exact new home is a build-time confirmation |

## Corrections made during audit

- Concept E frames initially marked desk-stage rows as non-interactive; they are tap
  targets ("tap a desk"). Fixed before measurement — E's taps read 6, not 2. (This is why
  honesty rules want the count read from the artifact, not typed.)
- `build.py` REPO path was one level shallow on first run; failed loudly (degrade-loudly
  compliant) and was fixed before any output existed.
