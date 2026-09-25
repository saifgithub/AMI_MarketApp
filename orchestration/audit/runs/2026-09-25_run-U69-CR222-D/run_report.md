# Run report — CR222-D round 1 (U69, 2026-09-25)

**Item:** CR222 slice D — behaviour diagnostics, Portfolio Health §F3. **Tier B as
submitted; promoted to Tier A rounds per BINDINGS §8** (one MAJOR).
**SHA audited:** `e0a9cc57dd04c46e4a71aae1db1dd13680d78316` (branch
`worktree-agent-ac5f62fc688f4b8ff`, off `main`; detached worktree
`.claude/worktrees/audit-CR222/`, shared with the CR222-B audit — same tree).
**Verdict:** AWAITING_FIXES (round 1) — 1 MAJOR, 2 MINOR, 1 out-of-scope note.

## Commands run

- Targeted suites (identical worktree/commands as CR222-B's report): **128 passed,
  1 skipped** (the four CR222 files + parity + ratchet + blocking-IO) and **133 passed**
  (CR136/CR131 renderer/validator/rule-engine/day-trader). Both match the submission.
- Hand reproduction of the probe fixture's arithmetic: turnover 83.33 annualised
  ((12,000+0)/2 / 10,000 × 100 = 60.0; 60.0 × 365.25/263 = 83.33), median hold 3.0 over
  12 uniform 3-day round trips, 8/4 win/loss split — all match the rendered block.
- The divergence evidence for MAJOR-1: on the pinned test's own fixture
  (`test_cr222_behaviour_diagnostics.py:392`), dollar-PLR = 200/300 = 0.667 (what the code
  and the test assert); Odean-1998 count-PLR on the same fixture = 1/2 = 0.5. A
  constructed divergent case ($900 realised gain + nine $100 paper gains): dollar-PGR 0.50
  vs count-PGR 0.10.
- Fixed-prose token sweep over every sentence `_f3_behaviour` can emit: all numeric tokens
  registered post-fix (see CR222-B's report for the mechanism verification).
- Source for the Odean definition: [Odean 1998, Haas
  PDF](https://faculty.haas.berkeley.edu/odean/papers%20current%20versions/areinvestorsreluctant.pdf)
  ("PGR is the number of realized gains / (realized gains + paper gains)").

## Code read (file:line)

`behaviour_diagnostics.py` whole file (743 lines): `too_early` gate :687-708 before any
measure; dollar accumulation :491-515; ratio :517-524; counts tracked but unused in the
ratio; `_NEW_BASELINES` count-based figures :147-155; `_disposition_ratio`'s
`priced_lots_excluded` degrade-loudly :505-508. Renderer `_f3_behaviour`
`portfolio_finding.py:686-760`. Allow-list registration :997-1050. Scope filter
`training_trade_scope` imported from `sim_engine.py` (:93, :206) — the shared DEF269
function.

## Findings

See `orchestration/audit/cr/CR222-D.auditor.md` — MAJOR-1 (dollar-weighted PGR/PLR beside
count-based Odean baseline), MINOR-1 (no pinned no-grade/no-warning/no-verdict test for
the behaviour block), MINOR-2 (coincidental-"5" fixture still stands), one out-of-scope
note (degenerate 100%/100% rendering is algebraic, not a bug).
