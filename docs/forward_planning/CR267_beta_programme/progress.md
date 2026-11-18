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
5. **WP-01 done (gate S1).** Ledger `afee9f99` on `main`; outcome in plan §6 WP-01 item 3. Rows
   dropped on the branch: CR245, CR247, CR250, CR254. New WPs: WP-15 (CR252, behind S11), WP-38
   (CR239), WP-39 (CR022). Still to close: DEF386, DEF434. ⚠️ Company Apple/Google accounts are
   **not enrolled**; the Play account will be an Organisation account.
6. **Gates S11/S12 added** (Saiful): pause for an implementation-plan discussion before any LLM
   change (WP-15, WP-10–14) and before any Jev/grader change (WP-22, WP-23).
7. **WP-00 steps 3–5 and WP-01 closures.**
   1. Decisions D-076–D-089 appended; D-066/D-067 marked reopened, D-068 closed, D-072's hosting
      clause amended (`17fbacc5`).
   2. `project_plan.md` status block and Phase 2 point at CR267 (`17fbacc5`).
   3. The CR253 duplicate deletion is committed on main (`6ee0921c`); CR254 holds the same content.
   4. Ten October leftovers were read in full (836 lines, Sonnet reader, with the flag confirmed by me).
      Nine were clean and are committed on main under K's tag (`769f599b`).
   5. **Held back for Saiful:** `.deliveryos/checkpoint_history/20261017T222812Z_855f74dc…md`
      contains third parties' phone numbers and client-confidential deal details (non-AMI work).
      It is left untracked. Saiful decides whether to delete it, move it out of the repo, or redact
      and commit it.
   6. `20261118T111900Z_f2ac2318…md` is today's memo from the Fable session; not ours, left alone.
   7. DEF386 and DEF434 closed with evidence (`26bf7fb5`).
8. **WP-00 done.** Acceptance:
   1. `gen_registers.py gen all` after merging main leaves no diff.
   2. No WP-00-owned path is dirty. The two untracked memos above are listed here.
   3. Every row changed by WP-00/WP-01 reads `done` or `dropped` with a dated reason (13 rows).
