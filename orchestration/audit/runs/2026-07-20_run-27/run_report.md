<!--
Auditor run report — run-27 (2026-07-20, session AT:U1). Round-2 audit of CR046
"Agent math ledger" — O1 hardening: risk_tier_cap made total for sparse caps tables.
Audited SHA 0907d8f (backend tree byte-identical at HEAD 80b3925). Verdict COMPLETE
(round 2). Owner: AUDITOR.
-->

# run-27 (round 2) — CR046 O1 hardening (`risk_tier_cap` total for sparse tables) → COMPLETE

- **Auditor session:** AT:U1 (track U), 2026-07-20
- **Audited SHA:** `0907d8f` (the O1 fix commit). `git diff 0907d8f HEAD -- backend/` is
  **empty** — the only commit on top is the architect's own lane-doc update `80b3925`
  (touches `audit/handshake/` only) → the backend tree is byte-identical at HEAD, so I
  ran the suite in place on the main checkout (clean working tree).
- **What round 2 is:** round 1 was audited COMPLETE with two non-blocking OUT-OF-SCOPE
  notes; Saiful asked to fold in **O1**. This round changes **exactly one source function
  + one test** (`git show 0907d8f --stat` → `sizing.py` +8/−4, `test_trading_math.py`
  +10). Nothing else.
- **Backend suite reproduced:** **865 passed** (1 pre-existing unrelated FastAPI HTTP_422
  deprecation warning in `test_sim_history.py`). = round-1's 861 + the intervening
  DEF069–073 / CR047-device dev + the 1 new sparse-table test.
- **Verdict:** COMPLETE — zero BLOCKER / zero MAJOR. O1 resolved; O2 (cosmetic float
  narration) left as a deliberate no-op by design.

---

## The one thing that mattered: did the rewrite move any enforced number?

`risk_tier_cap` is the exact function my round-1 verdict certified as reproducing the
pre-CR046 enforced ceiling "at every tier **and** out-of-band." Round 2 rewrote its OOB
branch, so the whole round-2 audit reduces to re-proving that certification against the
new code — independently, not trusting the architect's "behaviour unchanged" claim.

**The diff:**

```
-    key = min(max(int(risk_score), min(table)), max(table))
-    return table[key]
+    score = int(risk_score)
+    if score in table:
+        return table[score]
+    return table[min(table, key=lambda k: (abs(k - score), k))]
```

**Why it's safe — proven, not trusted:** the rewrite **keeps `int(risk_score)`** (float
truncation preserved), and for a *contiguous* key table the nearest-present-key is
identical to the range-clamp for every integer score. So the default table `{1..5}` can't
diverge. Verified with my own probe over `[-3,0,1,2,3,4,5,6,7,100,3.9,4.9,2.5,-100,4.0]`:

| Comparison | Divergences |
|---|---|
| round-2 `risk_tier_cap(default)` vs the **round-1** impl | **ZERO** |
| round-2 `risk_tier_cap(default)` vs the **pre-CR046** `_risk_tier_size_ceiling` (`4.5 if ≥4 else 1.5 if ≤2 else 3.0`) | **ZERO** |
| `_risk_tier_size_ceiling(1..5)` still `[1.5,1.5,3.0,4.5,4.5]` | **ZERO** |
| coherence guard `told == enforced ≤ 50` at every tier (`_max_position_pct` == `_risk_tier_size_ceiling`) | holds |

The M03 shown==enforced invariant survives the rewrite; no enforced clamp or narrated cap
changed.

## O1 actually resolved (the point of round 2)

| Check | Result |
|---|---|
| Sparse `{1:5,5:25}` totality | No raise across scores **−5..11**; `score=3` (equidistant) → `5.0` (ties round **down** to tier 1); `score=4` → `25.0` (nearest present key 5); `score=9` → `25.0`. |
| Single-key table `{3:9}` | Total — every score → `9.0`. |
| Empty table `{}` | Documented `ValueError` ("min() iterable argument is empty") — an honest caller error, **not** a silent wrong answer. Round-1 default would also have raised on empty, so no regression. |
| Docstring | Round-1 imprecision ("clamps to the nearest tier") now accurate: "snaps to the nearest key present (ties round down to the lower tier)." |
| New test bites | `test_risk_tier_cap_total_for_sparse_custom_tables` would **KeyError** against the round-1 range-clamp on `{1:5,5:25}`+score 3 → a genuine guard for the hardening (house rule). |

## Zero in-tree exposure (unchanged from round 1)

Both app callers use the default contiguous table:

```
app/agents/overlay_generator.py:397:    return risk_tier_cap(risk_score)
app/services/room_runner.py:422:        return risk_tier_cap(risk_score)
```

Neither passes `caps=`; grep confirms no app call site passes a custom table. The sparse
path is exercised only by the library's own test. O1 was always future-reuse hardening for
the library's stated copy-portable goal, never a live bug — consistent with why it was
OUT-OF-SCOPE (not a DEF) in round 1.

## Scope & governance

| Dimension | Result |
|---|---|
| Diff size | 2 files (`sizing.py` one function + `test_trading_math.py` one test). No collateral. |
| Coherence guard test | `test_position_sizing.py` **untouched** by round 2 (last touched `124f15f`) → the M03 shown==enforced guard is preserved verbatim. |
| Register | `cr_list.md` CR046 stays **`standing`** — correct; a totality hardening is not a status change. |
| Failure patterns | No new class needed — a totality hardening of an existing calc already sits under **P5**. |
| Promotion | Not promoted; architect is batching one Alpha promote with other in-flight dev (Saiful's call). Zero enforced-behaviour delta, so not load-bearing for correctness. |

## Definition-of-Done disposition (round 2)

| Architect row | Auditor disposition |
|---|---|
| Scope (fold in O1: one function + one test) | OK — verified: 2 files, no scope creep. |
| Tests (865; +1 sparse-table) | **Reproduced** (865) + independently re-derived the no-regression proof + confirmed the new test is non-vacuous. |
| Behaviour unchanged for default table + every prior test | **Independently proven** — round-2 == round-1 == pre-CR046 ceiling, zero divergences incl. floats. |
| O2 left as-is (cosmetic) | Concur — honest float rendering, no action. |
| Commit tag `(AT:R62 CR046)` on `0907d8f` | OK. |

---

## Verdicts

| Item | SHA | Verdict |
|---|---|---|
| CR046 | `0907d8f` | **COMPLETE (round 2)** — O1 hardening (`risk_tier_cap` total for sparse `caps` tables) folds in the round-1 observation. The one rewritten function moves **no enforced number**: round-2 `risk_tier_cap(default)` is byte-behaviour-identical to both the round-1 impl and the pre-CR046 enforced ceiling at every probe incl. floats (zero divergences — `int()` retained, nearest-key ≡ range-clamp for contiguous tables); coherence guard `told==enforced≤50` still holds `[1.5,1.5,3.0,4.5,4.5]`. Sparse totality achieved (no raise −5..11, ties round down, nearest key; empty table → documented `ValueError`); new test bites (round-1 range-clamp KeyErrors on the sparse case). Zero in-tree exposure (both callers use the default table). Scope 2 files; coherence-guard test untouched; register `standing`; suite **865 passed** reproduced. O2 cosmetic left as a deliberate no-op. |

OUT-OF-SCOPE: none new. O1 (round 1) now RESOLVED in-code; O2 (float narration cosmetic) knowingly deferred by design.
