<!-- lane hand-off — coder.api. CR052. -->
# BE-MINOR — coder.api hand-off

STATUS: READY_FOR_AUDIT (round 1)
BRANCH: lane/BE-MINOR.coder.api
COMMIT: f03a23cf

## What shipped

All three defects fixed, each pinned by a new regression test that goes RED when
the fix is reverted (verified by stashing each changed file in turn and re-running
its test).

**DEF165** — `sector_allocation.py::sector_cap_breach()`. The `max(portfolio_value,
holdings-derived total)` clamp that guards a stale/short `portfolio_value` is
unchanged (it still prevents weight > 1.0), but taking the fallback branch now logs
`sector_cap_stale_portfolio_value_fallback` with `ticker`, `sector`,
`supplied_portfolio_value`, `holdings_derived_total`. Test:
`test_def165_stale_portfolio_value_fallback_is_logged.py` — asserts the log fires
(and only fires) on the fallback branch, and pins that the fallback denominator is
specifically the holdings-derived (pre-DEF149) total, not merely that the weight
stays ≤ 1.0 (the exact gap the original DEF149 test left open).

**DEF169** — `safety_floor.py::check_mandate_compliance()`, step 6. When
`proposed.is_buy and proposed_value > 0` but `portfolio_value <= 0`, the
single-name cap now logs `safety_floor_single_name_cap_unevaluated` and appends to
a new `ComplianceResult.not_evaluated: list[str]` field (`schemas/trade.py`) —
`"single-name cap not evaluated — portfolio_value is not positive"`. Does not
touch `passed` (unevaluated ≠ blocked) or `violations`. Test:
`test_def169_single_name_cap_unevaluated_when_portfolio_value_zero.py`.

**DEF196** — `overlay_generator.py`. The static `— enforced as a hard block on the
next BUY, not a suggestion.` suffix moved off the `_mandate_common_block` template
line and into `_cooldown_text()`, so it's only emitted on the branch where the
resolved cooldown is `> 0`. The off-branch (`hours <= 0`) instead says `0` is a
no-op here, unlike the other caps. Added the requested doc line (as a code comment
next to the CR129 block) documenting that `0` binds as "block everything" on the
other six settable caps (`single_name_cap_pct`, `sector_cap_pct`,
`max_open_positions`, `max_trades_per_day`, `max_trades_per_week`,
`max_open_risk_pct`) but is a genuine no-op (zero-hour wait) on
`post_loss_cooldown_hours` specifically. No hand-edited numeric literals added —
every value in the copy is still interpolated from the resolver functions. Test:
`test_def196_overlay_never_contradicts_itself.py`, table-driven over all seven
settable fields × {set, unset}.

## Judgement call the assign asked for (DEF165)

**Does a stale `portfolio_value` deserve its own DEF for the staleness itself?**
No — I'm not filing one, and I don't think it's warranted as a *separate* defect
right now. Reasoning: `portfolio_value` is computed once per request from live
holdings + cash by the caller (Room runner / 1-on-1 path), not cached or persisted
across requests, so "stale" here really means "short" — the caller passed a number
that doesn't yet reflect a trade already accounted for in `holdings`/`quotes`
(e.g. a race between two proposals, or a caller bug upstream). That's a data-
integrity bug in whichever caller produces the mismatch, not a property of this
function — and now that the fallback is logged, if it ever fires in Alpha traffic
that log line is exactly the evidence needed to find and fix that specific caller.
Filing a DEF today would be speculative (I found no evidence it fires in practice,
only that the code path existed silently). Recommend: watch
`sector_cap_stale_portfolio_value_fallback` in Alpha logs post-promotion; file a
DEF against the specific caller if it ever actually fires.

## Mutation testing (acceptance 5)

All three reverted in turn (`git stash push -- <file>`, run that defect's test,
`git stash pop`) — all three went RED, none came back GREEN:

- DEF165: reverting `sector_allocation.py` → `test_stale_portfolio_value_below_holdings_logs_the_fallback` fails (`0 == 1`, no warning logged).
- DEF169: reverting `safety_floor.py` + `schemas/trade.py` → all 5 DEF169 tests fail (`ComplianceResult` has no `not_evaluated` attribute).
- DEF196: reverting `overlay_generator.py` → 2 of the 19 DEF196 tests fail on the exact `post_loss_cooldown_hours` contradiction (the other 17 params never had the bug — a field never contradicts because its narration never has an "off" branch, which is expected and documented).

## Full suite

`"./backend/.venv/bin/python" -m pytest backend/tests/unit/ -q` (venv borrowed from
main checkout — worktrees don't carry their own): **1768 passed, 0 failed** (baseline
1719; +14 new DEF165/169/196 tests, remainder is other lanes' commits already on
`main` at branch time). Read the `N passed, M failed` line directly, not piped.

## Registers

DEF165, DEF169, DEF196 all flipped to `fixed` in their own row files, `def_list.md`
regenerated (`scripts/registers/gen_registers.py gen def`), row files + regenerated
table committed in the same commit as the code (DEF159).

## Fences respected

Did not touch `mandate.py`, `mandate_store.py`, `one_on_one.py`, `brief_engine.py`,
`mandate.py` schema (BE-MANDATE), `sim_engine.py` (SIM-DEF166), `room_runner.py`
(ROOM-MINOR), `mobile/`, `DEF182`/`SECRET_KEY`/`infra/alpha.env`. Confirmed via
`git diff --stat` on the final commit — only the 4 app files + 3 new test files +
3 row files + `def_list.md` changed.

## Files touched

```
backend/app/agents/overlay_generator.py
backend/app/agents/safety_floor.py
backend/app/schemas/trade.py
backend/app/services/sector_allocation.py
backend/tests/unit/test_def165_stale_portfolio_value_fallback_is_logged.py   (new)
backend/tests/unit/test_def169_single_name_cap_unevaluated_when_portfolio_value_zero.py   (new)
backend/tests/unit/test_def196_overlay_never_contradicts_itself.py   (new)
docs/defect/_registry/DEF165.row.md
docs/defect/_registry/DEF169.row.md
docs/defect/_registry/DEF196.row.md
docs/defect/def_list.md
```

No `.architect.md` submit file — sprint mode, Architect integrates on their own
verification per the assign.

ASSIGNED: coder.api round 1
DISPATCH: READY_FOR_AUDIT
