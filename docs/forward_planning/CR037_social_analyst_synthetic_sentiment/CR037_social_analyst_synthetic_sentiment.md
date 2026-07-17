# CR037 — Social Media Analyst asserts synthetic sentiment as fact (gate it until CR024 lands)

**Status:** proposed · **Filed:** 2026-07-17 (AT:R59) · **Found by:** CR035 benchmark transcript audit
· **Related:** [CR024](../CR024_social_analyst_live_feed/) (live social feed, in_progress) ·
[CR038](../CR038_macro_fed_scaffolding_asserted_as_fact/) (same failure mode, macro/Fed fields) ·
DEF052–055 (the truthfulness batch that fixed this for every *other* analyst)

## What

The Social Media Analyst is the only one of the four data-gathering analysts with no live
feed, and it states its synthetic inputs to the user as fact. Either mute the agent until
CR024 connects a real source, or make its fallback structurally unable to assert fiction.

## Why — measured evidence (2026-07-16/17, 32-ticker `baseline2` batch)

| Finding | Measurement |
|---|---|
| No live feed | Live NVDA profile on melehost: `data_source=yfinance_live`, `technicals_source=live`, `news_source=live`, **`social_source=None`** |
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

## Options

- **(a) Gate the agent off until CR024 — recommended.** 12→11 agents; the Room stops asserting
  fictional sentiment; measured verdict influence is ~0 so nothing of value is lost; ~8% cheaper
  and faster. Needs an env flag + a Room-phase skip + the UI tolerating 11 speakers.
- **(b) Prioritize CR024** (real Reddit/Adanos feed) and leave the agent live meanwhile —
  keeps asserting fiction until it ships.
- **(c) Harden the fallback prose only** — cheapest, but honesty still depends on prompt
  obedience, which measures at 28% here. Weakest option; see CR038 for the same argument.

## Acceptance

1. Zero unhedged synthetic-sentiment assertions over a ≥30-run batch (measure with the CR035
   harness — the transcript audit script is the check).
2. Under (a): approve-rate change vs `baseline2` stays inside the measured noise floor
   (4/32 verdict flips ≈ 12%, no systematic direction) — i.e. muting Social doesn't move the
   Room's decisions beyond sampling noise.
3. Under (a): re-enabling is a single flag flip once CR024 lands.

## Risks

- Muting an agent changes the 12-agent product story ("your 12-agent analyst team"). Product
  call for Saiful, not an engineering one — the Room UI would show 11 seats until CR024.
- At n=32 the benchmark can only detect large effects; a small influence from Social can't be
  ruled out (see CR035 report's power note).
