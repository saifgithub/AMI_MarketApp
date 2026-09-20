# R03 — CCXT

**Repo:** github.com/ccxt/ccxt · surveyed 2026-09-20 as part of an 8-repo stack survey (see
`../../02_oss_stack_survey.md`).

## What it is

A pure exchange API wrapper — one library, unified interface across 100+ crypto exchanges (and
some traditional venues), for market data and order execution. No strategy, no signal, no
indicator of any kind. It is explicitly a developer tool for "coders, technically-skilled
traders, data-scientists" to build on.

## Our verdict

**NO TESTABLE CLAIM.** The clearest case of the eight. There is no mechanism to fail or hold —
CCXT does not decide what to trade or when; it only moves an order once something else has
decided.

## Why this verdict, not a test

Nothing about "is this API wrapper correct about the market" is a coherent question. It is
infrastructure in the most literal sense: connective tissue, not a claim.

## Revisit if

Nothing plausible would move this out of "no testable claim" — a connector library cannot acquire
an edge claim short of the project itself starting to ship trading logic, which is outside its
stated scope. Kept as a folder only for completeness of the 8-repo batch, not because a revisit is
expected.

## Track record note (context only, not a verdict input)

~44k GitHub stars, 900+ contributors, organisation-backed, actively maintained. Not applicable to
evaluate for "edge" since it is not a strategy.
