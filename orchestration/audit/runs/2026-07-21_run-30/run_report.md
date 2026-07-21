<!--
Auditor run report — run-30 (2026-07-21, session AT:U1). Round-1 audit of CR054-W0d
"open the CR046 BOK math entries M09-M12" (coder.math-delegated lane under CR052 dispatch).
Audited SHA b6c42b7 (backend tree byte-identical at HEAD 7a5c451). Verdict COMPLETE.
Owner: AUDITOR.
-->

# run-30 (round 1) — CR054-W0d "BOK math entries M09–M12: bond / option / portfolio / return metrics" → COMPLETE

- **Auditor session:** AT:U1 (track U), 2026-07-21. Second lane under the CR052 dispatch model
  (delegated track-R → `coder.math`).
- **Audited SHA:** `b6c42b7` (source). `git diff b6c42b7 HEAD -- backend/` is **empty** — only the
  orchestration lane-open `abfb561` sits on top → backend byte-identical at HEAD `7a5c451`, ran the
  suite in place (clean tree, only `Archive.zip` untracked).
- **The item:** open the CR046 math entries the BOK's Wave-1 worked examples route through (CR054
  §4.5 "numbers computed, never authored"): bond price/YTM/duration (M09), option payoff/break-even
  (M10), portfolio variance/covariance/correlation/beta (M11), CAGR/max-drawdown/Sharpe (M12). Pure
  functions in `backend/app/trading_math/`, +28 guard tests, +4 M-ledger entries. **No consumer
  wiring — staging ahead of Wave-1 authoring, by design.**
- **Backend suite reproduced:** **926 passed**, 1 pre-existing unrelated warning
  (`HTTP_422_UNPROCESSABLE_ENTITY` deprecation, `test_sim_history.py`), 136.74s.
- **Verdict:** COMPLETE — zero BLOCKER / zero MAJOR / zero MINOR. No OUT-OF-SCOPE.

---

## What changed

`b6c42b7` — 11 files, **+878 / −9** (`git show --stat`; the 9 deletions are all docstring/backlog
prose rewrites, zero deletions in any logic file). 4 new modules + `__init__` exports + 1 guard
file + 4 ledger docs + master-ledger rows.

## Why it's correct — verified, not trusted

**The riskiest dimension is formula correctness. Every pinned value was independently recomputed by
a different method than the module (direct discounted-cashflow sums; independent bisection solve;
numpy for the statistics), then required to agree 3-way: module == my reference == test literal.**

| Pinned value | Independent method | module == ref == literal |
|---|---|---|
| bond_price 5%/6%YTM/10y semi = **925.61** | brute-force Σ discounted CFs (module uses closed-form annuity) | ✓ |
| zero-coupon = **553.68**, par identity = **1000** | 1000/1.03²⁰; DCF | ✓ |
| bond_ytm(925.61)→**6.0**, (1000)→**5.0** | my own bisection on my DCF price fn | ✓ |
| macaulay 3y/5%/par = **2.86**; zero-cpn = **10.0** (=maturity) | independent PV-weighted-time Σ | ✓ |
| modified = **2.72** (= mac/1.05) | independent | ✓ |
| option payoffs/break-evens (call/put, ITM/max-loss, bankruptcy put) | closed forms | ✓ |
| variance **4.0** / covariance **2.0** / correlation **±1.0** / beta **2.0** | **numpy** (ddof=1, corrcoef) | ✓ |
| portfolio_variance 60/40 = **0.01888** | **numpy** wᵀΣw + spelled-out MPT formula (ρ0.3·σ0.2·σ0.1 = cov 0.006) | ✓ |
| cagr **7.18** (doubling) / **−6.7** (loss) | (2)^0.1−1 etc. | ✓ |
| max_drawdown **50.0** (peak140→trough70) | independent running-peak | ✓ |
| sharpe **22.45** / **1.41** (no annual) / **11.22** (rf) | independent mean/sample-sd/√252 | ✓ |

| Other dimension | Result |
|---|---|
| **Degrade-loudly None-guards** (adversarial probe) | 9/9 nonsense inputs → **None**, never a silent number: fractional bond periods, yield ≤ −100%, unattainable YTM price, unknown option kind, negative underlying, asymmetric cov matrix, non-PSD (negative variance), flat-series Sharpe, flat-series correlation. |
| **No new dependency** | `pyproject.toml`/`uv.lock` **absent** from the diff. D1's `empyrical-reloaded` deferred; the 3 needed metrics hand-rolled stdlib-only (Sortino/Calmar/vol stay on the D1 backlog). |
| **Library purity** | imports in the 4 modules = `__future__`, `collections.abc.Sequence`, `math.sqrt`, relative `.portfolio_stats` only. **No `app` imports** → copy-portable, no cycle. |
| **Dead-code-by-design disclosure holds** | 15 functions exported in `__init__.py`; **zero app callers** — no `from app.trading_math import` in app code, no bare call to any new fn. The `max_drawdown_pct` grep hits are the pre-existing **mandate field** (`Literal[10,20,30,50,100]`), a name collision, not the new function. Wave-1 authoring is the disclosed consumer. |
| **Guard tests non-vacuous** | Exact-value asserts (`== 925.61`, `== 2.86`, …) pinned to the true textbook values (proven above) — a formula mutation breaks an exact figure, not an approx band. `test_trading_math_bok.py` 28 tests; run with the existing library file → **59 passed**. |
| `pytest tests/unit/` | **926 passed**, 1 pre-existing warning, 136.74s. Reproduced at HEAD. |

## Scope & governance

| Dimension | Result |
|---|---|
| Diff size | 11 files, +878/−9. All owned paths: `trading_math/**` (4 modules + `__init__`), `test_trading_math_bok.py` (matches the `test_trading_math*.py` glob), CR046 ledger (4 M-entries + master). |
| Ledger M09–M12 | Present; each carries the house-format sections (formula / source / consumed-by / computed-in / guard-test / changelog). |
| room_runner/W0c WIP / Archive.zip / settings | Architect OUT-OF-SCOPE note: shared tree held W0c WIP + `Archive.zip` + `.claude/settings.local.json` at commit time. **Not swept in** — `git show --stat` = only the 11 owned files. Confirmed. |
| Commit tag `(AT:coder.math CR054)` | Sanctioned by `DISPATCH_PROTOCOL.md:41` (`(<TAG_PREFIX>:<instance-id> <ITEM>)`). |

## Auditor pin

None added. The 28 in-suite guards pin exact textbook values (independently confirmed true) plus
every None-guard; a redundant `orchestration/audit/regression/` pin would be noise.

## NEEDS-DEVICE-CHECK / live

- None load-bearing. Pure additive library, **zero app callers by design** → no live path exercises
  it and no Alpha behaviour changes until a Wave-1 lesson lane wires it. Not promoted.

## Definition-of-Done disposition

| Architect row | Auditor disposition |
|---|---|
| Scope (owned paths only) | OK — `git show --stat` = 11 owned files. |
| Bond / Option / Portfolio / Return math (M09–M12) | **Reproduced** — every pinned value 3-way independently recomputed. |
| No new dependency (D1 narrowed) | OK — `pyproject`/`uv.lock` untouched; stdlib-only hand-roll. |
| Guard test each (+28, red-proof) | **Reproduced** — 59 passed (28 new); exact-value pins, None-guards verified. |
| M-ledger entry each | OK — M09–M12 present, house format. |
| Full suite green (926) | **Reproduced** — 926 passed, 1 pre-existing warning. |
| Library contract (pure, stdlib, no app imports) | OK — grep-verified. |
| Consumer wiring (none, by design) | OK — zero app callers confirmed (name-collision ruled out). |
| Commit `b6c42b7`, owned paths, tag | OK — sanctioned tag; 11 files. |

---

## Verdicts

| Item | SHA | Verdict |
|---|---|---|
| CR054-W0d | `b6c42b7` | **COMPLETE (round 1)** — 4 pure-math modules (M09 bond price/YTM/duration, M10 option payoff/break-even, M11 portfolio variance/covariance/correlation/beta, M12 CAGR/max-drawdown/Sharpe) + 28 guard tests + M09–M12 ledger. **Every pinned textbook value recomputed independently (DCF sums / own bisection / numpy) and agrees 3-way** (module == my ref == literal): bond 925.61 / zero-cpn 553.68 / par 1000; YTM round-trips 6.0 & 5.0; Macaulay 2.86 & 10.0 (=maturity) / modified 2.72; option payoffs & break-evens; variance 4.0 / cov 2.0 / corr ±1 / beta 2.0 / portfolio-var 0.01888 (numpy + spelled MPT formula); CAGR 7.18 & −6.7; MDD 50.0; Sharpe 22.45/1.41/11.22. All 9 degrade-loudly None-guards reject nonsense to None (no silent wrong number). No new dependency (`pyproject`/`uv.lock` untouched; D1 narrowed, empyrical deferred). Library pure (no `app` imports, copy-portable). Dead-code-by-design disclosure holds — 15 fns exported, **zero app callers** (the `max_drawdown_pct` grep hits are the pre-existing mandate field, a name collision). Suite **926 passed** reproduced (1 pre-existing HTTP_422 warning); guard file 59 passed. Scope 11 owned files; ledger M09–M12 house-format; tag `(AT:coder.math CR054)` sanctioned. No live path (staging ahead of Wave-1) → not promoted, no device check load-bearing. |

OUT-OF-SCOPE: none.
