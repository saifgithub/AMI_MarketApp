STATUS: READY_FOR_AUDIT (round 1)

<!-- coder-owned lane file for CR058-MATH. State machine driven by the STATUS line above (byte-exact). See orchestration/dispatch/loop_prompts/CODER.md. -->

# CR058-MATH — coder.math lane

**Item:** CR058 — open a CR046 screening module (M13) so the Sharia debt/liquidity/income ratios and purification amount used by CR058's lessons 3 and 5 are computed, never hand-authored: `sharia_debt_ratio`, `sharia_liquidity_ratio`, `sharia_impermissible_income_ratio`, `sharia_screen`, `purification_amount` in `backend/app/trading_math/screening.py`, wired into `__init__.py`'s `__all__`, with guard tests in `backend/tests/unit/test_trading_math_bok.py`.

**Spec:** [`docs/forward_planning/CR058_sharia_compliant_investing/CR058_sharia_compliant_investing.md`](../../../docs/forward_planning/CR058_sharia_compliant_investing/CR058_sharia_compliant_investing.md) §3.1 lessons 3+5, §7, §8.

**Auditor:** auditor.core.
