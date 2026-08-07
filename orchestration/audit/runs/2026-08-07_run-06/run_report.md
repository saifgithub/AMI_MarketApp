# Run report — 2026-08-07_run-06

Item: CR131, round 1. SHA: `541234a1`. Verdict: **AWAITING_FIXES (round 1)** — 1 MAJOR,
2 MINOR, 0 BLOCKER. Full findings in `orchestration/audit/cr/CR131.auditor.md`.

## Collision with a concurrent auditor pass

Started this audit before noticing a concurrent instance (`AT:U66`) had already pushed
`VERDICT: COMPLETE (round 1)` as `7b0f4019` for the same round-1 submission. Read that
verdict in full before writing anything: its regression run, DEF166 check, ownership
check, winner/loser parity check, and both requested mutation reproductions all match
what I found independently below — no disagreement there, folded into the final lane
file rather than redone. The disagreement is narrower: `AT:U66` reproduced the mutation
the architect explicitly asked about (cohort lookup stubbed to `None`) and then, on the
architect-flagged coupling seam, deferred to the architect's own "agree not to fix it
here" framing without running an independent adversarial test of its own. This session
ran that test — see below — and it changes the answer.

## Setup

```text
cd "/Volumes/Extreme Pro/AMI_MarketApp"
git worktree add .claude/worktrees/audit-CR131 541234a1
```

## Regression suite (independent, scratch worktree, absolute interpreter)

```text
cd .claude/worktrees/audit-CR131/backend
"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest tests/unit/ -q
2588 passed, 13 warnings in 308.56s (0:05:08)
```

Matches the submission's claimed `2588 passed, 13 warnings in 299.11s` (~2.5% slower —
machine load, not a discrepancy; no divergence in pass count).

## Adversarial probes on the honesty-rules dimension (13 scenarios, throwaway file,
deleted after use — `test_auditor_cr131_adversarial.py` in the scratch worktree only)

All 13 passed on first run against the unmodified source:

1. `test_probe_days_threshold_actual_value` — confirms the shipped constant is `7.0`,
   not the `14` the submission/register describe (finding 2 in the lane file).
2. `test_probe_trade_count_boundary_9_vs_10_below` — 9 trades/side, plentiful days →
   `too_early`, zero numeric leaves.
3. `test_probe_trade_count_boundary_10_vs_10_at_threshold` — 10 trades/side → `ready`.
4. `test_probe_days_boundary_just_under_7` — active window 6d23h45m → `too_early`, no
   leak, despite 15 trades/side clearing the count floor.
5. `test_probe_days_boundary_exactly_at_7` — active window exactly 7d0h → `ready`.
6. `test_probe_lopsided_many_before_one_after` — 200 before / 1 after → `too_early`,
   no leak.
7. `test_probe_lopsided_one_before_many_after` — 1 before / 200 after → `too_early`,
   no leak.
8. `test_probe_zero_trades_before_switch_entirely` — `before_days` correctly resolves
   to 0 via the `before_start = switched_at` fallback, no crash, no leak.
9. `test_probe_zero_trades_after_switch_entirely` — `now == switched_at`, no crash,
   no leak.
10. `test_probe_all_trades_same_day_high_count` — 40+40 trades inside ~9 hours, count
    clears the floor on both sides, days floor still correctly refuses.
11. `test_probe_refusal_payload_exact_keys` — refusal is a hard `{status, message}`
    set on both `not_in_cohort` and `too_early`; `message` contains no digit
    characters (defence against a prose-smuggled count).
12. `test_probe_winning_user_no_asymmetric_extra_fields_vs_losing` — matched
    winner/loser, identical key sets top-level and per-window, identical
    `baselines` object, no banned moralising key in either.
13. `test_probe_trade_exactly_at_switch_boundary_active_side_and_docs_agree` — boundary
    trade lands ACTIVE, matches the documented `>=` rule.

## Mutations — reproduced independently, not trusted from either the submission or
## the concurrent COMPLETE

```text
# _meets_threshold -> True unconditionally
2 failed, 10 passed
  FAILED test_thin_sample_refuses_when_too_few_days_elapsed
  FAILED test_thin_sample_refuses_when_too_few_trades
# reverted, 12 passed
```

```text
# _earliest_day_trader_switch hard-stubbed to return None (function itself, not just
# the call site — the faithful reading of "stub the cohort lookup")
7 failed, 5 passed
  FAILED test_earliest_switch_entry_wins_when_multiple_exist
  FAILED test_thin_sample_refuses_when_too_few_days_elapsed
  FAILED test_thin_sample_refuses_when_too_few_trades
  FAILED test_hand_built_fixture_turnover_and_win_rate_arithmetic
  FAILED test_disposition_effect_losers_held_longer_than_winners
  FAILED test_winning_and_losing_users_get_the_same_response_shape
  FAILED test_endpoint_returns_ready_comparison
# reverted, 12 passed
```

Both match the submission's claims exactly. Noted in the lane file: a narrower
mutation that bypasses only the internal call site (leaving the function itself
callable and correct) gives 6 failures, not 7, because it doesn't touch
`test_earliest_switch_entry_wins_when_multiple_exist`, which calls the function
directly — recorded for precision; doesn't change the verdict on the claim.

## The decisive mutation — cohort-marker copy drift (mandate.py, not the lookup)

This is the one the architect's §3 raised and asked to be checked, and the one the
concurrent COMPLETE didn't independently run:

```text
# mandate.py:156, changed "...preset applied — ..." -> "...preset now active — ..."
# (still contains the literal substring "Day Trader preset")
cd backend && "…/.venv/bin/python" -m pytest tests/unit/ -q
2589 passed   # full suite, INCLUDING CR129's own adjacent guard, stays green
```

Then, against the same mutated tree:

```python
>>> compute_day_trader_outcomes(user_id)  # user who just switched via the real PATCH
{'status': 'not_in_cohort', 'message': 'This user has not switched on the Day Trader preset — there is nothing to compare.'}
```

Zero test failures, real endpoint, real user, silent wrong answer. Reverted
(`git diff` clean), re-confirmed targeted suite green (33 passed —
`test_cr131_day_trader_outcomes.py` + `test_cr129_risk_limits_from_risk_tolerance.py`).

## New pin added this round

`backend/tests/unit/test_cr131_cohort_marker_coupling_pin.py` — drives the real PATCH
endpoint, asserts cohort detection agrees. Verified: 1 passed against real code;
1 failed (naming the drift) against the mutation above; full suite still green with it
present (2603 passed on the shared tree — not cited as CR131 evidence per DEF159,
other lanes have uncommitted work in that tree right now; the scratch-worktree 2588 is
the evidence of record for this submission).

## Verdict

`AWAITING_FIXES (round 1)`. 1 MAJOR (cohort-marker coupling — no test protected
against real-world drift; now partially mitigated by the pin above, full fix is the
shared-constant refactor the architect himself proposed), 2 MINOR (14-vs-7 threshold
description mismatch across the submission/commit-message/register; README minimum-set
item 5 — survival-curve positioning — not computed and not disclosed as a gap).
Supersedes the concurrent `COMPLETE (round 1)` (`7b0f4019`) on this new evidence.
