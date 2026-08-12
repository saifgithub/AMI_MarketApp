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
| `sources.md` | Primary/secondary, code lines, fetch-failures recorded |
| `VERIFICATION.md` | Every number traced: PROVEN vs ASSERTED, corrections during audit |
| `prototype/` | `build.py` + two self-contained templates → `concepts.html`, `flows.html` |

## Status

Research only — no code changed, no CR minted. A build starts at `05_recommendations.md`'s
sequencing after Saiful answers `07_open_decisions.md` #2 and #4.
