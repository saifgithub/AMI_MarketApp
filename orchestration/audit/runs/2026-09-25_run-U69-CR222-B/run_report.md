# Run report — CR222-B round 1 (U69, 2026-09-25)

**Item:** CR222 slice B — passive twin, Portfolio Health §F3. **Tier B.**
**SHA audited:** `e0a9cc57dd04c46e4a71aae1db1dd13680d78316` (branch
`worktree-agent-ac5f62fc688f4b8ff`, off `main`; detached worktree
`.claude/worktrees/audit-CR222/`).
**Verdict:** COMPLETE (round 1) — zero BLOCKER, zero MAJOR, zero MINOR.

## Commands run (all from the worktree, repo `.venv` absolute interpreter)

- Targeted: `test_cr222_passive_twin.py test_cr222_behaviour_diagnostics.py
  test_cr222_training_toll.py test_cr222_preregistration.py test_config_compose_parity.py
  test_def200_ratchet.py test_no_blocking_io_in_async_routes.py` → **128 passed,
  1 skipped in 17.48s** — matches the submission.
- CR136/CR131: `test_cr136_finding_renderer.py test_cr136_finding_validator.py
  test_cr136_rule_engine.py test_cr131_day_trader_outcomes.py
  test_cr131_cohort_marker_coupling_pin.py` → **133 passed in 12.97s** — matches.
- **Full unit suite at the SHA: `7057 passed, 9 skipped in 1305.91s`** — green.

## Auditor's own probes (script: /tmp/audit_cr222b_probe.py, this session)

- **Independent IRR (from-scratch safeguarded Newton + own NPV, no module import of
  `irr`):** 4 schedules (the case-(a) shape, a doubling, a 50% loss, three deposits) match
  the module's `irr()` to ≤1e-6 relative; NPV at the module's roots ≈ 0 under the
  auditor's own NPV (≤1.8e-11). Degenerate shapes (no sign change / single flow / same-day)
  all return `None`.
- **Independent TWR:** 5-point NAV series with a restart — module's chain-link matches the
  auditor's hand split-at-event computation to the last bit (0.07100000000000017);
  the no-split figure (1.1) correctly not produced.
- **Halal matrix:** unconfigured halal (dict and object mandate shapes, truthy string/int
  markers) → `None`, never SPY, warning logged; configured `spus ` → `SPUS`; non-halal and
  no-mandate → SPY default. Structural claim (no fallthrough from the halal arm) verified
  at `passive_twin.py:257-280`.
- **Degrade-loudly:** one missing close → `twin_history` with all six numeric fields
  `None`; no capital event → `twin_no_capital`; short window → `twin_short_window`; flag
  off → `None` (absent block).
- **Toll-off byte-identity:** `cost_treatment` key absent with `training_toll_enabled`
  False.
- **Fixed-prose sweep (the round's bug class):** every numeric literal in every
  fixed-prose sentence of `_f3_passive_twin`/`_f3_toll`/`_f3_behaviour` resolves against
  `VALIDATOR_FIXED_RAW` ∪ `VALIDATOR_FIXED_PCT` via the validator's own Decimal-normalized
  membership (`portfolio_finding.py:1092-1097`). Without the round's "5" addition the
  attention sentence's "5" has no other source — the fix is load-bearing.

## Code read (file:line)

`passive_twin.py` whole file (511 lines); `_f3_passive_twin` `portfolio_finding.py:559-628`;
twin allow-list :949-976; render order :866-872; endpoint `api/portfolio.py:233-263`;
config :984-1017; compose :480-484. Mobile no-change confirmed by grep (`mobile/lib`: zero
hits for `passive_twin`/`behaviour` outside generated l10n) and by the generic §F1–F5
markdown renderer.

## Findings

None.
