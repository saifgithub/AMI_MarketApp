# 04 — Six concepts

Each concept hides the twelve-agent complexity behind a simpler surface and keeps depth
reachable. Frames in `prototype/concepts.html` (stat strips are DOM-read; fold = the frame's
visible scroll area). All concepts assume CR133's 4-tab nav and CR160's names except the
baseline, which is the shipped app.

Baseline for comparison (frame `0-baseline`): **13 identity marks (10 above fold) · 23 tap
targets · CTA 1.63 folds down**.

---

## A — Concierge-fronted home ("your chief of staff meets you at the door") — RECOMMENDED

**Landing:** one pink Concierge card: a composed 1–2 line status ("Morning, CEO. NVDA is
+2.1% since your team's BUY call…"), an *Ask AMI* affordance, three action chips (CONVENE
THE ROOM primary · DAILY CHALLENGE · continue lesson). Below: one "YOUR FIRM — 8/12 seats
filled" row, then the unchanged Challenge and League cards.

**Where the 12 go:** behind the firm row → CR159's desk-band screen (flow A2). Tap behaviour
into `agent_action_sheet` unchanged; safety floor stays visibly locked (D-024).

**Disclosure ladder:** Concierge card → firm row → desk bands → agent sheet (1-ON-1 /
BRIEF) → Room transcript. Five levels, all optional.

**Status line cost:** composed client-side from state the app already holds (streak, last
verdict delta, open challenge). Zero new LLM calls; no CR057 exposure.

**Measured:** 1 identity mark · 13 tap targets · CTA **0.43 folds** (screen 1) · column
717px ≈ one screen.

**Strains:** D-003 — the team is no longer *visually* present at rest. Mitigations: the firm
row carries a live seat count ("3 open on the risk desk" is a CEO's sentence); the Concierge
speaks *as staff reporting up*, never as the product talking down. D-018 — the ask
affordance must not re-run the interview; chips accelerate, they don't interrogate. T-TOUR —
the 5-stop tour is rebuilt as 3 stops (card, firm row, chips).

**Revised in review (2026-08-12):** the composed status line becomes an answer-card
carousel, the two heroes become CONVENE (ticker-in + ask AMI) then Daily Challenge, and the
league card is removed (CR109 Amendment A). Frame A′ in `prototype/concepts.html`; evidence
and measurements in `09_floor_header.md`.

---

## B — Briefing-first "Today" home — explored, folded into A

**Landing:** a morning-report stack — dateline, team-authored headline with desk bylines,
positions delta, ANALYZE A TICKER, challenge, firm row.

**Measured:** 1 mark · 10 taps · CTA 0.59 folds.

**Why it dies as a standalone:** the headline card needs a per-user daily digest — a new
backend surface, recurring per-user LLM spend (CR057), and stale-brief risk every
closed-market day. **What survives:** the brief-card grammar — A's status line *is* this
card, composed from existing state for free. B is A's voice with an unnecessary invoice.

---

## C — Task-first home — documented rejection

**Landing:** "What do you want to do?" + three task cards (GET A VERDICT · REVIEW YOUR
PORTFOLIO · LEARN) + small Concierge row.

**Measured:** 1 mark · 10 taps · CTA 0.16 folds — the best raw numbers of the six.

**Why it dies anyway:** the user is CEO of nothing visible — D-003 takes its hardest hit,
with no mitigating seat count or reporting voice. Two of three cards restate the PORTFOLIO
and LESSONS tabs — nav duplication, the exact non-problem CR004's plan_b called out. Kept as
the boundary marker: this is how far hiding can go before it stops being *this product*.

---

## D — Collapsed-firm Floor — documented rejection

**Landing:** the Floor keeps its shape; the 12-hex field folds into YOU → CIO → one "YOUR
TEAM 8/12" band that expands to CR159's bands in place; challenge, league, CTA as shipped.

**Measured:** 1 mark · 11 taps · CTA 0.83 folds.

**Why it dies:** (1) it re-proposes the collapsible-section pattern CR120 measured and
rejected — different content, same mechanics, and the register exists precisely to stop
quiet re-runs; the distinction (identity roster vs data list) is arguable but the burden of
proof sits on the re-proposer, and nothing here discharges it. (2) More fundamentally: the
landing surface still *answers* "who works here?" while the user is *asking* "what should I
do?" — the roster stays the organising principle, just folded. The complaint isn't that the
staff are large; it's that they're the greeting.

---

## E — Single-narrative Room, live phase — RECOMMENDED

**The complaint's second surface.** Default the *live* Room to a four-stage narrative —
ANALYST DESK → RESEARCH DEBATE → RISK REVIEW → CIO VERDICT — one hex-segment progress bar,
one streamed line per stage ("FUND — margins expanding, guidance intact"), a
BRIEFING | WATCH THE FLOOR toggle. WATCH THE FLOOR restores the shipped 12-seat roster;
the choice persists as a third value of CR106's `RoomViewMode` (same provider, same
one-writer rule). The settled Verdict Board is untouched — this CR ends where CR106 begins.

**Where the 12 go:** stage rows carry desk counts (2/4 reported); tapping a stage opens the
desk's members with their live states (flow E2); the toggle keeps the full floor one tap
away, forever, for the users who love it.

**Data cost:** zero — the four stages are a presentation of the existing `kAgentPhase`
grouping; the four seat states map 1:1 onto stage-row states, honesty rules
(DEF059/DEF174) included.

**Measured:** live-phase identity marks **12 → 2**; tap targets 6.

**Strains:** nearly none — it is CR106's own logic extended left in time; the CR106 CR
itself measured the prose problem this narrative pre-empts. Orthogonal to the home choice;
pairs with any of A–D.

---

## F — Global depth dial (Simple / Full) — documented rejection

**The idea:** a novice/pro switch; Simple hides the roster app-wide, Full is today's app.

**Why it dies:** every surface ships twice — built, tested, translated (EN/AR/MS), forever.
The dial needs a home the app doesn't have (no app bar — CR133 §1; a Settings burial means
the overwhelmed user, the one it exists for, never finds it). And the default is a fork:
default Simple and Simple *is* the app (that's concept A without the courage); default Full
and nothing changed. A mode switch here is the design refusing to decide.

---

## Constraint-strain matrix

✓ = compliant · △ = strained, mitigated · ✗ = violated

| | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| D-003/013 CEO metaphor | △ (seat count + reporting voice) | △ (bylines) | ✗ | ✓ | ✓ | △ (Simple side) |
| D-012 twelve agents | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| D-014/015 Concierge role | ✓ (is the lever) | ✓ | ✓ | ✓ | n/a | ✓ |
| D-018 conversational onboarding | △ (must not re-read as interview) | ✓ | ✓ | ✓ | n/a | ✓ |
| D-024 visible safety floor | ✓ (in agent sheet, unchanged) | ✓ | ✓ | ✓ | ✓ | △ (Simple buries the path to it) |
| CR113/117 geometry | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Rejected register | ✓ | ✓ | ✓ | ✗ (CR120 pattern) | ✓ | △ (mode ≈ dual UI) |
| New backend / LLM spend | none | ✗ daily digest | none | none | none | none |
| CR133/159/160 fit | composes | composes | competes with tabs | composes | composes | orthogonal |

Rejected-register cross-check: no concept proposes screeners, copy-trading, leaderboards, a
gear-in-app-bar, or a profile tab. D's collision with CR120 is stated in its own section, as
the register requires.
