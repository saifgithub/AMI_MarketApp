# CR035 — Room-vs-Street benchmark (Convene the Room vs analyst consensus)

**Status:** done (report in `results/report.md`) · **Filed:** 2026-07-16 (AT:R59) · **Requested by:** Saiful ("time to do some testing … compare our results against the consensus of a few respected websites")

## Findings (2026-07-16, post-fix batches `baseline2` + `ablation2`, 64 convenes)

1. **The Room is an entry-timing gate, not a consensus tracker.** 29/32 PASS,
   3/32 APPROVE (1.5–3% sizes) per batch. Agreement with pooled Street consensus
   53% (57% on Buy/Hold names), Cohen's κ = 0.08 ≈ no correlation. PASS reasons are
   consistently discipline-shaped (RSI overbought, failed breakout, no margin of
   safety) — it answers "buy now at this price?", the Street answers "attractive
   over 12 months?".
2. **Red-line clean:** zero APPROVEs on Street-Sell names (BGS, WU) in both batches.
3. **Ablation (consensus hidden): no parroting signal.** Approve-rate identical
   (3/32 both), overlap of approved names baseline∩ablation = 1 (NFLX). Run-to-run
   sampling variance is the same order as any ablation effect, so n=32 can't resolve
   a small anchoring effect — but the strong form ("Room = consensus echo") is ruled
   out by κ≈0 alone.
4. **DEF058** (PM prose verdicts, 22% pre-fix): fixed via prompt hardening + one-shot
   reformat retry; **0/64 incidence post-fix** (acceptance <2% met). Pre-fix batches
   kept in `results/runs_baseline-*.jsonl` as the incidence record.
5. **DEF059** (vLLM outage → deterministic fake APPROVEs): found live when the vLLM
   host went down mid-batch; fixed same-session (live PM failure now fails safe to
   PASS with an honest AMI-voiced reason), regression-tested.
6. **Compliance probes:** REJECT is unreachable live unless the PM first APPROVEs a
   blocked name (safety floor is veto-only) — MO ethics-probe and RIVN blocklist-probe
   both PASSed on market grounds. REJECT path remains covered by unit tests only.
7. **Respected-site spot-checks:** MarketBeat rates all six of our sell-leaning picks
   "Reduce" (validates the bucket); Zacks Rank diverges from Street consensus exactly
   where its earnings-revision model should (INTC #1 vs Street hold, NFLX #4 vs Street
   buy). TipRanks blocks automated access (HTTP 403) — excluded.
8. **Ops lesson:** benchmark drivers run ON melehost (docker-exec the rsync'd scripts
   inside `ami_api_alpha`, `--base-url http://localhost:8000`, copy JSONL back) — the
   Mac driver lost 13 ticker-runs to local network blips before this was corrected.
9. **Forward re-score:** every record carries a spot-price snapshot;
   `room_benchmark_report --baseline baseline2-2026-07-16 --forward` in 2–4 weeks
   computes Buy-vs-Hold forward returns.

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

---

## Three-arm experiment (2026-07-17, AT:R59) — 150 tickers, real social data

Saiful: *"run up the wall clock. take the time needed."* All three arms use the same 150-name
universe (`tickers_150.txt`), a fresh benchmark user per arm (defeats the 24h dedup), and the
driver runs **inside `ami_api_alpha`** against `localhost:8000` (CR035 ops lesson — a Mac-side
network blip cost 13 ticker-runs on 2026-07-16).

| Arm | Batch id | Street consensus in prompt | Social feed | Answers |
|---|---|---|---|---|
| **A — baseline** | `baseline150-2026-07-17` | visible | **live Adanos** | Room vs Street with everything real |
| **B — consensus ablated** | `ablconsensus150-2026-07-17` | **hidden** (`SUPPRESS_ANALYST_CONSENSUS=true`) | live Adanos | Does the Room parrot the Street rating it's fed? |
| **C — social ablated** | `ablsocial150-2026-07-17` | visible | **off** (`ADANOS_API_KEY=""` → synthetic path) | **Does the Social Analyst change any decisions?** — the question raised when auditing CR037 and unanswerable until the feed went live (DEF063) |

~8 h per arm, ~24 h total, sequential (the arms need different container env states).

Arm C costs **zero Adanos quota**: emptying the key short-circuits `fetch_live_sentiment` before
any HTTP call, and the warm cache is untouched — so restoring is a flag flip, not a re-warm.

**Restoration is mandatory after arm C**: `ADANOS_API_KEY` repopulated and
`SUPPRESS_ANALYST_CONSENSUS=false`, verified via `GET /v1/admin/config-check`. Both arms B and C
degrade live Alpha while running (fabricated sentiment / no Street view), so neither window may
be left open.

**Scoring:** A vs Street = the headline agreement number. A vs B = consensus anchoring. A vs C =
social influence. Prior noise floor to beat: **4/32 verdict flips (~12%)** between two identical
32-ticker runs — at n=150 a real effect needs to clear that, and 150 gives ~4.7× the paired
sample to resolve it with.
