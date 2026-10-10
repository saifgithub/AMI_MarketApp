# Room Investigation V2 — Experiment Log (living document)

**Maintainer:** track K (AT:K3) · **Started:** 2026-10-08 · **Status:** active
**Purpose:** the canonical record of every experiment arm run in the CR251/253/254/255
consistency program, the methodology that makes arms comparable, and the handoff
protocol for parallel lanes. Analysis write-ups live in
`docs/forward_planning/CR251_risk_monotonicity_matrix/analysis_r*.md`; this log is
the map that ties them to data.

## How to read this log

Each arm = one row in the board + a short findings entry. Methodology facts in §2
are load-bearing — a lane that ignores them produces data that cannot be diffed.
Handoff rules for parallel lanes are in §4.

## 1. Arm board

| # | Arm | Rooms | Prompt | Mandate | Model | Status | Data (local → melehost) | Analysis |
|---|---|---|---|---|---|---|---|---|
| 1 | main dsv4 matrix | 300 (30×5×2) | production | uncapped | dsv4 | DONE | out/cr251-v2-dsv4 → ~/cr251_v2_dsv4 | analysis_r3 |
| 2 | cap-1% matrix | 300 (30×5×2) | production | single_name_cap=1% | dsv4 | DONE | out/cap1-full → ~/cr251_v2_dsv4_cap1 | analysis_r4 |
| 3 | bpw flip-flop probe | 6 (R5) | production | 1% cap | dsv4 | DONE | out/cap1-bpw | analysis_r4 |
| 4 | dose probe (BAC/PYPL/WFC) | 12 (R5) | production | caps 2/3/4% | dsv4 | DONE | out/cap1-dose | analysis_r4 |
| 5 | inversion probe | 16 (R5) | production | 1% cap | dsv4 | DONE | out/cap1-inv | analysis_r4 |
| 6 | cap ladder (8 inv tickers) | 48 (R5) | production | caps 2/3/4% | dsv4 | DONE | out/cap1-ladder | analysis_r4 |
| 7 | sub-cap variant | 33 (11×3, R5) | disposition + sub-cap | uncapped | dsv4 | DONE | out/cr253-subcap | analysis_r4 |
| 8 | disposition-only variant | 33 (11×3, R5) | disposition only | uncapped | dsv4 | DONE | out/cr253-disposition | analysis_r5 |
| 9 | **disposition matrix** | **300 (30×5×2)** | **disposition only** | **uncapped** | **dsv4** | **RUNNING (ETA ~18:00 UTC 2026-10-10)** | → ~/cr253_disp_matrix | analysis_r6 (pending) |
| 10 | clean ami-llm matrix | 300 (30×5×2) | production | uncapped | ami-llm | QUEUED (DGX ~2 days out; hourly watcher 01M4HPV4ZND7A60H9MWK1CH9C5) | → ~/cr251_v2 | analysis_r6 (provider control) |

Benchmark yamls for every arm: `benchmarks/cr251-*.yaml`, `benchmarks/cr253-*.yaml`;
mandate snapshots: `benchmarks/mandates/cap{1,2,3,4}-r5.json`; prompt variants:
`benchmarks/cr253-disposition/prompts/portfolio_manager.md` (production + disposition
table), `benchmarks/cr253-subcap/prompts/` (adds sub-cap conditional — measured inert).

## 2. Methodology (load-bearing — replicate exactly)

1. **Model:** DeepSeek-V4-Flash via OpenAI-compatible vLLM at `http://100.94.223.38:8003`
   (alpha-spark, Tailscale; served model name `deepseek-ai/DeepSeek-V4-Flash`). No key.
   Shared box — keep ≤4 concurrent rooms (6 briefly is proven; 8 untested, don't).
2. **Runtime:** in-container on melehost inside the promoted api-alpha image
   (`alpha-2026-10-09-1`, bf0fa99f). Harness mount MUST be the repo root:
   `-v ~/ami_trade:/harness:ro` (env_bootstrap resolves REPO_ROOT as parents[4] of
   library/env_bootstrap.py — mounting the V2 dir at /harness crashes with IndexError).
3. **Tool path inside container:** `/harness/docs/tools/room_investigation_V2/tools/room_benchmark.py`.
4. **Out dir:** host-mounted, MUST `chmod -R a+rwx` before the run (compose run uid
   cannot write saiful-owned dirs).
5. **Env on every run:** DATABASE_URL (pg password from ~/ami_trade/.env),
   VLLM_BASE_URL + VLLM_MODEL as above, USE_REAL_MARKET_DATA=true,
   **ROOM_VETO_REVIEW_ENABLED=false + ROOM_RESURRECTION_REVIEW_ENABLED=false** —
   the in-container kimi review provider IS reachable on melehost (unlike the Mac)
   and v1 methodology had it OFF. Omitting these = a different experiment.
6. **Jev scoring (Mac side):** needs the pg tunnel
   (`ssh -f -N -L 5434:127.0.0.1:5434 melehost-ts`), DATABASE_URL to
   `127.0.0.1:5434/ami_trade`, JEV_API_KEY from repo .env (never print).
   `tools/jev_score_runs.py --runs <jsonl> --out <jsonl> --workers 4` — ~3 min/level.
7. **Join key:** jev rows and verdict rows join on **(arm_key, risk_score)** —
   arm_key alone is NOT unique across levels.
8. **Never share batch name/out-dir between concurrent runs.** Resume semantics:
   delete NO_VERDICT/error rows before re-running.
9. D28 EDGAR ingest is DONE (30/30 tickers, 10,584 facts) — all arms see SBC/ROIC.
10. Analysis tools: `tools/jev_verdict_relation.py` (Jev↔verdict), `tools/net_support.py`
    (directional net thesis support), `tools/decision_factors.py` (reason classification),
    `tools/risk_matrix_analysis.py` (monotonicity/discrimination/risk-bar/stability).

## 3. Findings per arm (the short version)

- **Arm 1 (main):** curve 5/11/22/27/17 — R5 inverts R4. Sizing perfect (1.00→4.82%
  means, caps pinned). Raw Jev room-mean ANTI-correlates with approval (r=−0.36):
  decomposed into trader prose artifact (−0.44, verdict-aware), rational bear weighting
  (−0.36), direction-agnostic conflation. Direction-corrected net support r=+0.19,
  zero threshold value over always-PASS. 158 high-support PASSes vs 4 low-support
  APPROVEs — failures are over-refusal (catalyst-waits 82% of high-support passes).
- **Arm 2 (cap-1%):** pinning size removes the R5 inversion (11/13/16/15/23) but flip
  rate worsens (21% vs 17%) — size coupling is real, variability is mostly elsewhere.
  2 spontaneous sub-cap approvals (NKE 0.5%, SLB 0.7%) with NO instruction.
- **Arms 3–6 (probes):** BAC/PYPL/WFC flip-flops recover at small caps; per-name size
  thresholds are real (DHR/MO approve ≤3%, refuse ≥4%; SO/CAG never at any size);
  dose-response is name-specific, not global.
- **Arm 7 vs 8 (isolation):** disposition table drives the ENTIRE willingness shift
  (sub-cap 13/33, disposition-only 16/33, uncapped 5/22). Sub-cap conditional inert.
  Stability untouched by both — flips are upstream of the PM.
- **Arm 9 (running):** does the disposition table move the full curve toward the
  CR255 target (R1=5/15/30/45/60 per 60)?
- **Decisions locked:** target curve 5/15/30/45/60 (Saiful); single-metric evidence
  bar DEAD (net-support ties) → C7 composite score; sub-cap = future structural
  computation, never prose.

## 4. Handoff for the tm-all lane (CR254)

The tm-all lane runs the same 30×5 matrix with the tm-all-converted prompt variant
after **arm 9 completes**. Rules:

1. **Start signal — do not start before BOTH hold:**
   - `ssh melehost-ts 'grep -q "DISP MATRIX DONE" /tmp/disp_matrix.log'` → exit 0, AND
   - 300 result rows: `cat ~/cr253_disp_matrix/r*/runs_*.jsonl | wc -l` == 300.
   Track K's analysis_r6 consumes the same data read-only — no conflict, but do not
   modify `~/cr253_disp_matrix/`.
2. **Replicate §2 exactly.** Your ONLY deltas: benchmark name (`cr254-tmall-r{1..5}`),
   out-dir (`~/cr254_tmall_matrix/r{1..5}`), prompt_variant (`cr254-tmall` or whatever
   the variant dir is named), and the prompt files themselves.
3. Write your yamls by copying `benchmarks/cr253-disp-matrix-r5.yaml` and changing
   name/out-variant fields — same ticker list, same repeats=2, same concurrency.
4. Jev-score your arm the same way; join on (arm_key, risk_score); produce your own
   analysis as analysis_r7 (or your lane's naming) diffed against arms 1 and 9 plus
   the frozen BASELINE.md. The diff protocol: monotonicity, discrimination (use
   net_support.py — raw room-mean misleads), risk-bar, stability, per-desk support.
5. The frozen references are BASELINE.md + analysis_r2 (ami-llm heuristics-off).
   Do not edit them. analysis_r3–r5 are dsv4-era context, also read-only.

## 5. Open items

- Saiful: DGX power-cycle (~2 days) → arm 10 auto-fires (hourly watcher).
- Saiful: approve disposition fold-in AFTER arm-10 control (prose effects are
  model-specific) and the full CR253 acceptance benchmark.
- Track K next build: CR255 C7 composite decision score; Phase D regression suite.
- Revert the alpha LLM bridge (LLM_FORCE_PROVIDER=glm) after ami-host is stable.
