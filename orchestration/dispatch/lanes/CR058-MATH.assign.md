<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR058-MATH — assign (Sharia screening math)

KIND: code
INSTANCE: coder.math
ACCEPTANCE: docs/forward_planning/CR058_sharia_compliant_investing/CR058_sharia_compliant_investing.md (§3.1 lessons 3+5, §7 CR046 rigor, §8 guards)
DEPENDS-ON: — (CR046 ledger extension; unblocks CR058-CONTENT)
HOT-FILES: backend/app/trading_math/__init__.py (add M13 export group) — coder.math is sole owner
GATE: auditor.core (code lane)

**What:** Open a CR046 **screening module** so CR058's Sharia ratio screens + purification are
**computed, never hand-authored** (§7 — a wrong halal-screen number is worse than none; CR060 accuracy).

**New module `backend/app/trading_math/screening.py`** (CR046 M13; header mirrors `bond.py`). Pure
functions, floats, no I/O:
- `sharia_debt_ratio(interest_bearing_debt, market_cap)` → `debt / market_cap * 100` (percent).
- `sharia_liquidity_ratio(cash_plus_interest_securities, market_cap)` → percent.
- `sharia_impermissible_income_ratio(non_compliant_income, total_revenue)` → percent.
- `sharia_screen(interest_bearing_debt, cash_plus_interest_securities, market_cap, non_compliant_income, total_revenue, debt_max=33.0, liquidity_max=33.0, income_max=5.0)` → a result
  (dataclass or dict) with the three ratios + per-ratio pass bool + overall `passes` bool. Thresholds
  are **parameters** (AAOIFI default 33/33/5) — the content names the standard; the math just checks.
- `purification_amount(non_compliant_income, total_income, dividend_received)` →
  `(non_compliant_income / total_income) * dividend_received`. Guard divide-by-zero (0 revenue/income →
  return None or raise a clear ValueError, matching the module's existing convention).

**Wiring:** add the 6 names to `__init__.py`'s `__all__` under a new `# sharia screening (M13)` group,
alphabetized within the group like the others.

**Guards (§8):** extend `backend/tests/unit/test_trading_math_bok.py` — shown==computed on worked
examples a reviewer can check by hand, e.g. debt 10B / mktcap 100B → 10.0%; income 3 / revenue 100 →
3.0% (passes 5% max); `sharia_screen` overall PASS when all under, FAIL when one over; purification
5B non-compliant / 100B income × $200 dividend → $10.0. Divide-by-zero cases covered.

**Self-test (headless one-shot — FOREGROUND):** `cd backend && uv run pytest tests/unit/test_trading_math_bok.py tests/unit/test_trading_math.py -q` green. Do NOT run the full suite (P7 — the
auditor does that via background+poll).

ASSIGNED: coder.math round 1
DISPATCH: OPEN
