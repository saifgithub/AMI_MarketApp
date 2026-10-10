# CR255 — Target-curve policy (Saiful, 2026-10-10)

**Policy:** the Room should approve, per 60 convenes (30 tickers × 2 reps):

| Risk | Target approvals | % of universe |
|---|---|---|
| R1 | 5 | 8% |
| R2 | 15 | 25% |
| R3 | 30 | 50% |
| R4 | 45 | 75% |
| R5 | 60 | 100% |

Shape: monotone ramp, not a switch. R5 = approve any defensible thesis;
R1 = only exceptional evidence.

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
