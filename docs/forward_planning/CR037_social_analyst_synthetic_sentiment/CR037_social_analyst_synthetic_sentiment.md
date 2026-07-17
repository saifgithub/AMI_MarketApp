# CR037 — Social Media Analyst asserts synthetic sentiment as fact (fallback must not fabricate)

**Status:** proposed · **Filed:** 2026-07-17 (AT:R59) · **Found by:** CR035 benchmark transcript audit
· **Blocked-by / precedes:** **[DEF063](../../defect/DEF063_adanos_alpha_vantage_keys_never_forwarded/)** —
fix that first · **Related:** [CR024](../CR024_social_analyst_live_feed/) (live Adanos feed — *shipped*) ·
[CR038](../CR038_macro_fed_scaffolding_asserted_as_fact/) (same failure mode, macro/Fed fields) ·
DEF052–055 (the truthfulness batch that fixed this for every *other* analyst)

> **Premise correction (2026-07-17).** This CR was originally filed claiming "CR024 is pending,
> so the agent has no feed". **That was wrong** — Saiful challenged it, and he was right. CR024
> *did* deliver the Adanos integration (`backend/app/services/social_context.py`) and the key is
> provisioned in `infra/alpha.env`. The feed is dark only because `docker-compose.yml` never
> forwards `ADANOS_API_KEY` into the container → **DEF063**. Once DEF063 lands, the agent gets
> real Reddit sentiment and the "mute it" option below is moot. What survives is the narrower
> question this CR now owns: what the agent says when the feed is *legitimately* unavailable
> (API down, 250/month budget exhausted, ticker not covered).

## What

The Social Media Analyst states unavailable-data scaffolding to the user as fact. Fix the
fallback so it is structurally incapable of asserting fiction — regardless of why the feed is
missing.

## Why — measured evidence (2026-07-16/17, 32-ticker `baseline2` batch)

All measurements below were taken while the Adanos feed was dark (DEF063), i.e. they describe
the **fallback path** — which is exactly this CR's subject.

| Finding | Measurement |
|---|---|
| Feed inactive (cause: DEF063, not missing code) | Live NVDA profile on melehost: `data_source=yfinance_live`, `technicals_source=live`, `news_source=live`, **`social_source=None`** |
| Inputs carry no information | Across the 32-ticker universe `sentiment_tone` takes **2 values** (`moderately bullish` 22, `mixed` 10); tone/score/trend seeded off `crc32(ticker)` — a deterministic function of the ticker's *name*, not the company |
| Stated as fact | **23/32** social messages state the synthetic values with **no hedge** — the profile block labels them "(illustrative)" / "NOT a live social feed", the LLM drops the qualifier ~72% of the time |
| Adds nothing to the verdict | PM cites social language **0/32**. Research Manager 4/32, Bull 11/32, Bear 7/32 |
| Largely re-reports what the room already has | **19/32** social messages cite the Street consensus or price target back at the room |
| Cost | 1 of 12 LLM calls ≈ 8% of a convene's latency/spend (~15–20 s of ~3 min) |

Example (NVDA, unhedged, hash-seeded): *"Social media chatter remains moderately bullish with
elevated intensity, suggesting retail investors are maintaining long-term conviction…"*

This is the DEF052–055 failure mode (fabricated inputs asserted as fact) surviving in the one
agent that batch didn't re-audit. Simulation-only doesn't excuse it: the user cannot tell this
sentence is fiction.

## Sequencing

**DEF063 first** (one compose line + promote) — that turns the feed on and makes the common case
real. This CR then handles the residual: Adanos is a 250-calls/month free tier with a 24h cache
(~8 distinct tickers/day), so a *cold* ticker will still hit the fallback regularly. The
fallback is not a rare edge case; it's the daily path for anything outside the cache.

## Options (for the fallback path)

- **(a) Remove the synthetic fields at source — recommended.** When `social_source` isn't live,
  omit `sentiment_tone`/`sentiment_score`/`mention_trend`/`influencer_take` from the profile
  entirely and tell the agent to say it has no sentiment data for this ticker today. The agent
  cannot assert what it was never handed — same argument, and same fix shape, as CR038(a).
- **(b) Skip the agent's turn when the feed is unavailable.** 12→11 speakers for that run;
  measured verdict influence is ~0 (PM cites social 0/32) so nothing of value is lost, ~8%
  cheaper. Changes the "12-agent team" product story per-run — Saiful's call, not engineering's.
- **(c) Harden the fallback prose only** — rejected: honesty still depends on prompt obedience,
  which measures at 28% here and ~30% for macro/Fed (CR038). DEF058 showed the same model
  ignoring an equally emphatic instruction ~22% of the time.

## Acceptance

1. Zero unhedged synthetic-sentiment assertions over a ≥30-run batch, measured with the CR035
   harness transcript audit (today's baseline: 23/32 unhedged).
2. With the feed live post-DEF063: the agent's message cites real Reddit sentiment and
   `social_source=live`.
3. With the feed forced unavailable: the agent says so plainly; no invented tone/intensity/trend
   appears anywhere in the transcript.
4. Verdict movement vs `baseline2-2026-07-16` stays inside the measured noise floor (4/32 flips
   ≈ 12%, no systematic direction).

## Risks

- At n=32 the benchmark only detects large effects; a small influence from Social can't be ruled
  out (see CR035 report's power note).
- Option (b) makes the roster size vary run-to-run, which the Room UI and the "12-agent analyst
  team" positioning both assume is fixed.
- Real Adanos data will change verdicts in ways this benchmark hasn't measured — re-run
  `baseline2` after DEF063 to re-establish the reference.
