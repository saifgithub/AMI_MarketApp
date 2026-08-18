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

**Status: 3 recorded runs across 2 distinct days.** The bar is a week. Earliest a close could be
argued on this evidence is **2026-08-24**, and only if every run in between is green and they are
genuinely spread across the days rather than clustered in one session.
