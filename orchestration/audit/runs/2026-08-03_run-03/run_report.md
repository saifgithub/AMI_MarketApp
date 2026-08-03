# Audit run 2026-08-03 run-03 — CR136-M05 (rule engine), round 2

Auditor track U. Answers round 1's `AWAITING_FIXES` (2 MAJOR + 1 MINOR, run-02).
Per the r1 closing rule: diffs only, plus a full-suite reproduction.

Verdict: **COMPLETE** — both MAJORs closed and mutation-proven, the MINOR closed.
Two new MINORs recorded, neither blocking. Findings in
`orchestration/audit/cr/CR136-M05.auditor.md`.

## Which SHA — and a process nit

The lane header (line 5) still reads `Branch: main @ a4265fd5` — the ROUND-1 SHA.
§10 and both round-2 test commands name **`2a653673`**, which is where the fixes
actually are. Audited at `2a653673`, detached in
`.claude/worktrees/audit-CR136-m05-r2`, clean at checkout.

Commit contents confirmed before choosing the tree:

- `2a653673` — all source + tests (`portfolio_health.py` +20/−5,
  `portfolio_rules.py` +17/−2, `test_cr136_metrics_engine.py` +42,
  `test_cr136_rule_engine.py` +38, DEF211 row + register).
- `9f653d56` — docs only (lane file +91, `INDEX.md`).

Nit, not graded: an auditor following the header alone audits a tree containing
none of the fixes. The file list also still omits `portfolio_health.py`, which
round 2 modifies.

## Reproduced

| Check | Submission | Auditor | Result |
|---|---|---|---|
| targeted (rule_engine + metrics_engine) | 74 passed | **74 passed** (35 + 39) | match |
| full `tests/unit/` at `2a653673` | 2243 passed, 13 warnings, 282.65s | **2243 passed, 13 warnings, 279.09s** | match |

+3 over round 1's 2240, 0 regressions — the claim is exact.

## M1 — CLOSED

Fix reads correctly: `full_weight_by_ticker` (`portfolio_health.py:552`) is built
over ALL positions from `full_weights`, and the pair gate at `:625-627` plus the
reported `weight_a`/`weight_b` at `:636-637` now use it. That is the same
denominator M05 re-checks (`HoldingInput.invested_weight_pct`), so the two filters
can only agree. With no drops the two bases are identical, so only dropped-holding
books change behaviour — and they change to the basis M05's own contract pins.

- Regression `test_r2b_pair_floor_uses_the_same_basis_the_rule_engine_re_checks`
  reproduces my exact numbers (CCC dropped at exactly `DROPPED_WEIGHT_MAX`, AAA/BBB
  at 4.5% full vs 5.625% covered) and asserts the pair is absent from
  `context["correlation_pairs"]` — **the payload, not merely R2b's fired output**.
  That is stronger than my finding required, and it is the right place to assert:
  anything reading the payload directly sees the same gate. Vacuity-guarded (asserts
  `dropped_holdings == [CCC/short_history]` and `partial is True` first).
- **My mutation** — reverted the gate and the reported weights to `v_weights[i]/[j]`:
  → **1 failed, 38 passed**, exactly
  `test_r2b_pair_floor_uses_the_same_basis_the_rule_engine_re_checks`. Restored
  byte-identical.
- **Did the fix over-tighten?** No. `test_correlation_pairs_are_precomputed_and_weight_gated`
  (`:667`) still asserts AAA/BBB IS emitted at ρ > 0.9 with TINY excluded, so the
  emit path keeps positive coverage; the fix narrows only the dropped-holding case.
- **Downstream blast radius: none.** `weight_a`/`weight_b` have no consumer outside
  their own construction (`grep` across `app/` and `tests/` finds only
  `portfolio_health.py:552,625,626,636,637`); `rule_inputs_from_context` reads only
  `p["a"], p["b"], p["rho"]`. The basis change is inert for rendering.

## M2 — CLOSED for the demonstrated defect; a residual remains (new m2)

`_ceil_display_pct` (`portfolio_rules.py:172-181`,
`Decimal(str(v)).quantize(ROUND_CEILING)`) applied at both breach sites (`:245`,
`:263`). Rendered end-to-end through the real `_f5`:

```
  cap=35.0 true=35.04 fired=True
  slot weight_pct=35.1
  - Your mandate caps a single holding at 35.0%. AAA is at 35.1% of your total portfolio value today.
```

The r1 sentence is gone. **My mutation** — `_ceil_display_pct` → `round(x, 1)`:
→ **1 failed, 34 passed**, exactly
`test_r0_breach_weight_never_renders_at_or_below_its_own_cap`. Restored.

Helper behaviour spot-checked: `35.04→35.1`, `35.00000000001→35.1`, `35.1→35.1`,
`34.999999999→35.0`, `0.0→0.0`, `100.0→100.0`.

**Residual (m2).** The ceiling is applied to the WEIGHT; the CAP is still rendered
by `_fmt`, which is `ROUND_HALF_UP` (`portfolio_finding.py:196-200`). A cap whose
own 1 dp rounding goes UP can therefore meet the ceilinged weight:

```
  cap=35.05 true_weight=35.06 fired=True
  shown cap='35.1'  shown weight='35.1'  CONTRADICTION=True
  - Your mandate caps a single holding at 35.1%. AAA is at 35.1% of your total portfolio value today.
  cap=39.95 true_weight=39.96 fired=True
  shown cap='40.0'  shown weight='40.0'  CONTRADICTION=True
```

Reachability, checked rather than assumed: **not reachable from any preset** —
`DEFAULT_RISK_TIER_CAPS = {1: 1.5, 2: 1.5, 3: 3.0, 4: 4.5, 5: 4.5}` and the sector
presets (25.0–60.0) are all exact at 1 dp, so a weight strictly above them always
ceilings at least one display unit higher. It needs a deliberate sub-0.1-precision
override: `Mandate.single_name_cap_pct` / `sector_cap_pct` are plain
`float | None` (`schemas/mandate.py:162-163`) with no `ge`/`le`/`multiple_of`, and
the PATCH path (`api/mandate.py:134-148`) narrates the change without validating
its precision.

Graded MINOR, and I want the reasoning on the record because I considered MAJOR:
the defect I demonstrated in r1 is genuinely closed and mutation-guarded, the
preset population cannot reach the residual, and re-bouncing a lane for a case
requiring an explicit sub-0.1 override is disproportionate. It is nonetheless the
same contradiction, so it is recorded rather than waived.

## m1 — CLOSED

`test_r0_sector_cap_is_strict_and_from_the_gate` mirrors the name-half pin with a
three-point boundary (`40.1` fires, `40.0` does not, `39.9` does not) and asserts
on the sector-scoped breaches specifically.

**My mutation** — the exact mutant from r1
(`> sector_cap_frac + _SECTOR_EPSILON` → `>= sector_cap_frac - _SECTOR_EPSILON`):
→ **1 failed, 34 passed**, exactly `test_r0_sector_cap_is_strict_and_from_the_gate`.
The mutant that survived r1 is now killed. Restored byte-identical.

## New MINOR — m3, provenance mislabeling

Three code sites cite defect IDs that do not describe them:

- `portfolio_health.py:607` — `# AT:R66 DEF211 fix — the floor gate and the
  reported weights must read off the SAME denominator...` That is the R2b basis
  fix (r1 finding M1), **not** DEF211.
- `test_cr136_metrics_engine.py:690` docstring — `AT:R66 DEF211 regression
  (M05-r1 audit M1)`. Same mislabel.
- `portfolio_rules.py:172` — `AT:R66 DEF212 fix — a breach slot must never render
  at or below the cap`. **DEF212 does not exist**: no
  `docs/defect/_registry/DEF212.row.md` (registry tops out at DEF211) and no row in
  `def_list.md`.

DEF211 is minted for the zero-variance-benchmark leg — my r1 OUT-OF-SCOPE item —
and its row is accurate and detailed, correctly marked `open` and explicitly
deferred. So a reader tracing `portfolio_health.py:607` opens DEF211, finds an
unrelated defect that is still open, and reasonably concludes the fix in front of
them did not work. Documentation-only, no behavioural impact; worth correcting
while the context is fresh, either by minting DEF212 for the R0 rendering fix and
re-pointing the R2b comment at the audit finding, or by citing the audit round
directly (`CR136-M05 r1 M1/M2`) as the other in-file comments do.

## Round-1 items carried forward, unchanged

- **DEF211** (zero-variance benchmark) — correctly minted, `open`, not fixed here.
  Deferral is right: the file is M04/M07's and round 2 does not touch it. The row
  records both candidate fixes and flags that the narrower per-block framing needs a
  decision plus a live check. Nothing owed to this lane.
- The live cross-check against Alpha still has not run (Mac off the LAN); owed at
  promotion per M11 §6 Phase 2, and it gates neither lane's verdict.
