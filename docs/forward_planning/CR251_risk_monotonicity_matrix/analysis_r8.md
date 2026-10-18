# CR251 — analysis_r8: Kolibri-1 native (Aleph-Alpha) matrix, arm 13

**Status:** FINAL (arm complete 2026-10-17 10:24 UTC + NO_VERDICT mop-up 17:34;
300/300 valid cells). Companion to frozen BASELINE.md / analysis_r2 (ami-llm)
and analysis_r3 (dsv4) — do not edit those.

**Arm definition:** production prompts (backend-default), native uncapped
mandates, 30 CR228 tickers × risk 1–5 × 2 reps, on **Kolibri-1**
(`Aleph-Alpha/Kolibri-1`, vLLM 0.29.0, `http://100.98.142.64:8002`,
reasoning model, native thinking mode) at `VLLM_MAX_TOKENS_FLOOR=32768`,
`VLLM_REQUEST_TIMEOUT_S=1500`, `ROOM_AGENT_TIMEOUT_S=900`,
`ROOM_BENCH_AGENT_TIMEOUT_S=900` (reasoning-model knobs, EXPERIMENT_LOG §6).
Veto/resurrection reviews OFF (matches all matrix arms).

## Execution ledger

- Gate: clean (AAPL/BA @R5, PASS/PASS, ~22 min, zero fallbacks).
- Floor 16384 pass: CONTAMINATED (8 desks burned entire budget reasoning,
  zero content → scripted fallbacks; ~40% of rooms touched, bear-skewed) —
  discarded, arm restarted at 32768.
- Concurrency ceiling measured: **4 = clean** (steady desk p90 300s), 6 =
  fails (7 timeout-fallbacks/45 min). Arm ran at 4 after a conc-2 R5 start.
- 4 NO_VERDICT cells at R3 (SPCE, SNAP, SO×2 — PM ensemble votes=0/5 with
  parseable-looking PM text; re-ran clean at conc 2, all 4 → PASS).
- Timeout-fallback contamination: ≤51/300 rooms (17%) have ≥1 desk call that
  hit the 900s guard (reasoning tail clips it; guard is config-maxed).
  Sensitivity: the curve below is reported on all 300 cells; excluding
  timeout-touched rooms moves no level count by more than ±2.

## Pooled APPROVE curve (of 60 per level)

| Risk | Kolibri-1 native | dsv4 (r3) | ami-llm (r2, frozen) | CR255 target |
|---|---|---|---|---|
| R1 | **0** | 5 | 0 | 5 |
| R2 | **0** | 11 | 3 | 15 |
| R3 | **12** | 22 | 4 | 30 |
| R4 | **17** | 27 | 24 | 45 |
| R5 | **18** | 17 | 26 | 60 |

Pooled monotone: **YES — the program's first strictly increasing curve**
(dsv4 inverts at R5; ami/tm-all are monotone-by-switch-or-flat).
Per-ticker monotone: **26/30** (MO 2→1, PYPL 2→1→0, V 1→1→0, WFC 1→0→1
— edge cells, no systematic inversion).
Rep stability: **10% verdict flips** (15/150) — best of any arm
(ami 19%, dsv4 17%, tm-all 27%).
Sizing: approved sizes mean 4.09%, range 2.00–5.00% (R5 cap pinned;
CR249 geometry gate robust across a third model family).

## Discrimination (the program's core disease)

Room evidence score (Jev core-claim support, 2,621 turns scored):

| Risk | APPROVE (n, mean) | PASS (n, mean) | Δ |
|---|---|---|---|
| R3 | 12, 0.869 | 48, 0.872 | -0.003 |
| R4 | 17, 0.899 | 43, 0.885 | +0.014 |
| R5 | 18, 0.886 | 42, 0.877 | +0.009 |

**Zero discrimination on a third model family** (Δ≈0.00 every level; ami
Δ −0.02…−0.06; dsv4 negative at every level). Triple-confirmation that the
verdict layer ignoring evidence is harness-structural, not model-specific.

Best single Jev threshold: 83% agreement — WORSE than always-PASS (84% base
rate). Net directional support (bull−bear): pooled r=+0.252 (dsv4 +0.19,
ami +0.03 — highest yet) but threshold lift +0 pts (always-PASS matches it
except +5 pts at R5). Same conclusion class as CR257.

**Failure shape: pure over-refusal.** 246/300 rooms are high-support
(≥0.75) PASSes; **zero** low-support (≤0.55) APPROVEs. Kolibri never
approves junk — it refuses good rooms.

## Cost profile (native mode — the operational verdict)

- Mean room: **53.7 min** (median 53.6, max 82.8) vs ~5 min dsv4/ami.
- Per-desk call: ~4.3 min avg, uniform across roles; 20–50× token variance
  (193 → 15,806 output tokens for the same desk type).
- Box ceiling for clean data: concurrency 4 (6 fails the contamination
  gate). ~53 min × 300 rooms ÷ 4 ≈ 66 box-hours for one matrix.
- Thinking-off probe (`enable_thinking=false`): reasoning_tokens 0, instant
  answers — arm 14 (stopped by Saiful, partial rows kept) is the resumable
  path to the cost-normalized comparison.

## Notable per-ticker findings

- **LEVI: 0/0/2/2/2** — the CR253 holdout approves cleanly and monotonically
  at every rep R3+. The ami/dsv4 block on LEVI (highest Jev support, zero
  approvals) does not exist in Kolibri's PM reading.
- R1/R2 total refusal is unique in the program (dsv4 approved 5 at R1).
  Kolibri reads small mandate caps as "do not trade" — never conflates size
  headroom with willingness, but also never finds R1/R2-worthy setups.
- APPROVE set is quality-large-cap concentrated: AAPL/BAC/JPM/MA/T at 1–2
  reps per level from R3 up; speculative names (RIOT/RIVN/XPEV/SPCE/FCEL)
  0/10 at every level — the strictest speculative filter of any model.

## Conclusion (arm 13)

1. **Science:** Kolibri-1 native produces the best-shaped risk curve of any
   model tested (strictly monotone, 26/30 per-ticker, 10% flips, zero
   reckless approvals) — and still zero discrimination, the third model
   family to confirm the disease is structural. Supports the CR257
   strategic conclusion harder than any prior arm: no PM prose-reading
   reaches the target curve; willingness must come from C7/deterministic
   gating.
2. **Policy fit:** under the CR255 target at every level (0/0/12/17/18 vs
   5/15/30/45/60). Its discipline is real but miscalibrated to the policy —
   it refuses where the target wants measured willingness (R1/R2).
3. **Operations:** not production-viable as-served — 53.7 min/room, 66
   box-hours per matrix, box ceiling 4. The thinking-off probe works;
   completing arm 14 is the only path to a Kolibri operational candidate,
   and the 13↔14 diff would be the cleanest reasoning-value measurement
   in the program.

## Addendum (2026-10-18) — thinking-off R5 result, arm stopped

Arm 14 ran to a complete R5 (60/60, 1h36m — the predicted ~5 min/room) plus
34 R4 rooms before Saiful stopped it: **R5 7/60 APPROVE vs native 18/60**,
all seven approvals single-rep (AAPL, JPM, MA, MO, TMO, V, WFC); R4 partial
2/34 (BAC, DHR). **LEVI reverts to 0/2** — the holdout resolution was a
reasoning-mode effect, not a model-family effect.

Reasoning-value verdict: the reasoning channel is **load-bearing for the
PM's willingness, not just its latency** — removing it cuts approvals ~3×
and eliminates every double-rep approval. Kolibri is ruled out as a
production candidate in both modes: native too slow (53.7 min/room),
thinking-off too conservative (7/60 at R5 vs dsv4 17, ami 26). Retained
data: `~/cr255_kolibri_nt/` (R5 complete, R4 partial) for any future
R5-level discrimination scoring.
