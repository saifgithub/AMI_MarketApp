# CR267 — Progress log

**What this is:** the hand-over between sessions executing the CR267 Beta programme, with one dated
entry per work-package state change, its commit and its acceptance evidence. **Why:** the plan
(§1.4) makes this file the cold-start anchor for whoever picks the work up next.

Branch `beta/cr267`, worktree `.claude/worktrees/cr267-beta`, track B. Rollback tag `pre-cr267`.

---

## 2026-11-18 — S0 given; WP-00 started (session B1)

1. **S0:** Saiful: "go, start WP-00".
2. **No child CR for WP-00.** It is docs and registers only (exempt under CLAUDE.md); commits are
   tagged `(AT:B1 CR267)`.
3. **WP-00 step 1 — CR266 run: completed, gate FAIL.** `~/cr266_ami_cards_complete_v2/` on
   melehost: 60/60 rooms; coverage 57/60; ICC(A,1) 0.810 < 0.85; 13/30 tickers flipped; 23 APPROVE
   / 37 PASS. Recorded in `CR266_decision_reliability/progress.md`.
4. **WP-00 step 2 — rows.**
   1. Closed with reasons: CR251, CR255, CR257, CR265, CR266 → `dropped` (superseded);
      CR253, CR256, CR259 → `done`.
   2. **Deviation from the plan's list.** CR252 and CR257 were never executed: no commits since
      2026-10-15, and the stocktake says CR257 was "drafted, unsent". CR257 is dropped because WP-22
      absorbs it. CR252 (measured GO, never folded in) stays `proposed` for WP-01 to decide.
   3. `CR253_data_lane_completeness/` was a separate, shipped item that collided on the CR253 ID.
      The Architect minted **CR268** for it; its row is `done`. Child CRs for later WPs start at
      **CR269**.
