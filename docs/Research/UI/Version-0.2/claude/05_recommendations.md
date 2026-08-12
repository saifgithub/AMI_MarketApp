# 05 — Recommendation: A + E

Two picks, per the brief's ceiling. They are one decision applied at the two moments users
complained about: **verdict first, people on request** — at rest (A) and while the team
works (E). The settled Room already lives by this rule (CR106); A and E finish the thought.

## The argument in one table

| Criterion | A — Concierge home | E — narrative Room |
|---|---|---|
| Lever legitimacy | D-014/D-015 *define* the Concierge as the single product-facing face | CR106 is shipped precedent on the same screen |
| Surface at rest / live | 13 marks + 23 taps → **1 mark + 13 taps** | **12 pinned seats → 1 tracker + 4 stages** |
| CTA | 1.63 folds down → **0.43 folds, screen 1** | n/a (verdict is the destination) |
| New backend / LLM cost | **zero** — status line composed from client state | **zero** — presents existing `kAgentPhase` |
| The 12 agents (D-012) | intact, one tap away, with seat counts | intact, one toggle away, persisted choice |
| Safety floor (D-024) | agent sheet unchanged, locked block visible | untouched |
| CR133 | slot-0 content changes, tab bar doesn't | no contact |
| CR159 | becomes the depth layer — *promoted*, not superseded | View B pipeline hook stays free |
| CR160 | consumes the names ("your CIO") | stage labels are the new desk names |
| Main build cost | rewrite of `floor_screen.dart` body (~541 lines); chat widgets, action sheet, earn-path sheet all reused; tour rebuilt 5→3 stops | extend `RoomViewMode` enum + provider; new stage-row widget; parity test vs comb (T-TWICE) |
| Main risk | D-003: team not visually present at rest — mitigated by seat-count row + reporting voice; test with real users | users who liked watching 12 seats — kept, behind WATCH THE FLOOR, persisted |

## Why not the others as the second pick

- **B** is A's voice plus a recurring invoice (per-user daily digest → backend + CR057 LLM
  spend + stale-brief risk). Its card grammar is already inside A.
- **C** posts the best raw numbers (CTA 0.16 folds) and breaks the product doing it — a CEO
  app whose firm is invisible at rest fails D-003 without mitigation, and its task cards
  duplicate tabs (CR004's actual point).
- **D** improves the numbers least (CTA 0.83 folds), lands the user on the org chart anyway,
  and re-runs CR120's measured rejection of collapsible sections.
- **F** doubles every build/test/translation surface to avoid choosing a default. Choosing
  the default *is* the job; A is that choice made.

## Sequencing (when Saiful greenlights a build)

1. **CR160 first** — renames; same registry file as everything downstream (T-SEQUENCE).
2. **CR159, re-scoped** — desk bands built as the "Your Firm" screen (pushed route), not the
   Floor body. Confirms open decision #4 (`07_open_decisions.md`). Traps T-TOUR / T-SLICE /
   T-TWICE inherited as written.
3. **Home CR (concept A)** — new Floor body: Concierge card + firm row + existing cards.
   Tour rebuilt (3 stops). `_agentKey0/_agentKey4` anchors die with the Wrap (T-TOUR).
4. **Room CR (concept E)** — third `RoomViewMode` value + stage-row widget + parity test.
   Independent of 3; can ship first if A stalls.

Each step is its own CR with its own acceptance; this research is evidence, not a spec.

## What would change this recommendation

- Real-user testing showing the seat-count row fails to carry the CEO feeling (D-003) →
  fall back to D's YOU/CIO topper *on top of* A's card, accepting the extra mark.
- CR160 not landing → A and E still work with shipped names, but "your CIO" becomes "your
  Portfolio Manager" and the stage labels lose their desk framing; the frames as mocked
  assume the rename.
- A decision to keep the honeycomb as brand identity at all costs → E alone still halves
  the complaint's surface area; ship it regardless of the home decision.
