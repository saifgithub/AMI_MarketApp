SUBMITTED: round 1

<!--
CR058-MATH.architect.md — coder-owned audit lane (delegated from track R architect to coder.math under CR052 dispatch). Opened AT:coder.math CR058. State derives from round numbers here vs CR058-MATH.auditor.md (see orchestration/audit/PROTOCOL.md).
-->

# CR058-MATH — audit lane (coder.math)

**Item:** CR058 — open a CR046 screening module (M13) so CR058's Sharia ratio screens + purification (§3.1 lessons 3+5) are computed, never hand-authored (§7 rigor, §8 guards). Spec: [`docs/forward_planning/CR058_sharia_compliant_investing/CR058_sharia_compliant_investing.md`](../../../docs/forward_planning/CR058_sharia_compliant_investing/CR058_sharia_compliant_investing.md) §3.1, §7, §8.

**depends-on:** none (CR046 ledger extension; unblocks CR058-CONTENT).

**Head SHA:** `21fb8b6` (source; pushed — `origin/main` at `21fb8b6f84e05cd97d16023b93a373d327080cc2`).

## What was done

1 new module + package wiring + guard tests. 4 files, 234 insertions, 3 deletions (deletions all in the `__init__.py` docstring/`__all__` edits — zero deletions in any logic file).

1. **`backend/app/trading_math/screening.py`** (M13) — `sharia_debt_ratio`, `sharia_liquidity_ratio`, `sharia_impermissible_income_ratio` (each `numerator / denominator × 100`, 1 dp, None on non-positive denominator); `sharia_screen` (all three ratios + a per-ratio pass bool + overall `passes`, returned as a `ShariaScreenResult` NamedTuple — mirrors `TradeAsymmetry`/`DrawdownContribution`'s existing compound-result convention; thresholds are parameters, default AAOIFI 33/33/5); `purification_amount` (`non_compliant_income / total_income × dividend_received`, 2 dp, None on non-positive total income).
2. **`backend/app/trading_math/__init__.py`** — imports + 6 new `__all__` entries under a new `# sharia screening (M13)` group, alphabetized within the group like its neighbours; scope docstring paragraph updated to name the new module.
3. **`backend/tests/unit/test_trading_math_bok.py`** — 12 new tests: hand-checkable textbook values (debt 10B/100B → 10.0%, liquidity 20B/100B → 20.0%, income 3/100 → 3.0%), `sharia_screen` all-under → `passes=True`, one ratio over (debt 40B/100B = 40% > 33% default cap) → `passes=False`, purification 5B/100B × $200 → $10.0, and the divide-by-zero/negative-denominator path for every function (ratios, screen, purification).

## Why this is safe / minimal

- **Purely additive to a pure library.** No existing `trading_math` function, signature, or return convention changed; every other module untouched.
- **Convention match:** guard style (None on non-positive denominator) matches `bond.py`/`valuation.py`/`option.py`; compound-result NamedTuple matches `trade.py`'s `TradeAsymmetry` and `risk.py`'s `DrawdownContribution`; rounding at 1 dp for the ratios (percent figures, same tier as `valuation.py`'s `fcf_yield_pct`) and 2 dp for the dollar purification amount (matches `option.py`/`bond.py` price-tier rounding).
- **Degrade loudly (CR040):** a non-positive market cap / total revenue / total income never silently divides — every path returns None so the caller states no figure rather than a wrong one (the exact CR058 §7 concern: "a wrong halal-screen number is worse than none").
- **Library contract held:** pure functions over primitives, no I/O/config/logging, no imports from the rest of `app`, copy-portable.
- **AMI naming / user copy:** none — code + internal tests only.

## Tests run (self-test)

- **`cd backend && uv run pytest tests/unit/test_trading_math_bok.py tests/unit/test_trading_math.py -q`** → **68 passed** (12 new + 56 pre-existing). Ran in the foreground per headless one-shot discipline; full 828s suite deliberately NOT run here (P7 — auditor's job).
- **Red-proof, by construction:** every ratio asserted against an independently hand-computable value (10B/100B=10%, 20B/100B=20%, 3/100=3%); the screen's fail case picks a ratio (40%) that's over its own default cap (33%) so a threshold-comparison-direction bug (`>=` vs `<=`, or an inverted pass/fail) breaks the assert; purification's 5B/100B×$200=$10 is arithmetic a reviewer redoes in one line. Every None-guard (zero and negative denominator) has a dedicated rejection assert per function.

## Definition of Done

| Row | Disposition |
|---|---|
| **Scope** | Owned paths only: `backend/app/trading_math/screening.py` (new), `backend/app/trading_math/__init__.py`, `backend/tests/unit/test_trading_math_bok.py`, `orchestration/dispatch/lanes/CR058-MATH.coder.math.md`. Nothing else in the diff — `uv.lock`/`settings.local.json`/`Archive.zip` not staged. |
| **`sharia_debt_ratio` / `sharia_liquidity_ratio` / `sharia_impermissible_income_ratio`** | Each `x/denominator×100`, 1 dp, None on non-positive denominator. |
| **`sharia_screen`** | Three ratios + per-ratio pass + overall `passes`, `ShariaScreenResult` NamedTuple, thresholds as parameters (AAOIFI defaults 33/33/5). |
| **`purification_amount`** | `(non_compliant_income/total_income)×dividend_received`, 2 dp, None on non-positive total income. |
| **`__init__.py` wiring** | 6 names imported + added to `__all__` under a new `# sharia screening (M13)` comment group, alphabetized within the group. |
| **Guard tests** | 12 tests in `test_trading_math_bok.py` — worked examples + divide-by-zero/negative-denominator path for every function. |
| **Targeted suite green** | 68 passed (`test_trading_math_bok.py` + `test_trading_math.py`). |
| **Library contract** | Pure, stdlib-only, no `app` imports, copy-portable, existing modules untouched. |
| **Commit** | `21fb8b6` — `feat(trading-math): CR046 M13 Sharia screening ratios + purification (AT:coder.math CR058)`. Owned paths staged by name; pushed to `origin/main`. |
