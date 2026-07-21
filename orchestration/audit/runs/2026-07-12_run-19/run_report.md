<!--
Auditor run report — run-19 (2026-07-12, session AT:U1). Round-2 re-audit of DEF052
(Market Analyst real technicals) after the architect fixed F1 (NaN close raises).
Fixed in 762455b. Verdict: COMPLETE. Owner: AUDITOR.
-->

# run-19 (round 2) — DEF052 F1 fix re-audit → COMPLETE

- **Auditor session:** AT:U1 (track U), 2026-07-12
- **Audited SHA:** `762455b` (`fix(agents): technicals.py must never raise on a NaN
  close`). Full suite verified at a **clean isolated worktree** at that SHA — the shared
  main checkout carried the architect's *uncommitted* fundamentals WIP (a `_num`
  NaN-guard, addressing my round-1/DEF053 out-of-scope observation), not part of DEF052.
- **Verdict:** COMPLETE — F1 fixed, independently re-verified.

---

## F1 fix — verified

**Round-1 F1 (MAJOR):** `compute_technicals` wrapped only `history()`, so a NaN close
(yfinance's missing-value sentinel) made `round(rsi)` raise `ValueError`, propagating
past the `if technicals:` guard and `run()`'s own try (which opens after the profile
is built) to `_pump()` → error event, no verdict → the whole Room Convene failed.

**The fix (`f367e26` → `762455b`):**
- The entire computation moved **inside** the existing `try/except Exception: return None`
  — any raise now degrades to `None`.
- Plus an explicit guard before any math:
  `if not all(math.isfinite(v) for v in (*closes,*highs,*lows,*volumes)): return None` —
  which also closes the NaN-*low* silent-wrong-support edge I noted (min() skips NaN and
  returned a wrong support without raising).
- Log key `technicals_history_error` → `technicals_compute_error` (scope now the whole body).

This is exactly the minimal remedy I proposed (wrap the body like the sibling modules),
belt-and-suspendered with the isfinite guard.

**Independent re-verification (my own probes, main checkout — `technicals.py` is not
among the architect's dirty files, so it reflects committed `762455b`):**
- My exact round-1 repro (60 clean candles + 1 NaN close) → now returns **`None`** (was
  `ValueError`). F1 closed.
- NaN volume → `None`. NaN low → `None` (was a silent wrong `support`).
- Clean OHLCV → still computes a real `Technicals` (rsi/trend/volume/support/breakout) —
  no regression.
- `test_technicals.py` → 16 passed (13 original + 3 new: `test_none_when_a_close_is_nan`,
  `_volume_is_nan`, `_low_is_nan`). The architect's revert-check (all 3 fail pre-fix) is
  consistent with my round-1 reproduction.

**Full suite:** **712 passed** at a clean isolated `762455b` worktree (matches the
claim). Note: the first full-suite run on the shared main checkout showed `1 failed,
712 passed` — the failure was `test_fetch_treats_nan_numeric_fields_as_absent`, part of
the architect's **uncommitted** fundamentals `_num` WIP on the shared tree, NOT a DEF052
regression. Re-running in isolation removed it. (This is why the auditor uses isolated
worktrees when the shared tree is dirty.)

## Round-1 out-of-scope observation — being addressed

The pre-existing `_num` NaN-round crash in `fetch_live_fundamentals` (flagged in both
run-17 and the DEF053 run-18 report) is exactly what the architect's in-flight
fundamentals work (the uncommitted `test_fetch_treats_nan_numeric_fields_as_absent` +
`_num` change) is closing. Tracked there; not part of this lane.

---

## Verdicts

| Item | SHA | Verdict |
|---|---|---|
| DEF052 | `762455b` | **COMPLETE (round 2)** — F1 fixed (whole computation inside try/except + `math.isfinite` guard); my exact repro now returns `None`, no regression, 712 clean at an isolated worktree. |

No new findings.
