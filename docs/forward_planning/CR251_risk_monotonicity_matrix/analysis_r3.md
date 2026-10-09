# CR251 — analysis_r3: v2 matrix on DeepSeek-V4-Flash (dsv4 arm)

**Status:** PRELIMINARY (companion to frozen BASELINE.md / analysis_r2.md — do not edit those).

**Arm definition:** the shipped stack at `alpha-2026-10-09-1` (`bf0fa99f`: CR249
trader-geometry repair gate, CR252 evaluation parameters folded into all 12
personas, CR253 data lanes incl. D28 EDGAR ingest, DEF451 fix) run as the full
300-room risk matrix (30 CR228 tickers × risk 1–5 × 2 reps) on
**DeepSeek-V4-Flash** (alpha-spark `100.94.223.38:8003`, via Tailscale) instead
of ami-llm, because ami-host died 2026-10-08 and awaits physical reboot.
Executed in-container on melehost inside the promoted api-alpha image.
Veto/resurrection review **disabled** via `ROOM_*_REVIEW_ENABLED=false` to
match v1 baseline methodology (v1 ran Mac-side where the kimi review 401s —
verified 0 "Veto review" strings in v1 JSONLs; the first dsv4 sweep room had
its APPROVE vetoed to PASS before this was caught).

## Caveats (read before diffing)

1. **Provider confound:** v1 baseline = ami-llm (qwen38-flash-next), this arm
   = dsv4. Every diff below mixes "stack changed" with "model changed". The
   clean ami-llm v2 run (`~/cr251_v2`) is still queued behind ami-host's reboot.
2. Review layer matched to v1 (both OFF).
3. Jev scored with the same `jev_score_runs.py` as v1.

## Pooled APPROVE curve (of 60 convenes per level)

| Risk | v2-dsv4 | v1 baseline (ami-llm) |
|---|---|---|
| R1 | **5** | 0 |
| R2 | **11** | 3 |
| R3 | **22** | 4 |
| R4 | **27** | 24 |
| R5 | **17** | 26 |

Pooled monotone: **NO** (rises R1→R4, inverts at R5).
Baseline was monotone (0/3/4/24/26, a switch between R3 and R4).

## What changed vs baseline

1. **The knob now acts at every level** — dsv4 approves 8%/18%/37%/45% across
   R1–R4 where ami-llm sat at 0/5%/7% then jumped. Low-risk willingness is
   5–5.5× higher.
2. **The R5 inversion (27→17)** — broad-based: 12 approval-slots lost R4→R5
   (DE 2, SO 2, LEVI 2, TMO, DHR, BAC, CAG, JPM, MO) vs 2 gained (NKE, XPEV).
   R5 PASS reasons read as quality passes (valuation premium, insider selling,
   dividend coverage) — the room raises its evidence bar in proportion to
   commitment size. This is the size-worthiness coupling surfacing at the
   decision layer; sizing itself is perfect (mean approved size 1.00→4.82%,
   maxes pinned at each level's cap). The cap-1% arm (`cr251-cap1-*`, running)
   isolates this: if variability collapses with size pinned, coupling confirmed.
3. **Discrimination did NOT improve.** APPROVE-room evidence scores are LOWER
   than PASS-room at every level (Δ = −0.11/−0.05/−0.11/−0.08/−0.07; baseline
   Δ≈0.00). The disease the whole CR247–253 arc targets is unchanged on dsv4.
4. **Risk-bar still flat** — min support among approvers 0.44/0.56/0.44/0.50/0.50
   (baseline 0.55–0.64 flat). No tier demands more evidence.
5. **Stability: verdict flips 17%** (baseline 20%, marginal gain); **Jev
   room-score flips 41%** (baseline 32%, worse).
6. **All 15 monotonicity violations are decision-limited** (evidence support
   present, verdict curve still breaks) — same decomposition class as v1.

## Per-desk mean Jev support (n=300 each)

bull 0.54 · news 0.66 · bear 0.72 · fundamentals 0.73 · RM 0.81 · trader 0.82 ·
market 0.86 · social 0.86 (debator desks not scored in this pass).
Baseline's weakest desks were the risk debators (aggressive 0.49, neutral 0.57)
and bull 0.62; dsv4's bull remains the weakest scored desk at 0.54.

## Decision matrix

Full 30×5 rep-level matrix was delivered to Saiful in-session (A/P per rep);
raw data: `out/cr251-v2-dsv4/r{1..5}/`, Jev: `out/cr251-v2-dsv4/jev/`,
tool report: `out/cr251-v2-dsv4/analysis.md`.

## Open questions for the clean run (ami-llm, post-reboot)

- Does ami-llm reproduce the R5 inversion, or is it dsv4-specific?
- Does discrimination move at all on ami-llm with the new stack?
- Cap-1% arm result (due ~2026-10-09 18:00 UTC) — if it flattens the curve,
  the size-worthiness fix (CR253 disposition) becomes measured-mandatory.
