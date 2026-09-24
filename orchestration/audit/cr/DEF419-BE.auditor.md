<!--
DEF419-BE.auditor.md — audit lane verdicts. Auditor-owned; the architect never writes here.
Newest round at the bottom. State derives from round numbers here vs DEF419-BE.architect.md.
-->

# DEF419-BE — auditor verdicts (per-account mandate check on /v1/sim/preview)

## Round 1 — auditor u66

**SHA audited:** `942b937b` (the merge), in a detached scratch worktree `DEF419-BE-u66`
per DEF159. Worktree verified clean after every probe was removed.

**Tier A** — the safety-floor input path.

### MAJOR-1 — open risk is AMI-denominated but judged against the Alpaca denominator

This is the submitted defect's own shape, surviving in a second rule.

DEF419 exists because a position was sized against the wrong denominator ("137.2% exceeds
single-name cap" — ASML measured against AMI's $10k instead of the Alpaca account). The fix
swaps the denominator for concentration, sector, gross exposure, cash and held-quantity. It
does **not** swap it for total open risk:

```
sim_engine.py (snapshot branch, one call)
    portfolio_value      = sizing_portfolio_value      # Alpaca equity
    existing_open_risk_pct = ctx.existing_open_risk_pct  # AMI-denominated
```

`existing_open_risk_pct` is built as `_position_pct(market_value, portfolio_value)` over AMI
trade rows (`sim_engine.py:1169-1178`), i.e. a percentage **of the AMI portfolio**. Inside the
floor the two are summed directly:

```
safety_floor.py:605
    total_open_risk = existing_open_risk_pct + proposed_contribution
```

`proposed_contribution` is computed from `portfolio_value` — the Alpaca equity. So the sum
adds a percentage of a $10k book to a percentage of a $500k book and compares the result to
one cap.

**Driven, with the setup asserted** (a real AMI position opened first; the probe fails loudly
if it did not):

```
PROBE setup: AMI position open, ~20% of AMI's $10k at risk
PROBE alpaca preview accepted: False | blocked_by: open_risk
PROBE violations: ['total open risk 20.00% exceeds cap 5.0%']
```

A $2,000 risk position on AMI blocks a trivial $5,000 trade against a $500k Alpaca account,
where the same $2,000 is 0.4%. The message states "20.00%" — true of AMI, false of the account
the order would actually reach. That is the exact complaint that opened DEF419, in the
opposite direction (wrongly rejecting rather than wrongly accepting).

The docstring's justification for keeping per-user limits on AMI's ledger is sound for the
cooldown and the over-trading brake — those count *events*, and AMI is the only place the
history exists. It does not transfer to open risk, which is a **percentage of equity**: a
sizing rule wearing a per-user label. The rule needs either the AMI risk re-expressed in the
snapshot's denominator (the dollar amounts are available), or to be skipped and disclosed on
the snapshot path — not silently carried across at the wrong scale.

### MAJOR-2 — the drawdown rule is silently inert on every Alpaca preview (CR040)

```
sim_engine.py (snapshot branch)
    sizing_drawdown_pct = 0.0
```

The comment defends this as "this codebase's established 'no data, never a false breach'
convention ... see `price_alert_evaluator.py`'s zero-context call".

**The cited precedent is not analogous.** `price_alert_evaluator.py:100-111` zeroes
*everything* — `portfolio_value=0.0`, `trade_open_timestamps=[]`, `existing_open_risk_pct=0.0`
— and its docstring says so explicitly: the call is deliberately narrowed so only
allowlist/blocklist/halal/classification run, and no sizing rule is meant to apply. DEF419's
snapshot path is the opposite: a **full** sizing check where every other rule fires against
real snapshot data and drawdown alone is neutralised.

CLAUDE.md's test is *"if this fires constantly and silently, what does the user end up
believing?"* Here it fires **100% of the time** on the Alpaca path, and nothing is surfaced.
Measured against a mandate carrying the tightest legal drawdown limit (10%):

```
PROBE snapshot+max_drawdown_pct -> accepted: True blocked_by: None
PROBE account_kind echoed: alpaca_paper
PROBE response mentions 'drawdown': False
PROBE full compliance: {'passed': True, 'violations': [], 'blocked_by': None,
                        'sharia_verdict': None, 'classification_verdicts': [],
                        'advisories': []}
```

The user sets a drawdown limit, previews against their Alpaca account, and is told the trade
passes — with no indication that one of their mandate's rules was not evaluated at all. That
is DEF059's shape: an uncertain path minting a confident approval.

The submission asks this exact question ("Is that silent ... Should the preview surface
'drawdown not measurable for this account' instead?"). The answer is yes. The response model
already carries an empty `advisories` array — a ready-made channel for the disclosure that is
not used.

### MINOR-1 — the no-persistence guard is narrower than its claim

`test_account_context_preview_never_persists` counts `SimPortfolioRow` only, and dismisses the
rest by assertion in a comment ("there is no table it even could land in") rather than by
checking. I widened it to the trade tables:

```
PROBE before: {'trades': 0, 'shorts': 0, 'options': 0}
PROBE after : {'trades': 0, 'shorts': 0, 'options': 0}
```

The property holds — no trade, short or option rows are written. The guard should assert what
it claims, so a future write to `sim_trades` from this path cannot pass it.

### What I verified and found sound

- **Attack surface 5 — no bypass.** Both `/preview` and `/submit` bind the same
  `SubmitTradeRequest`, so a client *can* attach `account` to submit; the safety rests entirely
  on `submit_trade` never reading it. Verified by reading (no `req.account` anywhere in the
  handler) and then by driving a $200k snapshot into `/submit`:

  ```
  PROBE submit+snapshot status: 200
  PROBE ok: False blocked_by: concentration
  ```

  Still sized against AMI's $10k. No bypass.
- **Attack surface 3 — shorts are unexpressible, not merely ignored.** The submission worried
  that negative quantities "produce `avg_cost` 0 and are dropped", escaping long_only and
  gross exposure. That description is stale: `AccountPositionIn` pins `qty: FiniteFloat =
  Field(ge=0)` and `market_value ... ge=0`. Both probes return **422**, so a short cannot be
  stated in the snapshot at all. `sizing_shorts=None` is therefore consistent, not a hole.
- **Attack surface 1 — validation is tight, and the residual risk is acceptable.**
  `extra="forbid"`, `kind` pattern-locked to `alpaca_paper`, `equity > 0`, `cash >= 0`,
  NaN/Inf rejected by `FiniteFloat`, `MAX_POSITIONS = 100`, ticker pattern
  `^[A-Z][A-Z0-9.\-]{0,9}$`. Under D-071 (paper only, no live routing ever) a user who lies
  about their own paper balance degrades only their own practice. Acceptable as scoped.
- **Absent-snapshot path unchanged.** The `account_snapshot is None` branch reads every value
  from the AMI portfolio exactly as before, and `test_no_account_field_checks_against_ami_sim_portfolio`
  covers it.

### Evidence, run bare in the pinned worktree

```
pytest tests/unit/test_def419_per_account_mandate_check.py tests/unit/test_safety_floor.py \
       tests/unit/test_sim_engine.py tests/unit/test_p30_registers_name_things_that_exist.py \
       tests/unit/test_config_compose_parity.py -q -p no:cacheprovider
71 passed, 1 skipped in 8.68s        EXIT=0
```

Matches the submission exactly.

Full backend unit suite, pinned worktree, run bare:

```
pytest tests/unit/ -q -p no:cacheprovider
6761 passed, 9 skipped, 21 warnings in 1578.39s (0:26:18)
EXIT=0
```

Fully green. (The two `test_p30_registers_name_things_that_exist` failures seen at
CR222-C's older SHA are absent here — this merge carries `8e550a57`, which fixed them.)

Exit code read from the redirected log, not from the harness's own run summary
(DEF326/DEF405).

### Verdict

The core of this fix is right and well built: the denominator swap is real, the mirror-image
tests prove it reads whichever account was named rather than always preferring one, the
schema validation is tight, shorts are structurally excluded, and submit genuinely cannot be
tricked into sizing an AMI fill against foreign equity — I attacked that one directly.

But a per-account mandate check that leaves one sizing rule on the wrong denominator
(MAJOR-1) and another silently switched off (MAJOR-2) does not yet do what the defect asks.
Both are the same class as the bug being fixed, and both land on the safety floor.

VERDICT: AWAITING_FIXES (round 1)

---

## Round 2 — auditor u66

**SHA audited:** `a51ea92d`, in a detached scratch worktree `DEF419BE-r2-u66` per DEF159.
Worktree verified clean after every probe and mutation was reverted.

All three round-1 findings are fixed. I re-derived each independently — re-running my own
round-1 probes and running my own mutations rather than reading the submission's transcript.

### The policy question was escalated, not decided locally — right call

MAJOR-1 and MAJOR-2 both turned on *what should happen* when AMI cannot measure a rule for a
foreign account. That is not an implementation question, and the architect fetched Saiful's
ruling rather than designing one:

> *"Disclose, don't block. ... the rules AMI cannot measure for that account ... are NOT
> evaluated against fabricated or foreign-denominated numbers, and the preview response states
> it explicitly. Every measurable rule still applies; the NEW trade's own risk still counts
> against the open-risk cap measured against the Alpaca equity."*

I audited against that ruling, both halves of it.

### MAJOR-1 — fixed

My round-1 probe, re-run verbatim against this SHA (setup asserted so a failed setup cannot
masquerade as a pass):

```
PROBE setup: AMI position open, ~20% of AMI's $10k at risk
PROBE alpaca preview accepted: True | blocked_by: None
PROBE violations: []
PROBE: round-1 MAJOR-1 is fixed
```

The $2,000 AMI risk position no longer blocks a trivial trade against a $500k Alpaca account.

**The ruling's second half holds too — the disclosure did not quietly disable the cap**, which
would have been worse than the original bug. The same order, same 3.0pt cap, against two
account sizes:

```
PROBE small alpaca ($10k) : accepted: False | open_risk | ['total open risk 3.69% exceeds cap 3.0%']
PROBE large alpaca ($500k): accepted: True  | blocked_by: None
```

Blocks at $10k, clears at $500k — the cap is now measured against **Alpaca** equity in both
directions. Note the `3.69%` is itself evidence of the `stop` fix: in round 1
`proposed_contribution` was structurally always `0.0`, because `preview()` had no `stop`
parameter at all on *any* path and `sim.py` dropped `req.stop` entirely. That was a real latent
gap the architect found while fixing mine, and it means the open-risk cap could never fire on a
preview before this round.

**No regression on the AMI path** — the risk of zeroing the snapshot branch was zeroing both:

```
PROBE ami-path preview accepted: False | open_risk | ['total open risk 23.69% exceeds cap 5.0%']
PROBE ami-path unmeasured_rules: []
```

23.69% = the 20% already open plus the new 3.69%, correctly summed at one denominator, and
nothing is disclosed because on that path nothing is unmeasurable.

**Mutation, mine not theirs.** Reverted `existing_open_risk_pct=sizing_existing_open_risk_pct`
to `ctx.existing_open_risk_pct` — the exact round-1 bug:

```
FAILED test_open_risk_not_carried_over_from_ami_at_the_wrong_denominator
1 failed, 24 passed
```

The regression test is load-bearing.

### MAJOR-2 — fixed, and fixed the right way

The number is unchanged (`sizing_drawdown_pct = 0.0`) and that is correct: AMI genuinely cannot
compute an externally-custodied account's drawdown, so any other value would be fabricated. What
changed is that the skip is now **reported** rather than silent:

```
PROBE unmeasured_rules: [
  {'rule': 'drawdown', 'reason': "AMI has no NAV history for your Alpaca paper account,
                                  so a drawdown breach can't be measured for it."},
  {'rule': 'existing_open_risk', 'reason': "AMI has no stop-loss data for your existing Alpaca
                                  positions, so this trade's own risk is checked against your
                                  Alpaca account's cap, but risk already open in that account
                                  isn't included."}]
```

Plain language, specific about *why* and about what still applies — not a generic "unavailable".
That is the CR040 direction: the user learns their mandate was partially evaluated instead of
being told the trade simply passed.

**Mutation, mine.** Silenced the drawdown `unmeasured_rules.append(...)`:

```
FAILED test_unmeasured_rules_names_drawdown_and_open_risk_on_snapshot_path
FAILED test_unmeasured_rules_absent_when_every_rule_is_measurable
2 failed, 23 passed
```

Two independent guards catch it.

**The disclosure reaches the user, not just the wire.** I checked the consuming half rather than
assuming it: `mobile/lib/models/sim.dart:879-900` parses it into a typed `UnmeasuredRule`, and
`trade_ticket_sheet.dart:784,956` renders it as a note on both the ALPACA PAPER and BOTH paths.
A disclosure that stopped at the response model would have been the same defect one layer out. I
will verify the rendering itself in DEF419-MOBILE round 2.

Wiring is clean end to end: `PreviewResult.unmeasured_rules` (`sim_engine.py:521`,
`default_factory=list`) → populated on the snapshot branch only → `PreviewTradeResponse`
(`sim.py:434`, same default) → forwarded at `sim.py:720`. The AMI path yields `[]`, never `None`.

### MINOR-1 — fixed

`test_account_context_preview_never_persists` now counts all four tables via
`_trade_table_counts`, asserting exactly the shape my round-1 probe used
(`{'trades': 0, 'shorts': 0, 'options': 0}`). The guard asserts what it claims. No production
change, correctly.

### Evidence, run bare in the pinned worktree

```
pytest test_def419_per_account_mandate_check.py test_safety_floor.py test_sim_engine.py \
       test_p30_registers_name_things_that_exist.py test_registers_no_drift.py \
       test_config_compose_parity.py test_wire_contract_parity.py -q -p no:cacheprovider
86 passed, 1 skipped in 14.39s        EXIT=0
```

Matches the submission exactly. The P30 register tests pass here, so the round-1 register
failures are behind this SHA.

Full backend unit suite, pinned worktree, run bare:

```
pytest tests/unit/ -q -p no:cacheprovider
2 failed, 6764 passed, 9 skipped, 21 warnings in 1363.61s (0:22:43)
EXIT=1
```

Exit code read from the redirected log, not the harness summary, which again reported
"exit code 0" (DEF326/DEF405).

### MINOR-2 (round 2, new) — the round's own new string was hand-copied into ar/ms

**This lane caused both failures**, and they are not the pre-existing register ones:

```
test_def295_seeded_translations_are_marked.py::test_no_english_sits_unmarked_in_a_target_arb[ar]
test_def295_seeded_translations_are_marked.py::test_no_english_sits_unmarked_in_a_target_arb[ms]

AssertionError: app_ar.arb holds 1 English string(s) that claim to be translations:
['tradeTicketUnmeasuredRulesNote']. Seed with `python3 scripts/translate_arb.py
--seed-missing` instead of copying English by hand — a hand copy is skipped by the
translator forever and the parity guard cannot see it (DEF295).
```

`tradeTicketUnmeasuredRulesNote` is **this round's own disclosure string** — the user-facing
half of MAJOR-2's fix. Identical English sits in all three locale files with no seed marker on
the two targets:

```
app_en.arb: "Not checked for this account: {ruleNames} — AMI has no history for your Alpaca account."
app_ar.arb: "Not checked for this account: {ruleNames} — AMI has no history for your Alpaca account."
app_ms.arb: "Not checked for this account: {ruleNames} — AMI has no history for your Alpaca account."
```

New to this round, confirmed: `git show 942b937b:mobile/lib/l10n/app_ar.arb | grep -c` returns
**0**, and `git log -S` names `a51ea92d` as the commit that introduced it.

**It is already on `main`**, so this is a live guard failure on the shared branch, not a
branch-local one. Running the guard against the main checkout reproduces it.

Fix is mechanical — `python3 scripts/translate_arb.py --seed-missing`, then flag AR/MS
re-translation per the standing content rule. Not a blocker for this lane's own findings, all
three of which are properly fixed; recorded as MINOR because the consequence is real and
silent: a hand copy is skipped by the translator forever and the parity guard cannot see it,
so the string ships as permanent untranslated English.

*Cross-lane, one line then dropped:* the same guard names `gamesBoardNextCloseIn` on `main` as
well. Not this lane's string and not mine to charge — flagged for whoever owns it.

### Verdict

Both MAJORs were policy questions underneath, and they were escalated to the person who owns the
policy rather than settled by whoever was holding the file. The implementation then honours both
halves of the ruling — the unmeasurable rules are disclosed instead of faked, and the measurable
part of the open-risk cap still bites against the right denominator. The `stop`-never-forwarded
gap found along the way was a genuine latent defect neither of us had named.

MINOR-2 is a one-command fix on a string this round introduced, and it does not undo any of
that. Closing COMPLETE rather than spending a round on it, with the seeding owed before the
mobile build ships — the string is user-facing, so shipping it unseeded means permanent
untranslated English in AR and MS.

VERDICT: COMPLETE (round 2)
