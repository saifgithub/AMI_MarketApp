# R01 — AI Hedge Fund (virattt/ai-hedge-fund)

**Repo:** github.com/virattt/ai-hedge-fund · surveyed 2026-09-20 as part of an 8-repo stack survey
(see `../../02_oss_stack_survey.md`).

## What it is

A multi-agent LLM system that simulates a hedge fund research desk: persona agents modelled on
well-known investors (Buffett/Munger/Graham/Lynch-style reasoning) plus functional agents
(fundamentals, technicals, sentiment, risk, portfolio manager) debate a ticker and reach a
consensus buy/hold/sell call. The README states it plainly: **"a proof of concept... to explore
the use of AI to make trading decisions."** It does not place real trades.

## Our verdict

**NO TESTABLE CLAIM.** Not `DISPROVED`, not `NOT SUPPORTED` — those verdicts are for a claim we
tested and it failed. This one has no fixed recipe to test in the first place: the LLM personas'
reasoning is not a deterministic rule set, so there is nothing to pre-register. Re-running the
same prompts twice would not even reproduce the same trade calls.

## Why this verdict, not a test

RES008's method (`PREREG_COMMON.md`) requires a recipe specific enough to commit to *before*
running it — an indicator, a threshold, an entry/exit rule. An LLM persona "debating" a stock has
no such fixed mechanism; testing it would mean testing our own choice of prompt and model, not the
project's claim, because the project makes no claim about outcomes.

## Revisit if

- The project ships a benchmarked backtest with specific, stated returns (it does not today).
- A YouTube creator builds a *specific, fixed* trading rule on top of this framework and claims a
  result — that would be a new C## candidate sourced from the video, not from this repo.

## Track record note (context only, not a verdict input)

~63k GitHub stars, solo creator plus community contributors, no known live-trading disclosure or
independent academic evaluation found at survey time.
