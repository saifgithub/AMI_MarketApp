<!--
DEF419-BE.architect.md — audit lane. State derives from round numbers here vs DEF419-BE.auditor.md.
GATE: independent (CR231 / D-072). It touches the safety-floor input path, so it is Tier A.
-->

# DEF419-BE — audit lane (per-account mandate check on /v1/sim/preview)

**SCOPE:** chunk (the backend half; the mobile half follows as DEF419-MOBILE)

**TIER: A.** This changes what `check_mandate_compliance` sizes against: it swaps in a different denominator and holdings set.

**SHA:** `b945142c` (fix) + `942b937b` (merge of `main`; the only conflict was the generated register, which I regenerated). Both are on `main`. Review with `git diff 4fb4f02f..b945142c`.

**depends-on:** none. **Promoted:** no. It needs `/promote-to-alpha` after this verdict, and the mobile half is useless without it.

## What and why
Saiful, 2026-09-24, from TestFlight +108 screenshots (ASML, buy 10 @ $1731, destination ALPACA PAPER → "position size 137.2% exceeds single-name cap 100.0%"):

> *"When placing an order either for both or for alpaca paper only, the mandate is checked against the local AMI SIM account. The mandate should check limits based on the account in use. It does mean that it may reject for ami and approve for alpaca. Or vice versa. This is an expected condition."*

**The fix:**
- `SubmitTradeRequest.account: AccountSnapshotIn | None` is read by the **preview** endpoint only.
- When present, `SimEngine.preview` runs the SAME `check_mandate_compliance`, with the SAME mandate, against the snapshot's equity, cash and positions.
- When absent, behaviour is byte-identical to before.
- Submit ignores the snapshot, so an AMI fill can never be sized against a foreign account.
- The response echoes `account_kind`.

Design note, including the per-account / per-user / mandate-level rule table: `docs/defect/DEF419_per_account_mandate_check.md`.

## Tests (Architect re-ran on the merged tree, bare)
`cd backend && .venv/bin/python -m pytest tests/unit/test_def419_per_account_mandate_check.py tests/unit/test_safety_floor.py tests/unit/test_sim_engine.py tests/unit/test_p30_registers_name_things_that_exist.py tests/unit/test_config_compose_parity.py -q -p no:cacheprovider` → `71 passed, 1 skipped` (exit 0).

The builder also ran `-k "sim or alpaca or safety_floor or preview or mandate or account"` → 403 passed. That is not the full suite: the shared Mac is overloaded, and the auditor's run on melehost is the authoritative one.

## Measurement
None live yet. The reproduction for the auditor on Alpha after promotion:
- Preview the ASML ×10 order with a $100k `alpaca_paper` snapshot. It should be accepted.
- Preview the same order without the snapshot. It should be rejected at about 137%.

## Attack surface (please probe)
1. **Client-attested snapshot (known limit, CR202 custody):** the server cannot verify the Alpaca figures. Judge whether validation is tight enough: the finite, bounded, `extra=forbid` and ticker-pattern checks. Judge whether "the user lies about their own paper account" is acceptable for a paper-only mandate (D-071).
2. **Drawdown is set to `0.0` on the snapshot path:** the drawdown rule can never fire for Alpaca. Is that silent (the CR040 degrade-loudly question)? Should the preview surface "drawdown not measurable for this account" instead?
3. **Shorts are ignored:** `sizing_shorts=None`, and negative quantities in the snapshot produce `avg_cost` 0 and are dropped from quotes. Does a short Alpaca position escape the long_only and gross-exposure checks?
4. **Per-user limits read the AMI ledger:** the total open-risk cap, trade counts and cooldown all come from AMI's own history. Is sizing open risk on AMI's ledger right when the order goes to Alpaca?
5. **Bypass:** can a preview with the snapshot be replayed into `submit` so an AMI fill is sized against the foreign equity? The builder says submit ignores the field.
6. **No persistence:** the preview must still perform zero DB writes. There is a dedicated guard test.

SUBMITTED: round 1

## Round 2

**SHA:** `a51ea92d` (this branch, `.claude/worktrees/agent-aeb78b50ed54a6a98`). Not yet on `main` / promoted.

Saiful's ruling was fetched, not designed here: 2026-09-24, verbatim —

> *"Disclose, don't block. For Alpaca-destination previews, the rules AMI cannot measure for that account — account drawdown and existing open risk (AMI has no NAV history and no stop data for the Alpaca account) — are NOT evaluated against fabricated or foreign-denominated numbers, and the preview response states it explicitly. Every measurable rule still applies; the NEW trade's own risk still counts against the open-risk cap measured against the Alpaca equity."*

### MAJOR-1 (open risk summed at the AMI denominator)

**Fix:** `backend/app/services/sim_engine.py:2503-2650` (`SimEngine.preview`, account-snapshot branch). `sizing_existing_open_risk_pct` is now a branch-local variable — `ctx.existing_open_risk_pct` (AMI-denominated) on the no-account path, hardcoded `0.0` **plus an `unmeasured_rules` entry** on the snapshot path — passed to `check_mandate_compliance(existing_open_risk_pct=sizing_existing_open_risk_pct, ...)` instead of always `ctx.existing_open_risk_pct`. Per the ruling's second sentence, the NEW trade's own risk still counts: `SimEngine.preview()` gained a `stop: float | None = None` parameter (`sim_engine.py:2430`, `2432` in the signature), forwarded as `proposed_stop=stop` (`sim_engine.py:2652`) — previously `preview()` had no way to receive a stop at all on ANY path, so `proposed_contribution` was silently always `0.0`; this is additive (still `None`/`0.0` by default) and now lets the snapshot path's own `proposed_contribution` (priced against `portfolio_value`, the ALPACA equity on this branch) breach the cap on its own. `backend/app/api/sim.py:697` (`preview_trade`) forwards `stop=req.stop`, previously dropped entirely.

**Tests:** `test_open_risk_not_carried_over_from_ami_at_the_wrong_denominator` (the regression itself — a real $6,000/50%-stop AMI position, 30.0 open-risk points on AMI's own $10k book, no longer blocks an unrelated $1 preview against a $500k empty Alpaca account with a 5.0pt cap) and `test_new_trades_own_risk_still_counts_against_alpaca_equity` (the ruling's own requirement — the same $5,000/10%-stop order blocks against a $10k Alpaca account, 5.0pt > 3.0pt cap, and clears against a $500k one, 0.1pt < 3.0pt cap), both in `backend/tests/unit/test_def419_per_account_mandate_check.py`.

**Mutation evidence:** reverted `existing_open_risk_pct=sizing_existing_open_risk_pct` back to `existing_open_risk_pct=ctx.existing_open_risk_pct` (the round-1 bug) in a scratch edit — `test_open_risk_not_carried_over_from_ami_at_the_wrong_denominator` failed: `AssertionError: {"accepted":false, ... "violations":["total open risk 30.00% exceeds cap 5.0%"] ...}` (the exact wrong-denominator shape the auditor's own round-1 probe found). Reverted the mutation; full DEF419 suite (25 tests) green again.

### MAJOR-2 (drawdown silently inert)

**Fix:** same branch, `sim_engine.py:2536-2549` (approx). `sizing_drawdown_pct = 0.0` is unchanged arithmetic (there is no better number AMI can compute here — see the DEF doc's Known Limitation) but is now paired with an `unmeasured_rules.append({"rule": "drawdown", "reason": "..."})` call. New field: `PreviewResult.unmeasured_rules: list[dict]` (`sim_engine.py`, `PreviewResult` dataclass) → `PreviewTradeResponse.unmeasured_rules: list[dict]` (`backend/app/api/sim.py`, new field on the response model, forwarded from `pv.unmeasured_rules`). Empty list on the no-account path (verified explicitly, not merely absent of the two known entries).

**Tests:** `test_unmeasured_rules_empty_on_ami_path`, `test_unmeasured_rules_names_drawdown_and_open_risk_on_snapshot_path` (asserts the rule set is exactly `{drawdown, existing_open_risk}` with non-empty reasons), `test_unmeasured_rules_absent_when_every_rule_is_measurable` (the AMI/Alpaca contrast on the identical order).

**Mutation evidence:** commented out the `unmeasured_rules.append({"rule": "drawdown", ...})` call in a scratch edit — `test_unmeasured_rules_names_drawdown_and_open_risk_on_snapshot_path` and `test_unmeasured_rules_absent_when_every_rule_is_measurable` both failed (`assert 1 == 2`, only `existing_open_risk` present). Reverted; suite green again.

### MINOR-1 (no-persistence guard narrower than its claim)

**Fix:** `backend/tests/unit/test_def419_per_account_mandate_check.py` — new `_trade_table_counts(user_id)` helper queries `SimPortfolioRow`, `SimTradeRow`, `SimShortPositionRow`, `SimOptionTradeRow` (imports added at the top of the file). `test_account_context_preview_never_persists` rewritten to assert `after["trades"] == before["trades"] == 0` etc. across all three trade tables, not only the portfolio row. No production-code change — this is a guard being widened to match its own claim, per the auditor's finding.

**Tests:** the widened `test_account_context_preview_never_persists` itself passes (0 rows before/after across every table, exactly the auditor's own probe shape `{'trades': 0, 'shorts': 0, 'options': 0}`).

### Evidence, run bare on this branch

```
cd backend && .venv/bin/python -m pytest tests/unit/test_def419_per_account_mandate_check.py \
  tests/unit/test_safety_floor.py tests/unit/test_sim_engine.py \
  tests/unit/test_p30_registers_name_things_that_exist.py tests/unit/test_registers_no_drift.py \
  tests/unit/test_config_compose_parity.py tests/unit/test_wire_contract_parity.py -q -p no:cacheprovider
86 passed, 1 skipped in 14.14s        EXIT=0
```

`test_def419_per_account_mandate_check.py` alone: 25 passed (20 round-1 + 5 round-2), exit 0.

### Governance

`docs/defect/DEF419_per_account_mandate_check.md` updated: ruling quoted verbatim, rule table's Drawdown/Total-open-risk rows updated to reflect the disclosure mechanism, new "Round 2" section with the fix detail above, Tests section updated to 25, Status corrected from stale `open` to `fixed` (both halves were already implemented; round 1 had simply never updated this section after the row file moved to `fixed`). `docs/defect/_registry/DEF419.row.md` appended (not rewritten) with a round-2 summary paragraph covering both halves; registers regenerated (`gen_registers.py gen all`) and `test_registers_no_drift.py` / `test_p30_registers_name_things_that_exist.py` both pass.

### What I did not touch

Attack surfaces 1/3/5/6 from round 1 (client-attested-input bounding, shorts structurally excluded, no submit bypass, persistence — now widened per MINOR-1 above) were found sound by the auditor and are unchanged this round.

SUBMITTED: round 2
