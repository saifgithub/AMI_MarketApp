# DEF321 — full-suite run log

**Why this file exists.** [DEF321](def_list.md) is an intermittent failure of
`test_sim_reputation.py::test_buy_without_stop_or_target_awards_nothing` in the shared checkout.
Its row sets the closing bar itself:

> If it stays green across a week of runs, close it citing DEF324. If it fires again, the cause is
> elsewhere.

Nothing was recording the runs, so every session's evidence evaporated at the end of that session
and the week could never accumulate. This is that record.

**The rule this file exists to enforce on its own reader:** the bar is *a week of runs*, not *n
green runs*. This defect's entire nature is intermittency, and closing it on a handful of greens is
exactly the error P24 was filed for — the row says so in its own words. **Do not close DEF321 from
this table alone.** Read the dates.

**What counts.** A full `backend/tests/unit/` run **in the shared checkout** — that is the
environment the defect lives in. A run in a fresh detached worktree does *not* count: DEF324
identified the trigger as the gitignored `backend/.local.db`, which exists in the shared checkout
and not in a clean worktree, so a worktree run cannot exercise the failure. That asymmetry is the
whole reason the earlier "passes SHA-pinned" note was wrong.

Read the `VERDICT:` line from `scripts/promotion/preflight_suite.sh`, never pytest's own summary
(DEF326).

| Date (UTC+3) | Result | passed / failed / skipped | Notes |
|---|---|---|---|
| 2026-08-17 | PASS | 4352 / 0 / 3 | recorded in that session's checkpoint memo |
| 2026-08-17 | PASS | 4356 / 0 / 3 | recorded in that session's checkpoint memo |
| 2026-08-18 | PASS | 4354 / 0 / 3 | AT:R70, at commit `9990289f` (DEF195 + DEF330) |
| 2026-08-18 | (suite red, **DEF321 test green**) | 4363 / 1 / 3 | the one failure was `test_registers_no_drift::test_registers_match_their_row_files`, collected mid-edit while register rows were being rewritten — my own dirty tree, DEF159's exact point, unrelated to DEF321. Logged rather than dropped: the reputation test *ran and passed*, which is the fact this table tracks. Confirmed green on the committed tree immediately after. |
| 2026-08-18 | PASS | 4376 / 0 / 3 | AT:R70, committed tree at `0173b43f` |
| 2026-08-26 | PASS | 5351 / 0 / 5 | AT:R74, shared checkout, DEF377 round |
| 2026-08-26 | PASS | 5348 / 0 / 5 | AT:R74, shared checkout, CR109 slice 7 round |
| 2026-08-26 | PASS | 5348 / 0 / 5 | AT:R74, shared checkout, after the l10n seed fix |
| 2026-08-26 | PASS | 5359 / 0 / 5 | AT:R74, shared checkout, CR054 canon-spine round |
| 2026-08-27 | PASS | 5362 / 0 / 5 | AT:R74, shared checkout, CR054 Wave 3 content round |
| 2026-08-27 | PASS | VERDICT: PASS | AT:R74, `preflight_suite.sh` at `ac3f4c1e`, promoting `alpha-2026-08-27-1` |

**Status: 11 recorded runs across 4 distinct days spanning 2026-08-17 to 2026-08-27** — ten
calendar days, and the second cluster is from a different week, different sessions, and a
working tree that was dirty in different ways on every run (content edits, register rewrites,
another lane's uncommitted `llm_gateway.py`/`room_runner.py` throughout). That is the variation
the bar was asking for, not just a higher count.

**One caveat, recorded rather than averaged away.** For part of this window the canary's FINAL
assertion was vacuous. CR109 slice 7 (`023cb815`, 2026-08-26) deleted every
`reputation_service.award()` call site, so `_events(user_id, "trade_disciplined") == []` became
unfailable. **The flaking assertion was never that line** — DEF321's observed symptom is
`status_code == 200` failing with *"position size 68.8% exceeds single-name cap 3.0%"*, and that
assertion was live in every run above. So the tally stands; but the test has been re-aimed and
renamed `test_a_patched_mandate_reaches_the_submit_path`, with the dead line removed and an
explicit store read-back added, so a future reader is not counting greens from a hollow test.

**Both root causes were found and fixed during this window**, which is why the greens are
expected rather than lucky: **DEF323** (`_walk_for` seeded from `hash()`, salted per interpreter
under PEP 456 — now `_stable_seed`, verified giving base `408.14` across three separate
interpreters) and **DEF324** (the gitignored `backend/.local.db` reachable through one teardown
window). This log's job was to prove the fixes held in the environment the defect actually lived
in, and eleven runs across ten days say they did.

**CLOSED 2026-08-27**, past the earliest defensible date this file itself named (2026-08-24).
