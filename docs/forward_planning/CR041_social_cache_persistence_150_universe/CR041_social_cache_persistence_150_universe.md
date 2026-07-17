# CR041 — Durable 30-day social sentiment cache + 150-ticker benchmark universe

**Status:** done (cache live in `alpha-2026-07-17-3`; 150/150 warmed; acceptance verified) · **Filed:** 2026-07-17 (AT:R59) · **Requested by:** Saiful ("make it 150
calls, and extend our 32 to 150. and make sure we cache all calls so we can re use it while we
test. set a staleness value to 30 days")
· **Depends on:** [DEF063](../../defect/DEF063_adanos_alpha_vantage_keys_never_forwarded/) (feed
now live) · **Related:** [CR035](../CR035_room_benchmark/) (benchmark harness),
[CR037](../CR037_social_analyst_synthetic_sentiment/) (fallback fabrication)

## What

1. Move the Adanos sentiment cache from in-process memory to Postgres, TTL 30 days.
2. Expand the CR035 benchmark universe from 32 → 150 tickers.
3. Warm the cache with 150 Adanos calls, burst-aware, inside the free-tier budget.

## Why — the requested TTL is impossible with today's cache

`social_context.py` caches in a plain `dict` on the `_AdanosSource` instance
(`self._cache`, `_CACHE_TTL = 86_400`). That cache **dies with the process**. The api-alpha
container was recreated 4× on 2026-07-17 alone (promotions + the CR035 ablation flag flips), and
there is **no `/data` volume mounted on api-alpha** — only `postgres_data` and `redis_data`.

So a 30-day in-memory TTL would be a fiction: each restart re-burns the whole universe against a
**250 calls/month** budget. At 150 tickers, two restarts = 300 calls = budget blown, and the
Social Analyst silently reverts to inventing sentiment (CR037) with no signal. The durable cache
isn't a nice-to-have here; it's what makes the 150-ticker plan arithmetically possible.

Redis is referenced only in `config.py` and is otherwise unused by the app — Postgres is the
durable, inspectable choice (we can query exactly what's cached and how old it is), and alembic
is already the schema path.

## Live budget facts (measured 2026-07-17 from Adanos response headers)

| Header | Value |
|---|---|
| `x-ratelimit-limit-monthly` | 250 |
| `x-ratelimit-remaining-monthly` | 246 |
| `x-ratelimit-used-monthly` | 4 |
| `x-ratelimit-reset-monthly` | 2026-08-17T07:12:05Z |
| **`x-ratelimit-limit-burst`** | **100** (short window; resets on the hour) |
| `x-account-type` | free |

**The burst cap of 100 is new information and it constrains the warm-up**: 150 tickers cannot be
fetched in one pass. Warming must chunk (~95 per burst window) and wait for the reset. These
headers also give us live budget telemetry — worth logging on every call rather than guessing.

Budget after warming: 246 − 150 = **~96 calls of headroom** this cycle (resets 2026-08-17).
Within the 30-day TTL every benchmark re-run is **0 calls**, which is exactly the point.

## Scope

**Durable cache**
- `SocialSentimentCacheRow` in `backend/app/db/models.py` — `ticker` PK, JSON payload,
  `fetched_at`, `found` flag. Alembic migration on head `e2f3a4b50016`.
- `social_context.py`: read-through cache against the table; keep the in-process dict as an L1
  in front of it (avoids a DB hit per convene).
- **Cache negatives too.** A `found: false` ticker must not re-burn a call every convene —
  today's code returns `None` without caching, so an uncovered ticker costs a call *per run*.
  This is a live quota leak independent of the TTL change.
- `social_cache_ttl_days: int = 30` (env `SOCIAL_CACHE_TTL_DAYS`) in `config.py` + forwarded in
  `docker-compose.yml` (CR040's parity test enforces this — it will fail the build otherwise).
- Log `x-ratelimit-remaining-monthly` on every live fetch; surface the gate in
  `/v1/admin/config-check` so budget exhaustion is visible, not silent (CR040 P2).

**150-ticker universe**
- Screen a ~200-name candidate pool via yfinance `recommendationMean`, keep 150 balanced across
  buy / hold / sell-leaning, mixed sectors, incl. sparse-coverage probes.
  `docs/forward_planning/CR035_room_benchmark/tickers_150.txt`.

**Warm-up script**
- `backend/scripts/social_cache_warm.py` — burst-aware (≤95 per window, sleep to reset), stops
  hard at a `--max-calls` cap, prints remaining monthly quota per chunk, resumable (skips
  already-cached tickers). Runs **on melehost** (CR035 ops lesson).

## Wall-clock warning (needs a decision before the next batch)

At ~3 min/convene, **150 tickers ≈ 7.5 h per benchmark batch** (1,800 vLLM calls); a
baseline+ablation pair ≈ 15 h. The Adanos side is cheap and cached; the vLLM side is the real
cost. Options: run baseline-only, run overnight, or subset the Room benchmark while keeping the
150-name cache for other uses.

## Acceptance

1. Cache survives a container recreate: warm a ticker → `docker compose up -d api-alpha` →
   same ticker resolves from cache with **0** new Adanos calls (verify via
   `x-ratelimit-used-monthly` unchanged).
2. TTL honoured: a row older than `SOCIAL_CACHE_TTL_DAYS` refetches; a fresh one never does.
3. Negative results cached — an unknown ticker costs exactly one call per 30 days, not one per
   convene.
4. Warm-up completes 150 tickers without exceeding the burst cap or the monthly budget; final
   `x-ratelimit-used-monthly` ≤ 160.
5. `tickers_150.txt` exists with the bucket balance documented.
6. CR040 parity test passes (proves `SOCIAL_CACHE_TTL_DAYS` is forwarded).

## Risks

- 150 warm calls leave ~96 headroom until 2026-08-17. A cache wipe (DB volume loss, or a TTL
  bug) after warming cannot be re-warmed this cycle — the table is now budget-critical state.
- Sentiment frozen for 30 days is *stale by design*: fine for benchmark reproducibility, wrong
  for a live user reading "1,725 mentions" that is a month old. If the Room ships to users on
  this cache, the agent must say how old the data is — otherwise it's CR038's failure mode with
  real numbers. **Recommend: 30d TTL for benchmark tickers, shorter for user-initiated convenes**
  — or at minimum, render the age.


---

## Outcome (2026-07-17, verified)

**Warm-up:** 150/150 cached — **126 covered, 24 no-coverage**, ~153 calls.
Budget: **89/250 remaining**, resets 2026-08-17. Re-runs are free for 30 days.

**Acceptance #1 (the whole point) — verified by measurement, not assertion:**
`x-ratelimit-used-monthly` 162 → `docker compose up -d --force-recreate api-alpha` →
resolved TSLA (939 mentions), NVDA (1,725), AAPL (1,988) in the **fresh** container →
used-monthly 163, of which 1 was the verification probe itself. **Quota spent by 3 lookups
across a container recreate: 0.** Under the old in-memory cache this same restart cost 3 calls;
across a 150-ticker universe it cost 150.

**Acceptance #3 (negative caching):** 24 tickers have no Reddit coverage and are cached as
`found=false` — previously each cost a live call *per convene*, forever.

**Two bugs found in the warm script by reading its own output against the logs:**

1. It reported network timeouts as *"no coverage (negative cached)"* — conflating "Adanos has no
   data" (a cached result) with "the call failed" (retryable, uncached). PM and RBLX were
   mislabelled this way. Now distinguished by checking whether a cache row actually landed.
2. Budget arithmetic compared a *refreshed* `monthly_remaining` against a *cumulative* `spent`,
   so it declared "monthly budget exhausted" with **99 calls left**, silently skipping LYFT, NKE
   and TSLA. Now tracked per-probe. Both fixed; the 5 stragglers re-warmed.

Note the first bug is P2 (silent confident degradation) in miniature — a script reporting a
failure as a finding. The fix was the same shape: distinguish the states structurally instead of
inferring from a `None`.

**Coverage reality:** 24/150 (16%) of the universe has no Reddit sentiment at all. Those names
fall to CR037's fabrication path on every convene — the fallback isn't an edge case, it's 1 in 6
of this universe.
