<!--
RETRO-CR221-S13.auditor.md — audit lane verdicts. Auditor-owned; the architect never writes here.
Newest round at the bottom. State derives from round numbers here vs RETRO-CR221-S13.architect.md.
-->

# RETRO-CR221-S13 — auditor verdicts (CR221 slots 1+3+history-arm, CR170/CR171 backend, retroactive)

## Round 1 — auditor u66

**SHA audited:** `34941fa19cdc5bfa1a4739d5ad79386c75583232`, in a detached scratch worktree
`RETRO-S13-u66` per DEF159 — which also closes this submission's first stated limit ("no
scratch-worktree measurement"). Worktree verified clean after every probe was removed.

**Tier B** for the CR221 slots (flag-gated, dark on Alpha). **Tier A** for CR170-BE/CR171-BE —
unconditional, live on every trade today. My effort went where the tier is.

### The architect's own open question, answered

> *"The `fundamentals_fcf_from_statements_enabled` default-flip to `True` ... its originating
> commit not traced — worth the auditor pinning down whether that was a deliberate, reviewed
> decision or an incidental default."*

**Deliberate, reasoned, and authored by Saiful.** `git log -L 916,916:backend/app/core/config.py`
gives the whole history in one command:

- `8b4f189c` (CR221 slot 3) introduced it **`False`**, explicitly "off by default until CR221 §7
  has measured it".
- `83e9c6e6` (DEF399/DEF400, 2026-09-17) flipped it to **`True`**, with the reason stated in the
  commit body:

  > *"DEF400 — the fix landed in 8b4f189c and was always correct; what kept the defect open was
  > that it shipped OFF... It was off for one stated reason, CR221 §7's `cash` arm, and that arm
  > has run. Leaving a measured-correct number behind a default-off flag past its measurement
  > window is the DEF063 dark-feature shape."*

Not incidental. The gating condition was named, it was satisfied, and the flip cites the exact
failure pattern (DEF063) that leaving it off would have become. No finding.

### Tier A — CR170/CR171, attacked rather than re-run

The submission states plainly that it did not adversarially re-derive this math. I did.

**Rule 2 (worse-of-two-prices) — exhaustively verified, no user-favourable edge.** The ask was
to construct a case where the rule picks the better price for the user. I searched the whole
grid instead of guessing at one:

```
PROBE: 168 triggered combinations, none better-for-user than max/min(named, mark)
PROBE: Rule 1 diagonal confirmed for all four order shapes
PROBE: boundary inclusive on both directions
```

Across 2 sides × 3 resting order types × a 7-point price grid, every triggered combination books
at or worse than both the named price and the observed mark. The module's farmability argument
is also correct on its own terms: 15-minute delayed data polled every ~5 minutes means up to 20
minutes of tape has already traded through, so on trigger the mark is *systematically* on the
better-for-user side — filling at it would be directly harvestable by resting a buy limit a
fraction under the market. Filling at the worse of the two removes the edge rather than
bounding it.

`fill_price_for` also takes no `order_type`, deliberately, because the rule does not have one —
avoiding the P10 four-case shape the module exists to close.

**Cash-committed accounting — the fill-time refusal fires; cash never settles negative.** The
lane's own `test_a6_the_snapshot_reports_a_negative_available_when_over_committed` proves the
*reporting* half (and is a good test — it drives the route rather than recomputing the
arithmetic, recording the DEF190 lesson in its own docstring). It stops short of the fill. I
drove that:

```
PROBE setup: committed $12000.00 against $10000.00 cash
PROBE sweep: filled=0 rejected=2 checked=2
PROBE order 6f6b0859 state=rejected reason=None
PROBE order 703da02b state=rejected reason=None
PROBE final current_cash: $10000.00
```

An over-committed book is reachable, both orders are refused at fill, and `current_cash` is
untouched. The refusals are terminal (`_stamp_rejected`), recorded through
`record_compliance_block`, and pushed to the user via `notify_rejected` — "visible, not
vanished", as §6 promises, including on the sweep path where "nobody is watching".

The design reasoning holds too: reserving cash would redefine `current_cash`, which
`total_value`, `total_drawdown_pct`, `portfolio_nav_daily`, the TWR chain and
`_risk_limit_context` all read — a reserved debit would be indistinguishable from a loss in the
NAV series.

**Resting fills re-run the whole floor.** `fill_resting_order` calls `check_mandate_compliance`
with the full context at *fill* time, not placement time, so a 90-day-old order cannot become a
time-delayed bypass of a mandate, drawdown, cooldown or halal change. Explicitly reasoned in
its docstring and correct.

**Short cover / unbounded loss (DEF259) — both halves covered and right.**
`test_a7_the_forced_close_succeeds_with_zero_cash` is the one that matters: a margin close that
could be refused for insufficient cash "is a containment mechanism that fails exactly when it is
needed." And `test_a8` gates the margin close to market hours rather than firing against a stale
overnight print. A short is the one position whose loss is unbounded; both the close path and
its timing are sound.

**DEF262 genuinely fixed.** `safety_floor.py`'s `long_only` is now a real branch (`:303`), not
the bare `pass` the commit describes, and `:293` refuses outright when it cannot distinguish a
sell-to-close from a sell-to-open rather than guessing.

### Tier B — CR221, the "first attack" the submission recommended

> *"`95e7dbec`'s commit message claims 'a loud dark-ingest warning' ... confirm the warning
> actually renders when EDGAR ingest has never run, vs. silently omitting the line."*

**Sound, and already covered — the coverage just lives outside this lane's file list.** Reading
`room_runner.py:895-941`: every unresolved dimensional field is stamped
`LiveDataState.UNAVAILABLE` *before* the dark-ingest probe runs, so the sheet renders a declared
absence, never a wrong number or a silently missing line. The `logger.warn`
(`edgar_dimensional_rows_not_ingested`) is an additional **operator** signal distinguishing
"the ingest never ran" from "this filer tags nothing" — not the user-facing degrade, which is
the `UNAVAILABLE` state.

It is tested, in `test_cr221_d1_d2_revenue_breakdown.py:276-280` (slot D1/D2's file, which is
why this submission did not find it). Green at this SHA: `29 passed`.

**The combined A3 / DEF399 surface — fail-safe in both directions.** The submission asks me to
treat A3 and `_gate_interest_coverage` as one attack surface because a regression in A3's
`resolve_interest_cost` would propagate. I drove the regression directly:

```
PROBE A3=None          -> row left standing (silent, as documented)
PROBE A3=0             -> coverage: 31.8 | state: None      (no false withdrawal, no div-by-zero)
PROBE A3 inflated 100bn-> coverage: None | state: unavailable
PROBE: an A3 regression degrades to ABSENCE, never to a wrong number
```

That is the right direction on every path. The gate's own principle — **withdraw, don't
correct** — is DEF059 applied exactly: rebuilding a quarterly ratio from an annual numerator
would be "an assumption wearing a measurement's clothes", so the honest output is the absence
the sheet already knows how to render. Silence when EDGAR cannot corroborate either way is also
correct: an un-ingested fact store is not evidence the shipped row is wrong.

(My own first probe mis-stated the CAT case — I passed `529` as the quarterly figure when the
commit uses it as the *annualised* one. Recomputed: 1861/529 = 3.52, past the 2.0 limit,
withdrawn, exactly as `83e9c6e6` states. My arithmetic, not theirs.)

### Compose parity

All seven CR221-family flags forwarded, verified at the audited SHA, and the guard itself passes.
CR040's config-parity rule is not violated.

### Evidence, run bare in the pinned worktree

```
pytest test_cr170_order_pricing.py test_cr170_resting_orders.py \
       test_cr171_short_selling.py test_cr171_shorts_on_the_wire.py -q
93 passed in 8.70s            EXIT=0

pytest test_cr221_a1_debt_maturity.py test_cr221_a3_interest_cost.py \
       test_cr221_debt_structure_render.py test_cr221_c3c4_cashflow_bridge.py \
       test_cr221_c2c5_fcf_history.py test_cr221_b2_roe_history.py -q
95 passed in 8.60s            EXIT=0
```

Both match the submission's per-item figures exactly (93; 41+22+32 = 95).

Full backend unit suite, pinned worktree, run bare:

```
pytest tests/unit/ -q -p no:cacheprovider
2 failed, 6738 passed, 9 skipped, 21 warnings in 1144.19s (0:19:04)
EXIT=1
```

**Both failures are unrelated to this lane and already fixed on `main`** — the same two I
diagnosed in CR222-C's audit, which pins this identical SHA:

```
test_p30_registers_name_things_that_exist.py::test_every_file_a_register_row_claims_actually_exists
test_p30_registers_name_things_that_exist.py::test_no_new_register_identifier_is_absent_from_the_codebase
```

DEF416/417/418's row files carried a wrong-depth `../../../` prefix plus one invented
identifier. Fixed by `8e550a57`, which postdates `34941fa1`; those five tests pass green on
current `main`. No file from this lane appears in either failure.

Exit code read from the redirected log, not the harness summary (DEF326/DEF405) — the harness
reported this run as "exit code 0" while pytest's own `$?` was 1.

### Remaining limits, recorded not charged

These are named because they are genuinely unverified, not because they block:

- **No live flag-flip drive.** I did not start a server and toggle the seven CR221 flags. The
  flag-off paths are asserted by compose parity plus the builder's unit tests. Given the flags
  are off on Alpha and the code is dark, the cost of being wrong here is low; I would not spend
  a round on it.
- **`bf6209c1`'s mobile claims** (held pop, disabled CTA) are out of this backend-scoped lane and
  remain unverified anywhere I can see. Worth confirming they are covered by a mobile lane, or
  filing the gap.
- **XOM's 4-vs-5 column balance/income shape (B2)** not re-measured; taken from the commit
  message, as the submission states.

### Verdict

This lane came back strong. Every Tier A surface the submission declined to attack, I attacked,
and each one held: Rule 2 has no user-favourable edge across 168 triggered combinations, the
over-committed book refuses at fill without ever settling negative cash, a resting fill re-runs
the full floor, the forced short close survives zero cash and will not fire on a stale overnight
print, and an A3 regression degrades to a declared absence rather than a wrong number. The one
open question the architect flagged — the `True` default — traces to a deliberate, reasoned,
DEF063-citing decision in one command.

The code is better than the submission claimed for it. Nothing here needs another round.

VERDICT: COMPLETE (round 1)
