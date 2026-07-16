# DEF058 — PM verdict JSON fails to parse in ~22% of live Room runs (silent PASS fallback)

**Filed:** 2026-07-16 (AT:R59) · **Status:** open · **Found by:** CR035 Room-vs-Street benchmark

## Symptom

7 of 32 baseline benchmark convenes (NVDA, META, DAL, SLB, UNH, PEP, CPB) produced a
verdict with `overridden_from_llm: true` and reason:

> "Portfolio Manager did not return a machine-readable verdict; defaulting to no trade
> for safety."

`_parse_pm_verdict` (`backend/app/services/room_runner.py`) could not extract the JSON
`{action, narration, …}` block from the PM's raw output, so `PASS` was substituted.

## Why it matters

The fail-safe direction is correct (never fabricate an APPROVE), but at a ~1-in-5 rate
the user-visible verdict frequently is **not the PM's actual decision** — the debate's
conclusion is silently discarded and the Room reads as more conservative than it is.
It also contaminated the CR035 benchmark (those runs are excluded from agreement
scoring as `pm_parse_fallback`).

## Suspected causes (unverified)

1. PM stream capped at `max_tokens=600` — long narration before the JSON block gets
   the JSON tail truncated.
2. Prompt format instruction losing to the narration ask on Gemma (`ami-llm`) — model
   emits prose-only endings under some debate contexts.
3. Parser strictness — `_parse_pm_verdict` may reject near-miss JSON (trailing commas,
   fenced code blocks, single quotes).

## Repro

`backend/scripts/room_benchmark.py` against alpha; ~22% incidence over 32 runs on
2026-07-16 (batch `baseline-2026-07-16`, raw records in
`docs/forward_planning/CR035_room_benchmark/results/`).

## Acceptance for a fix

- Parse-failure rate < 2% over a ≥30-run batch, measured by the same benchmark.
- No weakening of the fail-safe: unparseable output still never yields APPROVE.
