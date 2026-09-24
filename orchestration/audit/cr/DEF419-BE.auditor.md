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
