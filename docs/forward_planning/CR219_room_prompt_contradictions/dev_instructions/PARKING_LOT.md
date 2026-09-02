# Parking lot — ruled OUT of CR219 (do not build)

Rows Saiful explicitly parked (2026-09-02 for R53/R57–R60; earlier for R55). A worker
session finding these in the register builds **nothing** for them; they wait for their
own future CR. Kept here so the ideas don't die with the register's status column.
Source detail for all of them: `../fable/05_further_improvements.md`.

| Row | Idea (one line) | Why parked | Wake-up condition |
|---|---|---|---|
| R53 | Permanent `DATA GAPS:` telemetry tail on analyst turns — every Alpha convene reports what data it lacked, giving a standing demand signal like the arms produced | Tier-3 catch-all; prompt+parser change with unmeasured token cost | After AC4's post-fix measurement, if data-gap demand needs continuous tracking |
| R55 | Verdict-outcome ledger — log every verdict vs subsequent price path; internal calibration floor. **Internal-only; no user-facing calibration stats before v1.0** | Ruled its own future CR at the combine step (the one item explicitly ruled out); ID minted by the Architect then | When CR219 closes and the combine step runs |
| R57 | Stance-envelope grammar tension — forcing envelope emission via grammar would destroy its value as a compliance *measurement* channel | Fable's own recommendation: leave untouched until the R50 scoreboard exists and shows parse-rate data | R50 shipped + envelope parse rate known |
| R58 | Debate-order randomization (Bull always speaks first; anchoring risk) | Cheap experiment but needs the WP07 harness to measure; not a contradiction fix | Harness idle time after CR219 experiments |
| R59 | Full numbers-audit: every number the user reads is computed or checked in code | The RO-precompute half already ships via R20 (WP03); the general audit is a program, not a CR item | If a user-visible arithmetic error surfaces post-CR219 (that would also be a DEF) |
| R60 | "What changed since your last convene" delta line on re-runs | Pairs with R52 (kill-criterion); needs convene-history plumbing | If R52's kill-criterion field proves useful on Alpha |

House rule reminder: when one of these wakes up, the Architect mints the CR ID —
nothing here pre-claims a number.
