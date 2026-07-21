<!--
Auditor run report — run-26 (2026-07-20, session AT:U1). Round-1 audit of CR046
"Agent math ledger" (STANDING CR) + M03 position-size incoherence fix. Audited SHA
124f15f (ancestor of HEAD 2cbeaf0; CR046 tree byte-identical at HEAD). Verdict
COMPLETE. Owner: AUDITOR.
-->

# run-26 (round 1) — CR046 "Agent math ledger" + M03 position-size reconciliation → COMPLETE

- **Auditor session:** AT:U1 (track U), 2026-07-20
- **Audited SHA:** `124f15f` (the CR046 feature commit). Linear **ancestor** of
  `HEAD == origin/main == 2cbeaf0`. The commits in between (`67dcbe3` CR047, my CR047
  verdict `6498d76`, `e3275c9` docs, `2cbeaf0` CR046 lane-open) touch **disjoint** files;
  `git diff 124f15f HEAD --` over all CR046 source+test files is **empty** → the CR046 tree
  is byte-identical at HEAD, so I ran the suite in place on the main checkout (clean tree).
- **Backend suite reproduced:** **861 passed** (1 pre-existing FastAPI HTTP_422 deprecation
  warning in `test_sim_history.py`, unrelated). This is the architect's `854` at `124f15f`
  plus the `7` CR047 tests that landed on top — consistent.
- **Independent red-proof (my own script, not the CR046 tests):** the M03 coherence guard
  bites **5/5** tiers against the pre-fix `{1:5,2:10,3:15,4:25,5:40}` narration; post-fix
  `told == enforced ≤ backstop` at every tier.
- **Verdict:** COMPLETE — zero BLOCKER / zero MAJOR. One informational OUT-OF-SCOPE note
  (zero-exposure `risk_tier_cap` sparse-table totality) + one cosmetic aside. Live-Alpha
  render legitimately deferred (not promoted; no enforced-behaviour delta).

---

## What CR046 does

Stands up a **standing (always-open) CR** whose charter is a single policy: *any number an
AMI agent presents as fact that can be computed deterministically is computed in Python — in
the new portable `backend/app/trading_math/` library — and injected as a finished figure; the
LLM never does the arithmetic.* The first filing seeds the ledger (M01 indicators, M02
drawdown, M03 sizing, M04 fundamentals, M05 portfolio — the last two are spec-only backlog)
and executes **M03**: three modules answered "how big a position?" three inconsistent ways —
the Trader was **told** up to 40% per name (`overlay_generator._max_position_pct`), the PM
silently **clamped** to 4.5% (`room_runner._risk_tier_size_ceiling`), and compliance allowed a
flat 50% (`safety_floor.SINGLE_NAME_CAP_PCT`). A risk-5 user's Trader narrated 40% while the
system enforced ~4.5% — a ~9× shown≠enforced gap. All three now read one canonical source in
`trading_math/sizing.py`. **No enforced number changes** — the canonical values *are* the
ceilings the PM already clamped to; only the Trader's false narration is corrected.

## Why it's correct — verified, not trusted

### The M03 thesis (independently re-derived)

| Dimension | Result |
|---|---|
| **Red-proof: does the coherence guard actually bite?** | My own script set the pre-fix narration `{1:5,2:10,3:15,4:25,5:40}` against the enforced ceiling `_risk_tier_size_ceiling` and got mismatches on **all 5 tiers** (5≠1.5, 10≠1.5, 15≠3.0, 25≠4.5, 40≠4.5). So `test_position_sizing.py` is non-vacuous — it fails RED on the pre-fix state and stays green only while both call sites read `risk_tier_cap`. |
| **Green: shown == enforced ≤ backstop** | Post-fix `_max_position_pct(t) == _risk_tier_size_ceiling(t) ≤ SINGLE_NAME_ABSOLUTE_CAP_PCT` for every t∈{1..5}; told = `[1.5,1.5,3.0,4.5,4.5]`. |
| **"No enforced number changed" (the safety claim)** | The canonical table `{1:1.5,2:1.5,3:3.0,4:4.5,5:4.5}` reproduces the OLD conditional `4.5 if ≥4 else 1.5 if ≤2 else 3.0` at every tier **and out-of-band** — I probed `[-3,0,1,2,3,4,5,6,7,100,3.9,4.9]` and found **zero divergences**. The enforced clamp and the compliance backstop (`SINGLE_NAME_CAP_PCT == 50.0`) are bit-identical to pre-fix. This is what makes M03 a safe narration-only change. |
| **Rendered narration** | Built the real Trader overlay via the conftest `base_mandate` fixture: risk 1 → `"- Position size capped at 1.5% per name (risk_score=1)."`, risk 3 → `3.0%`, risk 5 → `4.5%`. Matches the architect's manual verification; the risk-5 line is the true 4.5%, not the old false 40%. |
| **Enforced clamp tests still green** | `test_room_pm_size_clamped_to_risk_tier_ceiling` (20%→1.5%) + `test_risk_score_5_sizes_up_aggressively_vs_risk_1` + the two other tier tests → **4 passed** — the PM still clamps to exactly what it clamped to before. |

### The M01/M02 migrations (byte-identical)

| Dimension | Result |
|---|---|
| **RSI / SMA / tone (M01)** | `trading_math/indicators.py` is the old `technicals.py::_rsi/_rsi_tone/_sma` line-for-line (Cutler's simple-average RSI, `period` default 14). `technicals.py` re-exports them under the original private names. The 17-test `test_technicals.py` is **not in the commit** and stays green — the proof the extraction changed nothing. |
| **Drawdown contribution (M02)** | `trading_math/risk.py::drawdown_contribution` is the old `room_prompts._drawdown_snapshot_line` inline math verbatim, with the same `size>0 and entry>0 and 0<stop<entry` guard, now returning `None` on invalid. Caller's `if dc:` maps exactly to the old guard (a 2-field NamedTuple is always truthy when non-`None`). DEF066 point reproduced: 5%×10% stop = **0.5 pts** (not 10); nonsense inputs → `None`. `test_room_prompts.py` (the DEF066 tests) untouched + green. |
| **Combined guard-suite reproduction** | `test_technicals.py` + `test_room_prompts.py` → **31 passed** — the migration preservation proof, run by me. |

### The library contract (portability)

| Dimension | Result |
|---|---|
| **Zero app coupling** | `grep -rE '^\s*(from\|import)\s+app' trading_math/` → **nothing**. The only imports are `typing.NamedTuple`, `from __future__ import annotations`, and relative intra-package imports. Copy-portable claim holds; no import cycle is possible (consumers depend on it, not the reverse). |
| **Total, never-raises sizing** | `risk_tier_cap` clamps an OOB score into the key range rather than raising; `clamp_size` is a bare `min`. Pure integer/float math — no NaN/div, no DEF052 class. |

### Governance & scope

| Dimension | Result |
|---|---|
| **failure_patterns.md P5** | New class "LLM asked to compute a number it presents as fact" present, lists **DEF052 / DEF066 / CR046-M03** as instances, and carries an **Enforcing check** block (per-calc guard tests + the `test_position_sizing.py` coherence test "verified red against the pre-fix 40-vs-4.5 state" + the ledger discipline). Honors the house rule "second occurrence ⇒ add an entry *with a guard*." |
| **cr_list.md** | CR046 row present, dated 2026-07-20, AT:R62, status **`standing`**. |
| **Scope discipline** | `124f15f` diff is CR046-only (21 files). `room_runner.py` diff = the `risk_tier_cap` import + the one `_risk_tier_size_ceiling` function + its docstring — the ruff over-reach the architect reverted did not leak (no `datetime.now(UTC)`/`TimeoutError` churn anywhere in the diff). `AGENT_FAMILIES` removed from `overlay_generator.py` is genuinely unused (`grep -c` → 0). |

## OUT-OF-SCOPE (non-blocking, informational)

- **O1 — `risk_tier_cap` totality holds only for contiguous-key tables (zero exposure today).**
  The function clamps `score` into `[min(keys), max(keys)]` then indexes the table. For the
  shipped default `{1..5}` and the test's `{1,2}` (both contiguous) it is fully total. A
  *sparse* custom `caps` (e.g. `{1:x, 5:y}`) with an intermediate score would `KeyError`. No
  in-tree exposure — every app call site uses the contiguous default, and the only custom-table
  test is contiguous. The docstring's "clamps to the nearest tier" is imprecise (it clamps to
  the key *range*, not the nearest *existing* key). Informational only; no DEF recommended.
- **O2 — cosmetic.** Narration renders float caps ("3.0%" vs "3%"). Honest and correct; no action.

## NEEDS-DEVICE-CHECK / live (legitimately deferred)

- **Live Alpha:** not promoted (Mac is pure editor). M03 is a narration correction + pure-function
  extraction with **zero enforced-behaviour delta** (independently proven: canonical table ==
  old enforced ceiling at every tier + OOB), so a live convene is not load-bearing for
  correctness. Backend logic fully reproduced at code level (861 suite + my red-proof). Architect
  flagged the natural next-Room spot-check + Saiful's acceptance — correct disposition.

## Definition-of-Done disposition

| Architect row | Auditor disposition |
|---|---|
| Scope (standing CR + ledger M01–M05 + M03 fix; backlog deferred, not dropped) | OK — verified vs the CR046 doc's "first filing" section. |
| Tests (854; +2 new files ~19 tests; 1 overlay test rewritten off retired literals) | **Reproduced** (861 at HEAD = 854 + 7 CR047) + **independently red-proofed** (5/5 bite). |
| Manual verification (rendered overlay; live deferred) | OK — narration rendered myself (1.5/3.0/4.5); live correctly carried to NEEDS-DEVICE-CHECK. |
| Docs (CR doc + 5 M-specs + library_survey + P5 + register) | OK — P5 carries its enforcing check per the house rule. |
| Commit tag `(AT:R62 CR046)` on `124f15f` | OK. |
| Register `standing` | OK. |
| Scope discipline (CR046-only; ruff revert; incidental unused-import removal) | OK — `room_runner.py` diff minimal, `AGENT_FAMILIES` 0 refs. |

---

## Verdicts

| Item | SHA | Verdict |
|---|---|---|
| CR046 | `124f15f` | **COMPLETE (round 1)** — M03 shown==enforced independently re-derived (coherence guard bites 5/5 on the pre-fix `{5,10,15,25,40}`; post-fix told=`[1.5,1.5,3.0,4.5,4.5]` == enforced ≤ 50 backstop); **no enforced number changed** (canonical table reproduces the old ceiling at every tier + OOB); narration corrected 40%→4.5% (rendered); M01/M02 byte-identical migrations with their untouched guard suites green (31 passed); library zero-app-imports/portable; P5 governance with enforcing check; register `standing`; 861 suite reproduced. 1 informational OUT-OF-SCOPE (sparse-table totality, zero exposure) + 1 cosmetic; live-Alpha render legitimately deferred (no enforced-behaviour delta). |

OUT-OF-SCOPE: O1 (`risk_tier_cap` sparse-table `KeyError`, zero in-tree exposure — informational); O2 (float narration cosmetic).
