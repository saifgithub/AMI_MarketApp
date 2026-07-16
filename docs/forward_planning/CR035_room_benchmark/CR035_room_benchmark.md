# CR035 — Room-vs-Street benchmark (Convene the Room vs analyst consensus)

**Status:** in_progress · **Filed:** 2026-07-16 (AT:R59) · **Requested by:** Saiful ("time to do some testing … compare our results against the consensus of a few respected websites")

## What

A cross-sectional benchmark of Convene the Room: convene ~30 tickers against the live
Alpha backend, collect each final `Verdict`, and score agreement against analyst
buy/sell/hold consensus from external aggregators. Includes an **ablation batch**
(analyst-consensus line suppressed server-side) to measure whether the Room forms its
own view or parrots the Street rating it is fed.

## Why

The AT:R58 batch (DEF051–DEF057) made the Room's verdict debate-driven and its inputs
truthful. Before trusting it in front of alpha users we need an external sanity check.
Full backtesting is impractical (12 vLLM calls per convene); a consensus comparison is
cheap (~360 calls per batch) and directly answers "does the Room's Buy/Hold line up
with the Street's?"

## Method

- **Verdict mapping:** APPROVE/MODIFY → Buy, PASS → Hold, REJECT → excluded but logged
  (with a neutral mandate any REJECT is itself a finding). The Room is buy-side only —
  there is no SELL — so on consensus-Sell names the scoreable question is the
  **red-line check**: the Room must not APPROVE them.
- **Universe:** ~30 tickers balanced across consensus buckets (~12 buy, ~12 hold,
  ~6 sell-leaning), mixed sectors, 2–3 sparse small caps as robustness probes.
  Committed as `tickers.txt`.
- **Batches:** fresh anonymous user per batch (defeats the 24 h (user, ticker) dedup),
  plan patched to `trader` via the admin API so runs execute at the representative
  tier, pinned neutral `mandate_override`.
- **Consensus sources:** yfinance (`recommendationKey/Mean`, `targetMeanPrice`,
  `recommendations_summary` counts) + StockAnalysis.com forecast endpoint
  (best-effort). TipRanks / Zacks / MarketBeat are spot-checked at report time.
  Finnhub dropped (API key + ToS approval requirements — see CR007 research).
- **Metrics:** agreement rate (pooled + per source), 2×3 confusion matrix, red-line
  list, Cohen's kappa, Room target vs mean analyst target %diff, and a spot-price
  snapshot enabling a forward-return re-score (`--forward` mode) in 2–4 weeks.
- **Ablation:** `SUPPRESS_ANALYST_CONSENSUS` env flag gates the two analyst fields in
  `fundamentals.py`; promoted to Alpha, flipped on for the ablation batch only, then
  reverted (the flag affects live users while on).

## Scope

- `backend/scripts/room_benchmark.py` — batch runner (mint user → patch plan →
  stream-POST → poll → JSONL; resumable).
- `backend/scripts/room_consensus.py` — consensus fetchers + normaliser.
- `backend/scripts/room_benchmark_report.py` — scoring + markdown report + forward mode.
- `backend/app/core/config.py`, `backend/app/services/fundamentals.py`,
  `docker-compose.yml`, `infra/alpha.env(.example)` — ablation gate.
- `results/` in this folder — `tickers.txt`, `users.json`, `runs.jsonl`,
  `consensus.jsonl`, `prices.json`, `raw/`, `report.md`.

## Acceptance

1. Baseline batch: ≥90% of the universe produces a terminal verdict with
   `cached: false`.
2. Consensus: ≥90% of tickers have a normalised bucket from ≥2 programmatic sources.
3. Report renders agreement rate, confusion matrix, red-line list, target sanity,
   baseline-vs-ablation comparison.
4. Ablation flag verified back to `false` on melehost after the ablation batch.

## Risks

- StockAnalysis.com endpoint is undocumented (SvelteKit devalue payload) — defensive
  parsing, raw payloads cached, treated as best-effort.
- yfinance throttling on the Mac side — backoff + spacing.
- Degraded runs (90 s per-agent timeout) — recorded, resumable.
- Circularity: baseline agreement is partly self-fulfilling because the Fundamentals
  agent sees Yahoo's consensus — this is exactly what the ablation isolates.
