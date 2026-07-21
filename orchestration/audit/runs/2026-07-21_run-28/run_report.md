<!--
Auditor run report — run-28 (2026-07-21, session AT:U1). Round-1 audit of DEF074
"Room drops the computed technical support; renders the 52-week low as the recent-range
floor." Audited SHA d014c95 (backend tree byte-identical at HEAD e4c24f0). Verdict
COMPLETE. Owner: AUDITOR.
-->

# run-28 (round 1) — DEF074 "Room renders 52-week low as the range floor, dropping technical support" → COMPLETE

- **Auditor session:** AT:U1 (track U), 2026-07-21
- **Audited SHA:** `d014c95` (the fix commit). `git diff d014c95 HEAD -- backend/ mobile/`
  is **empty** — the only commit on top is the architect's own lane-open `e4c24f0`
  (`audit/handshake/` only) → the backend tree is byte-identical at HEAD, so I ran the
  suite in place on the main checkout (clean working tree).
- **The defect:** `compute_technicals` produces a real 50-day support (AAPL `$273.75`) that
  `room_runner.py:341` writes into `profile['support']`, but `room_prompts._format_profile`
  rendered `profile['low']` (the 52-week low, `$201.5`) as the recent-range floor and never
  showed `support` at all. The same analyst therefore showed `$273.75` in a 1-on-1
  (`build_technicals_context_block`) and `$201.5` in the Room — two surfaces, two support
  numbers. A P5 "shown == shown across surfaces" routing bug; no value is miscomputed.
- **Backend suite reproduced:** **866 passed** (865 + the 1 new guard; 1 pre-existing
  unrelated FastAPI HTTP_422 deprecation warning in `test_sim_history.py`).
- **Verdict:** COMPLETE — zero BLOCKER / zero MAJOR. No OUT-OF-SCOPE defects. Live-Alpha
  render legitimately deferred (batched with the next promote; pure display change).

---

## The fix

```diff
-        f"Recent range: ${profile.get('low')}–${profile.get('high')}, "
-        f"breakout level: ${profile.get('breakout')}",
+        f"Recent range: ${profile.get('support')}–${profile.get('breakout')} "
+        f"(52-week: ${profile.get('low')}–${profile.get('high')})",
```

One line in `_format_profile`. Display-only — no computed value, no `_profile_for_ticker`,
no overlay cascade, no fallback touched. Only *which already-computed field* the Room reads
for the floor changed (`low` → `support`), with the 52-week band kept as labelled context.

## Why it's correct — verified, not trusted

| Dimension | Result |
|---|---|
| **The field-swap can't crash the Room** (the obvious risk) | The new reads are `profile.get('support')`/`.get('breakout')` — the whole function is `.get()`-based, so a missing key renders `$None`, never a KeyError. Unlike the DEF052 NaN-round class, a field-swap here has no crash path. |
| **`support` is reliably populated → not even a `$None` regression** | Set at `room_runner.py:283` (`round(base_price*0.9, 2)`, synthetic base) **and** `:341` (`technicals.support`, live overlay) — the exact sibling of `breakout` (`:288`/`:342`), which was already rendered pre-fix. Clean `float` (`technicals.py:116`). So the floor always shows a real number. |
| **Room now agrees with the 1-on-1** | `technicals.py:139` renders `"Recent range — support: ${t.support}…"` in the 1-on-1 block. The Room now renders the same `support` field → the two-surfaces divergence is closed (the whole point of DEF074). |
| **Independent render** | `_format_profile` on an AAPL-shaped profile (support 273.75 / breakout 334.99 / 52w-low 201.5 / 52w-high 334.99) → `Recent range: $273.75–$334.99 (52-week: $201.5–$334.99)`. Floor = technical support; 52-week low survives only as parenthetical context. Matches the architect's manual render exactly. |
| **Red-proof (guard bites)** | The new guard drives the real `build_room_messages` path and asserts `"Recent range: $273.75" in sp`, `"52-week: $201.5" in sp`, `"Recent range: $201.5" not in sp`. My reconstruction of the pre-fix line — `Recent range: $201.5–$334.99, breakout level: $334.99` — fails all three, so the test is non-vacuous (RED on the old code). |
| **No number invented** | `support`/`breakout`/`low`/`high` all pre-exist in the profile; the fix changes only which field is the floor — consistent with a routing bug, not a math change. |
| **Bonus: timeframe coherence** | Pre-fix paired a 52-week floor (`low`) with a 50-day ceiling (`breakout`) — mismatched windows. Post-fix is a coherent 50-day `support`–`breakout` pair (`support ≤ breakout` by construction) with the 52-week band as separate context. Strictly an improvement. |
| `pytest tests/unit/` | **866 passed**; `test_room_prompts.py` → 16 passed. Reproduced at HEAD. |

## Scope & governance

| Dimension | Result |
|---|---|
| Diff size | 5 files: `room_prompts.py` (one line) + its test + 3 docs. **Only one source file.** No collateral. |
| Register | `def_list.md` DEF074 = **`resolved`**, correctly classed P5 "shown == shown across surfaces" and cross-linked to the CR046 M01 ledger changelog — the standing agent-math ledger recording a routing instance. |
| Promotion | Not promoted; batched with the next Alpha promote per Saiful (CR046 already went out at `alpha-2026-07-20-3`; DEF074 committed after). Pure display change. |

## NEEDS-DEVICE-CHECK / live

- **Live Alpha:** the Room fact-sheet render on melehost is exercised only after the next
  `/promote-to-alpha`. Zero computed-value delta, so not load-bearing for correctness — the
  render is fully reproduced at code level (866 suite + my own render). Correctly deferred.

## Definition-of-Done disposition

| Architect row | Auditor disposition |
|---|---|
| Scope (one-line display fix; fallback + computed values untouched) | OK — one source line, `.get()`-safe, no cascade change. |
| Tests (866; +1 guard, red on pre-fix) | **Reproduced** (866) + independently rendered + confirmed the guard bites. |
| Manual verification (rendered `_format_profile`) | OK — reproduced the exact string; live carried to NEEDS-DEVICE-CHECK. |
| Docs (DEF074 folder + root-cause + register + M01 ledger link) | OK — P5 classification + ledger cross-link correct. |
| Commit tag `(AT:R62 DEF074)` on `d014c95` | OK. |
| Register `resolved` | OK. |
| Scope discipline (DEF074-only) | OK — 5 files, one source. |

---

## Verdicts

| Item | SHA | Verdict |
|---|---|---|
| DEF074 | `d014c95` | **COMPLETE (round 1)** — one-line display fix: the Room's `_format_profile` renders the computed `profile['support']` as the recent-range floor (52-week band kept as parenthetical context), matching the 1-on-1 surface. `.get()`-safe → no crash path from the field-swap; `support` reliably populated (synthetic `:283` + live `:341`, sibling of the already-rendered `breakout`) → no `$None` regression; clean float. Room now agrees with `technicals.py:139` (1-on-1), closing the two-surfaces divergence. Independently rendered `Recent range: $273.75–$334.99 (52-week: $201.5–$334.99)`; guard non-vacuous (RED on the reconstructed pre-fix line, drives real `build_room_messages`). No number invented; also corrects a 52w-vs-50d timeframe mismatch. Suite **866 passed** reproduced; scope 5 files / one source; register `resolved`, P5-classed + CR046 M01 ledger-linked. Live-Alpha render deferred to the next promote (pure display, no computed-value delta). |

OUT-OF-SCOPE: none. (Synthetic-support fallback when technicals is None is pre-existing + globally disclosed — unchanged, correctly out of scope.)
