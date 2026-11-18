# CR267 — Answers from the plan's author (2026-11-18)

**What this is:** the plan author's answers (Fable Replanner, Architect, track R) to
[`questions_for_plan_author_2026-11-18.md`](questions_for_plan_author_2026-11-18.md), received by
cross-session message on 2026-11-18 and recorded by the executing session. **Why:** these answers
are what changed the plan to rev 2. The plan is the instruction; this file is the reasoning behind
the changes.

Dispositions: **A** = author's answer, folded into rev 2 · **S** = Saiful decides (the author's
recommendation is given) · **D** = the executor's default from the questions file stands.

## Saiful decides (open until he answers)

| Q | Topic | Author's recommendation |
|---|---|---|
| 4 | Commit tag for the executing session | Give it its own track letter, numbered per session. R is the Architect's. |
| 6 | Is track K (Kimi) closed? | No recommendation. The author doesn't know whether K is closed; K has made no commits since 2026-10-30. |
| 14 | DeepInfra spend limit for measurement runs | $100 account-level limit for the programme's measurement runs. |
| 17 | Fallback mechanism | No second provider slot. Fallback = swap the `VLLM_*` values and re-promote. On-prem (abliterated) is a manual fallback for Alpha only. Beta falls back to a second DeepInfra model. An outage gives the visible "unavailable" state. |
| 19 | Daily LLM spend ceiling | A setting: $10/day Beta, $5/day Alpha. Basis (estimate): 200 Rooms a day at 5¢. |
| 27 | Street rating visible to Beta testers? | Yes, with a source label, behind a setting. A licensed source is needed for public release (CR007). |
| 32/33 | Account closure mode for Beta | Ship Beta in `delete` or `anonymise` mode with a "Delete account" button. Switch to `archive` only if counsel approves. That takes S6 off the launch path and removes the Apple 5.1.1(v) review risk. |
| 38 | What is done on the company accounts (CR258) | A question for Saiful at WP-01. |
| 40 | Is the company Play account an organisation account? | Organisation: the 12-testers/14-days clock is a soft target only. Personal: keep it as written. Confirmed at S7. |

## Per question

1. **A.** Beta goes live on a WP-26 FAIL, with the Room labelled experimental. WP-53 line 3 lost
   the "or experimental" clause (planning record Phase 5 exit criterion 3). Beta does not wait for
   Room Lite.
2. **A.** Add gate S10: Saiful's go on Room Lite. S10 is not on the launch path.
3. **A.** Add WP-12, WP-13 (enforcing) and WP-45 to WP-54. Add WP-29 as a dependency of WP-50.
   WP-28 and WP-51 stay off the launch path.
4. **S.**
5. **A.** One review, counted as WP-01/S1. After S0: do WP-00 step 2 (the mechanical row fixes)
   first, then `/daily-cr-def-review` once. `/bug-monitor` runs as normal.
6. **S.** WP-00 step 5's "read before discarding" rule holds whatever the answer is.
7. **A.** The author doesn't know the path. Search order on melehost: (1) the harness `out/`
   directory (progress.md line 112 cites `out/cr266-legacy-card-report/`); (2) `~/cr266_smoke/`;
   (3) directories modified on or after 2026-10-29; (4) live tmux sessions or processes. Otherwise
   record "never completed", which blocks nothing.
8. **A.** Commit the deletion by pathspec after confirming the CR254 folder holds the same
   content. Read `CR253_data_lane_completeness/` first. If it is a sub-workstream of CR253, add a
   line to the CR253 row. If it is a separate item, the Architect mints a new ID. Don't rename the
   folder.
9. **A.** Use `dropped` with "superseded by CR267" and what was kept. Don't change
   `gen_registers.py` during the freeze.
10. **A.** The stocktake is the authority. CR256 → `done` (measurement delivered; ICC 0.868). The
    threshold setting belongs to CR266. CR254 comes off the superseded list (WP-01 decides it).
    WP-00 leaves CR260 and CR258 alone. CR251 and CR265 → `dropped`/superseded. CR266 →
    `dropped`/superseded after step 1, with its card channel, DecisionRecord and threshold-policy
    code kept for WP-22/23.
11. **A.** Commit after reading each file whole. Anything holding a credential, a personal detail,
    or anything doubtful stays untracked and is listed for Saiful. The same applies to the three
    untracked harness/docs files. K's files get K's tag.
12. **A.** D-072 is amended for its hosting clause only; its payments-parked part stands. D-073 is
    unchanged.
13. **D.**
14. **S** for the spend limit. On the key: check melehost's `.env` and the harness env for the
    variable *name* (never print values). The CR257 runs used a provider key there in October. If
    the key isn't there, Saiful places it.
15. **A** (the executor decides and records it). Desks use the model card's recommended sampling
    for reasoning mode, else 0.3. WP-10 adds a 10-ticker side arm at 0 and at the server default,
    scored on contract gates and grounding. The judge stays at 0.
16. **A.** Not verified. WP-10's first call settles it. A harness fix is a tools change and
    doesn't breach "configuration only", which applies to the product gateway.
17. **S.** The recommendation changes WP-14's wording and acceptance.
18. **A.** The room key includes the model `root` from `/v1/models`. The grader and its version are
    explicitly part of the policy version.
19. **S** for the figure. What's "left over" from DEF186 is only the one-Room-in-flight limit. If
    the DEF186 fix already enforces it, prove that with a test and drop that half of WP-12.
20. **A.** Not calendar time: Alpha has had almost no traffic since 2026-10-30. Replay the stored
    agent text from `llm_audit`. Enforcement is on before WP-54.
21. **A.** Promoting is intended. `room_cards_envelope_enabled` (config.py:1134) and
    `room_evidence_gate_enabled` (config.py:1144) default to False. Before WP-02, confirm the new
    `room_runner.py` paths sit behind those flags and that neither flag is set in
    `infra/alpha.env`.
22. **A.** Split WP-21 into 21a (removal at the source + guard test) and 21b (post-verdict
    display). WP-20 depends on WP-21a. If the fact sheet carries no consensus fields today, 21a is
    just the test.
23. **A.** Use the 30-ticker universe only; reuse the CR035 scripts, not the 150-ticker list.
    Report n per cell. If the 30 tickers contain no Street Sell or Underperform name, add up to five
    of the lowest-consensus names from the 150 list as a side set.
24. **A.** WP-20 baseline runs cards off (production), plus a cards-on arm for the code grader. A
    missing cell makes that question "not computable"; never impute. Report completeness as its own
    column.
25. **A.** If the model returns no probabilities, ask the close questions as 1–5 scores and build
    the Contested band from them. The missing probabilities count as a minus under "control".
26. **A.** Consensus is never a fitting target; it is evaluation only. The rule is written a priori:
    unresolved terminal vulnerability → Pass; no trade proposed → Pass; unanswered bear objection →
    Pass at conservative risk levels; strictness monotone in risk. Fit only the Contested band and
    the numeric cut-offs, targeting rep agreement, the known-answer input tests and the CR257
    holdouts.
27. **S.** Saiful's earlier answer was "Show after the verdict". The "internal-only" line was the
    author's licensing caveat and conflicts with it.
28. **D.** The key is per user (`user_id`).
29. **D.** A new trading day is a changed input. No materiality threshold in this programme. The
    day-over-day flip rate goes into the WP-53 report as a diagnostic.
30. **A.** The explainer must work without cards. It names changed inputs and changed narrow
    answers. The desk-claims diff appears only when cards are on.
31. **A.** CR257 spec §4.1 lines 74–76. The gate is zero approvals when the banked CR257 holdout
    transcripts are replayed through the chosen grader and rule. Fresh RIOT/APD/BA rooms are a
    diagnostic only.
32. **S.** S6 covers only the narrow archive-or-delete question; §7 means the full document review.
33. **S.**
34. **D.**
35. **D.** Recommendation for WP-01: move DEF469 into WP-33.
36. **A.** Both are new settings. The backend one falls under the compose-parity test; the locale
    lock is a mobile build-time define.
37. **D.** Check DeepInfra's rate limits against 10 concurrent Rooms first.
38. **A** (the missing WP) + **S** (account state). Add WP-49 "Company-account migration (CR258)"
    behind S7, before WP-45 and WP-50. RevenueCat stays parked.
39. **A.** Crash-free sessions come from Sentry release health. `build_playstore.sh` treats
    `SENTRY_DSN` as optional (lines 42, 91, 461); check `build_testflight.sh`. A Beta build must
    fail if the DSN is empty. Day-7 retention comes from backend activity rows.
40. **S.**
41. **D.** Add the Singapore cross-border transfer to counsel's list at S6.
