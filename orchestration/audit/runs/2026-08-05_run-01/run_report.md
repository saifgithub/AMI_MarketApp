# Audit run 2026-08-05 run-01 — CR136-M11, round 1

Auditor track U. First audit of M11 — the verification/promotion lane, whose
deliverable is the ship runbook and the live cross-check harness.

Audited at **`c56e2c41`** in detached worktree `.claude/worktrees/audit-m11r1`.

Verdict: **AWAITING_FIXES (round 1)** — zero BLOCKER, **1 MAJOR**, 4 non-gating
MINOR. Findings in `orchestration/audit/cr/CR136-M11.auditor.md`.

## The submission invited a bounce. The queue delay is why it does not get one

§1 offers to have the lane returned as misallocated effort, on the grounds the
harness "has never run at all". Between submission and this audit, **track R ran
it on Alpha** (`8c7a0cb4`, 2026-08-05): `EXIT=0 — 9 metrics checked, 0 FAILED`,
book `8f1e288a…`, 500 returns, sleeve SCHD/HPQ/DIS/BAC. The script is
byte-identical `c56e2c41` → `main`, so the artefact that certified the live
engine is the artefact under audit.

## MAJOR A1 — PASS and exit 0 on a strict subset

§3.4.2 confirmed by driving `main()` with `_load_closes` and `_fetch_health`
stubbed:

```text
control: honest payload             exit=0  checked: 7  FAILED: 0   PASS
benchmark unusable                  exit=0  checked: 4  FAILED: 0   PASS
r_squared renamed -> rsq            exit=0  not checked: ['r_squared']  PASS
control: sigma_p 0.1pp wrong        exit=1  FAILED: 1
```

Checklist 2.9's acceptance is literally *"exits 0"*, and the exit code cannot
distinguish seven-of-seven from four-of-seven. The `checked:` line is printed —
it is prose, and CR038's rule is that prose is not a control.

**Corrected the submission's own mechanism.** §3.4.2 blames
`INSUFFICIENT_BENCHMARK_MISALIGNED`; two of that cause's three states
self-correct into `exit 2` (missing benchmark → the `missing` check; short joint
→ the window check). The reachable route is `bench_clean` false — a bad print in
stored SPY — where the engine drops the benchmark but keeps the same window. The
key-rename route needs no unusual book at all.

## MINOR m1 — untested, not untestable

`grep -rln "cr136_live_crosscheck" backend/tests/` → nothing. M11 §5 claims
"acceptance greps enforce"; there is no such grep anywhere.

Graded MINOR because I measured what the prose stands in for and it holds:

```text
app.trading_math* in sys.modules after importing the harness : NONE
max |cov diff| vs app.trading_math, 4x300 : 2.711e-20   relative 3.676e-15
sigma_ann harness / engine                : identical to 12 dp
```

That reproduces the builder's calibration claim, which §3.3 flagged as
unreproduced. §4 says the deliverable "has no test that can be made to fail".
My probe is ~40 lines, two stubs and a `main()` call — and it found A1 on first
contact. That is the argument for the finding.

## MINOR m2 — the join-order docstring is inverted

Harness trims per-ticker first then intersects; engine intersects full sets then
trims once. The docstring asserts the opposite and explains why the opposite
would be wrong.

```text
A: 780 weekdays, B: every other weekday, same span
engine  _join   -> 389 returns   [2023-08-07..2026-07-30]
harness _joined -> 251 returns   [2024-08-27..2026-07-30]   -> exit 2
```

35% of the window, and the exit-2 message sends the operator to "investigate
M01's join". Not graded higher: the harness's intersection is a subset of the
engine's by construction, so the count is always ≤ and the window check fires
before any number is compared. I could not construct the worse corner (equal
counts, different dates, spurious `exit 1` blaming the engine).

## MINOR m3 — the fixed flake's coupling is unpinned

```text
AUD-1  journal_store.py  `>= day_start` -> `>`
       M11 suite    82 passed   SURVIVED
       full suite  2269 passed  SURVIVED
```

`test_cr136_health_gate.py`'s `max(now + offset, day_start)` is correct only
because the production comparison is inclusive; nothing holds them together.

## MINOR m4 — the tolerance is right for the render, a size small for §1.1's claim

`_TOL = 0.005` is absolute and at most half a rendered ULP for every metric the
card shows (vol 1 dp, beta 2 dp, R² 0-dp percent, effective bets 1 dp, shares
0-dp percent; TE is not rendered in `mobile/` at all). Against the numbers the
gate actually recorded:

```text
portfolio_volatility (pp)   2.7571    ±0.005 =  0.18%
beta                        0.0415    ±0.005 = 12.05%
r_squared                   0.0487    ±0.005 = 10.27%
tracking_error (pp)        14.3196    ±0.005 =  0.03%
effective_bets              1.9023    ±0.005 =  0.26%
```

β and R² were certified to ±12% and ±10%, because the chosen book carried 87.2%
cash. The runbook's selection criteria pin holdings and history length and say
nothing about cash weight.

## Reproduced

| Check | Submission | Auditor | Result |
|---|---|---|---|
| M11 suite (82) | 82 | **82 passed, 3.16s** | exact |
| full `tests/unit/` | 2269 | **2269 passed, 285.49s** | exact |
| QA-A / QA-B / QA-C | 2 / 2 / 1 failed | **2 / 2 / 1, names match** | exact |
| `--verify-scenarios` live Yahoo | −34.10 / 0.20pp, −25.36 / 0.04pp | **identical, exit 0** | exact |

2269 corroborates M01's and M07's round-1 audits of the same tree. §3.3 declined
to re-run the scenario check; I ran it and it holds.

## Checked and accepted

§3.4.6's `real_mode` mirror (all three derivations are the same expression).
§2.2's weights identity (exact, including the cash row). The EWMA estimator
matches in *form* — both demean, neither takes a dof correction — so the ≈0.003pp
mismatch a demeaning difference would produce, invisible at this tolerance, is
not present. §2.4's DEF211 degradation (HTTPError → exit 2). §2.5's three doc
claims, all re-measured; the i18n reading is worse than disclosed in the same
honest direction — 40/40 AR **and** 40/40 MS `portfolioHealth*` values are the EN
string verbatim.

§3.4.4 confirmed and already remediated on `main` by track R (Phase 0
re-measured at `afb1d6d8`, gate 1.4 closed). Surviving bookkeeping: checklist
1.1 still says 26 fleet scripts; there are 27 at the submitted SHA and 31 at
`main`.

## Probes preserved

`m11_probe1.py`, `m11_probe2.py`, `m11_mut.sh`.
