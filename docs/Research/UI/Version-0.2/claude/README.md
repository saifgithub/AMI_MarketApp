# UI v0.2 research — hiding the twelve

**Claude lane** · 2026-08-12 · written blind to sibling lanes (see `00_method_and_limits.md`).

## The short version

Users read the Floor as *"walking into a meeting with 12 staff waiting for you."* They're
describing two shipped surfaces: the landing tab (13 identity hexes, 23 tap targets, the
CONVENE CTA 1.63 folds down) and the live Room (all 12 seats pinned from the first frame).
The settled Room already solved its half of this — CR106 defaults to the Verdict Board with
the prose one toggle away. This research applies that same rule — **verdict first, people on
request** — to the two surfaces that never got it, and recommends **two** of six explored
concepts:

- **A — Concierge-fronted home.** One pink card greets the CEO with a composed status and
  three action chips; the twelve live behind a "YOUR FIRM · 8/12 seats" row that opens
  CR159's desk bands. Landing surface: 13 marks → 1, CTA on screen one. Zero new LLM cost.
  The lever is already sanctioned — D-014/D-015 make the Concierge the product's single face.
- **E — Single-narrative Room.** The live phase defaults to four desk stages with one
  streamed line each; WATCH THE FLOOR restores the full 12-seat view, persisted as a third
  value of CR106's own `RoomViewMode`. Live marks: 12 → 2. The Verdict Board is untouched.

Rejected with reasons: briefing-first home (B — recurring digest cost buys nothing A's card
doesn't), task-first home (C — best numbers, breaks the CEO metaphor), collapsed-firm Floor
(D — re-runs CR120's measured rejection; still greets with the org chart), depth dial
(F — two apps forever to avoid picking a default). CR004's "navigation is not the problem"
is conceded and answered: the complaint is at-rest cognitive load, which tap counts can't
see (`06_answering_cr004.md`).

**Look at the mockups first:** `prototype/concepts.html` (baseline + all six, with DOM-read
stat strips) and `prototype/flows.html` (A and E walked three frames deep). Regenerate with
`python3 prototype/build.py`.

**Persona addendum (post-review):** the original pass skipped personas; `08_personas.md`
fixes that with four personas built from the specs and real alpha behaviour. The data is
blunt — of 172 real users, 73% take no core action, ≤6% ever touch an individual agent,
Brief Your Agent sits at 0% — so the landing surface was optimised for the smallest
measured persona. A+E survives the re-run and gains a step 0: post-DEF060-fix, only 21% of
fresh installs finish the onboarding interview, so instrument where the interview leaks
before (or with) any home CR — the bigger funnel loss is upstream of the Floor.
(Renamed in review: P1 **The Curious User**, P4 **The Learner**.)

**Header revision (Saiful's review, 2026-08-12):** concept A's status line becomes an
answer-card **carousel** (portfolio value · the team's calls · sector watch), the heroes
become CONVENE (ticker-in + ask AMI) then the Daily Challenge, and the league card is gone —
CR109's game already deletes it (Amendment A). The carousel evidence cuts in its favour once
it obeys five rules (no auto-rotate, priority order, peek, ≤5 cards, dots) — measured as
frame A′: still 1 identity mark, CTA at 0.46 folds, column shorter than A. See
`09_floor_header.md`.

## Reading order

| File | What it holds |
|---|---|
| `00_method_and_limits.md` | What was measured vs asserted; the fold; blind-lane note |
| `01_the_complaint_measured.md` | The shipped Floor + live Room, in numbers |
| `02_external_patterns.md` | Progressive disclosure, Hick/choice-overload, 2025-26 agentic UX, Cleo/Fin/Robinhood — verified quotes |
| `03_house_levers.md` | CR106, the Concierge sanction, CR159/160/133, `kAgentPhase` — everything reused |
| `04_concepts.md` | All six concepts + constraint-strain matrix |
| `05_recommendations.md` | A + E: argument, costs, CR sequencing (CR160 → CR159 re-scoped → home → room) |
| `06_answering_cr004.md` | The tap-count concession and what it can't measure |
| `07_open_decisions.md` | Five calls for Saiful (tab name, card voice, E's default, CR159 re-scope, status-line source) |
| `08_personas.md` | Addendum after review: four personas from specs + real alpha behaviour (172 users; 73% no core action, depth features ≤6%, Brief 0%, interview completion 21% post-fix); recommendation survives, funnel instrumentation promoted to step 0 |
| `09_floor_header.md` | Second review addendum: answer-card carousel header (evidence + five rules), CONVENE + challenge as the two heroes, league removed per CR109, frame A′ measured |
| `sources.md` | Primary/secondary, code lines, fetch-failures recorded |
| `VERIFICATION.md` | Every number traced: PROVEN vs ASSERTED, corrections during audit |
| `prototype/` | `build.py` + two self-contained templates → `concepts.html`, `flows.html` |

## Status

Research only — no code changed, no CR minted. A build starts at `05_recommendations.md`'s
sequencing after Saiful answers `07_open_decisions.md` #2 and #4 (#5 was settled
client-composed by the 09 review; #1 defaults to FLOOR if silent).
