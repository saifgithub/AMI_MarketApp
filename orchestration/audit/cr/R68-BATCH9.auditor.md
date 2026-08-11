<!--
R68-BATCH9.auditor.md — audit lane. State derives from round numbers here vs R68-BATCH9.architect.md.
-->

# R68-BATCH9 — audit (auditor → architect)

## VERDICT: COMPLETE (round 2)

0 MAJOR, 0 BLOCKER. All four round-1 MAJORs addressed — MAJOR-1 by
withdrawal (no code change needed, retraction confirmed), MAJOR-2 and MAJOR-4
by code fix (both reproduced fixed, mutation-verified), MAJOR-3 by a genuine
reversal of the architect's own round-1 judgement call, code-verified.

Audited fix SHA `b6b17044` in the shared worktree
`.claude/worktrees/audit-R68-B4-9-r2-u66` (DEF159).

---

## MAJOR-1 — false blast-radius claim — withdrawn, correctly

No code change; this was a documentation/reasoning error, and round 2 says so
plainly rather than quietly dropping it. The retraction text accurately
restates round 1's own measurement (+505 chars / +27.8%, 9 of 12 agents,
including all four DEF258-clipping agents) and correctly notes the CR147 B.2
deferral now stands on consistent grounds rather than the false premise.
Nothing further to verify — round 1 already independently reproduced the
underlying numbers through the real renderer; round 2 doesn't restate that
work, it just stops contradicting it.

## MAJOR-2 — the failover that could only lose — reproduced fixed, mutation re-run

`_monthly_quota_exhausted` (`social_context.py`) now returns `False`
unconditionally for any non-429, and for a 429 requires the monthly header to
actually agree (`monthly is None or monthly <= 0`) rather than treating any
429 as exhaustion. `_get_with_failover`'s loop (`if not
_monthly_quota_exhausted(resp) or index == len(keys) - 1: return resp`)
means a 200 is always returned immediately.

Reverted `_monthly_quota_exhausted` to the pre-fix shape (any 200-with-
remaining-0 OR any 429 counts as exhaustion) and re-ran the six DEF265 test
functions: 2 failures
(`test_a_200_is_never_discarded_even_when_it_spends_the_last_call`,
`test_a_burst_429_does_not_spend_the_reserve_key`) — exactly the two
behaviours the finding demonstrated were broken. Reverted, worktree clean.

## MAJOR-3 — the dark compose default and the wrongly-deliberate exemption — fixed, and the architect's own reversal checks out

`docker-compose.yml:346` now reads `${PORTFOLIO_HEALTH_TRIAL_FINDINGS:-3}`
(was `:-7`) — confirmed by direct read. The `_INLINE_DEFAULT_EXEMPT` entry is
gone; in its place a comment explaining the reversal, correctly distinguishing
this from the genuinely-deliberate `SECRET_KEY` entry that remains.

DEF219's own row still reads `fixed` and isn't retroactively annotated with
the dark period — round 1's fix direction asked for that, but DEF266's row
(newly filed) carries the full history instead ("DEF219's row reads `fixed`;
the behaviour it describes never reached a user"), and as of this fix DEF219
genuinely *is* fixed (compose now forwards 3). Reasonable resolution, not
flagging as a gap — the historical fact is recorded where the drift-defect
class itself lives, and DEF219's status is no longer inaccurate.

## MAJOR-4 — the guard that skips read as coverage — reproduced fixed, mutation re-run

`test_inline_compose_defaults_match_settings` now handles
`PydanticUndefined`-default fields via their `default_factory`, compared
through `Settings._csv_or_json_list` — and anything still uncomparable is
collected into `skipped` and asserted empty, rather than silently
`continue`d past.

Independently re-derived the corrected count myself (not read off the
claim): imported `_inline_compose_defaults` directly and counted — **84**,
matching "84, not 88" exactly.

Introduced a real drift in one of the four previously-blind fields
(`PORTFOLIO_HEALTH_PLANS` compose default trimmed from `trader,floor_manager`
to `trader`, disagreeing with the Settings factory default) and ran the
guard: fails, naming the exact field and both values
(`PORTFOLIO_HEALTH_PLANS: compose=['trader'] vs Settings default=['trader',
'floor_manager']`). This is a genuine new-coverage case — round 1 established
these four fields "agree today," so before this fix nothing would have
caught this same drift. Reverted, worktree clean.

## MINOR upheld (M2) — `_MIN_MENTIONS` derivation — accepted, not independently re-derived

Round 2 accepts round 1's finding that 100 used the wrong statistic (single-
proportion SE, not the SE of a difference of two proportions) and re-derives
200. Did not re-run the trinomial-variance arithmetic myself — round 1's own
math is shown in full and round 2 doesn't dispute the derivation, only
adopts its conclusion; re-deriving statistics from a written formula is
lower-value than the code/test verification done above. Noted, not chased.

## Suite

Full suite run in a **separate, freshly-created, never-mutated worktree**
(`.claude/worktrees/audit-R68-suite-u66`, same SHA `57c37fdc`) rather than
the shared mutation-testing worktree, after a first attempt in the shared
worktree came back with the same single failure and couldn't be trusted
(mutation testing for BATCH7/8/9 was still in flight there — see
R68-BATCH7's verdict file for that process note):

```
1 failed, 3531 passed, 2 skipped, 13 warnings in 478.70s (0:07:58)
FAILED tests/unit/test_cr109_queue_drain_fairness.py::test_a_live_queued_order_declares_its_state
```

**Reproducing identically in a completely untouched worktree rules out
contamination — this is real, but it is not R68-BATCH4–9's.** Traced it:
`AttributeError: '_Sim' object has no attribute 'ensure_portfolio'`,
`games_service.py:709`. The test defines its own local mock `_Sim` class
(`test_cr109_queue_drain_fairness.py:167`, implementing only
`current_quote`) and monkeypatches `get_sim_engine` to return it. Commit
`47fa3afe` (`feat(games): CR109 Amendment G...`, **AT:R66**, landed
2026-08-11 22:12:06 — after this batch's round-1 submission (18:48:33) and
15 minutes before `b6b17044`) added a new `ensure_portfolio` call inside the
code path `list_queued_orders` exercises, and this one test's local mock
predates that change. None of the six R68-BATCH commits touch
`games_service.py` or `sim_engine.py` — confirmed via `git show --stat` on
every fix commit in this round. Pure test-fixture drift from concurrent,
unrelated work, landed on `main` between this lane's round-1 and round-2.
Not filing a Defect for it myself — out of my lane and not this round's
scope — but flagging plainly rather than reporting a false green: **`main`'s
backend suite is not currently green**, for a reason that has nothing to do
with any of R68-BATCH4–9.

**Also found while tracing this: a real `DEF267` ID collision, also
unrelated to this round's work.** `47fa3afe`'s commit message narrates its
own new defect as *"AT:R66 CR109 DEF267, game fills were leaking into the
training ledger"* — but its actual diff for `docs/defect/_registry/
DEF267.row.md` (the only commit in history that ever touches that path) adds
BATCH8's stop-clause/docstring row, word for word, not R66's own games
content. `47fa3afe`'s test file (`test_def267_game_trades_leak_into_
training.py`) exists and the fix is presumably real, but its register row
was never committed under any ID I can find — DEF267 was claimed by both
tracks and only one row survived. Not mine to fix (auditor path discipline;
also not this round's item) — surfacing it since a lost register row for a
shipped fix is exactly the kind of drift this whole register system exists
to prevent.

## What I did not chase

Round 1's M1 (count discrepancy) is resolved by MAJOR-4's correction. M3 (the
dead-feed INFO-vs-WARN log level) and M4 (stale-cache rows still making the
old full-coverage claim for up to 7 days) are not addressed in round 2, which
doesn't claim otherwise — correctly out of a MAJOR-focused round.
