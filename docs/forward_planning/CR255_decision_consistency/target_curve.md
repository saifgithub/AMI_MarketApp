# CR255 — Target-curve policy (Saiful, 2026-10-10; amended 2026-10-13)

**Amendment 2026-10-13 (Saiful, via CR256 review B2):** R5 is re-anchored to
the investable universe. The code-computed holdout predicate (negative
SBC-adjusted FCF) bars 7 of 30 tickers (APD, BA, FCEL, RIOT, RIVN, SNAP,
SPCE — published list, with a data-absent branch for the 9 tickers lacking
the datum). R5 therefore approves every non-barred name: **46/60 target**
(tolerance ±8 → 38–54). Holdouts stay out at every level (AC3).

**Policy:** the Room should approve, per 60 convenes (30 tickers × 2 reps):

| Risk | Target approvals | % of universe | % of investable (23) |
|---|---|---|---|
| R1 | 5 | 8% | 22% |
| R2 | 15 | 25% | 65% |
| R3 | 30 | 50% | — |
| R4 | 45 | 75% | — |
| R5 | **46** | 77% | 100% |

Shape: monotone ramp. R5 = approve any defensible thesis among investable
names; R1 = only exceptional evidence.

**Why this is the anchor for the evidence bar (CR255 Phase C7):** the per-level
net-thesis-support thresholds are FIT to reproduce this curve on the
calibration universe. The fit, not intuition, sets each level's number.

**Measured curves for contrast** (same 30-ticker universe, per 60 rooms):

| Arm | R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|---|
| ami-llm baseline (frozen) | 0 | 3 | 4 | 24 | 26 |
| dsv4 uncapped | 5 | 11 | 22 | 27 | 17 |
| dsv4 size-pinned 1% | 11 | 13 | 16 | 15 | 23 |

**Holdout rules that survive any fit:**
- RIOT-shaped: high grounding but thesis-broken (support 0.76–0.80, 0/10
  baseline) must stay out at every level — proof the bar is thesis-aware,
  not a bare threshold.
- APD/BA-shaped: grounded bear case with negative SBC-adjusted FCF — PASS is
  correct even at R5; grounding ≠ direction.
