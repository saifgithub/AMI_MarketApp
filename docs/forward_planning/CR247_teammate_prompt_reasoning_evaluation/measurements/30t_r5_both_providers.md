# CR247 — 30-ticker R5 new-persona run (both providers)

Run: 2026-09-30, `room_batch.py`, CR228 pilot universe (30 tickers,
stratified sell→strong_buy), risk_score 5, concurrency 4 per provider,
harness 5K floor, backend at `6011c349` (Phases 0–6 + Phase 5 personas).
Outputs: `out/cr247-30t-r5/{vllm,deepinfra}/runs_*.jsonl`. 60/60
completed, 0 failed.

## Verdict distributions

| Provider | APPROVE | PASS | Approval rate |
|---|---|---|---|
| vLLM (`qwen38-flash-next-abliterated-nvfp4`) | 14 | 16 | **47%** |
| DeepInfra (GLM-5.3-Flash) | 4 | 26 | **13%** |

vLLM APPROVEs: APD, BA, BAC, DHR, FCEL, JPM, MA, PLD, PYPL, RIVN, SLB, T,
V, WU. DeepInfra APPROVEs: BAC, MO, SO, T. Common: BAC, T.

## Cross-provider agreement: 16/30 (53%)

14 disagreements — 12 are vLLM=APPROVE / DeepInfra=PASS, 2 are the
reverse (MO, SO). Direction is consistent: the serving model is
materially more approval-prone than GLM-5.3-Flash at R5 on identical
mandates. (Context for CR240/D18: this is model-bias shape, measured on
the new personas.)

## Gate results

| Provider | OK | FAIL | Failure class |
|---|---|---|---|
| vLLM | 25/30 | 5 | all MISSING_STANCE (research_manager ×1, neutral_debator ×1, bull_researcher ×1, conservative_debator ×2) — the recurring per-seat envelope-miss class; **zero truncation, zero PM-JSON failures** (schema constraint held across ~150 PM draws) |
| DeepInfra | 26/30 | 4 | all PM_JSON_UNPARSEABLE (LEVI, SLB, TMO, XPEV) — the known GLM template-format class, tolerant parser recovered every convene; zero truncation, zero missing stances |

Aggregate across both arms: zero truncation events, zero
corruption/REJECT anomalies, zero ensure_portfolio races at concurrency
4 (the uuid5 fix held), reviews exercised on every eligible verdict
(DeepInfra-CIO resurrections audited cross-model on vLLM — upheld or
re-run; vLLM-CIO reviews hit the kimi-fallback 401 and fail-safed,
verdicts unchanged — the Mac env key defect, no production impact).

## Operational observations

- Wall clock: DeepInfra 81 min, vLLM 146 min for 30 convenes at
  concurrency 4 (vLLM also served the DeepInfra-CIO review calls, and
  convenes stretched to 17 min under 4-way contention; DeepInfra 429'd
  sporadically under the PM fan-out, recovery path absorbed all).
- Degrade-loudly lines fired correctly throughout: `sbc_absent`/
  `roic_absent` on tickers lacking the new tags (WU, WFC, XPEV, XRX…),
  `debt_maturity_absent` (WU, XPEV), `peer_basket_unavailable` (AAPL
  SIC-3571, XRX 1-peer), `news_context_recency_floor_dropped` (XRX).
- `room_geometry_implausible_level` fired twice (V stop/entry ratio,
  XPEV $1 stop) — the guard working.
