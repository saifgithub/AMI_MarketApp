# R02 — Numerai

Surveyed 2026-09-20 as part of the broader market-ML sweep prompted by the wundernn.io request.
Cross-reference: `../../03_market_ml_landscape_survey.md`, `TRACKER.md` row B14.

## What it is

A crowd-sourced quant hedge fund. Thousands of data scientists train models on obfuscated financial
features and submit predictions; Numerai blends submissions into a "Meta Model" that drives an
actual, operating market-neutral equities fund. Contributors can stake NMR (its own cryptocurrency)
on their model's live performance via a "Meta Model Contribution" (MMC) score, earning or losing
stake based on whether their model helps or hurts the live Meta Model.

## Our verdict

**A REAL, AUDITED PERFORMANCE CLAIM — but not one RES008's method can test, and not a "debunk"
candidate.** Reported (third-party-sourced, not self-published-only): 2024 net return 25.45% at a
2.75 Sharpe ratio (one down month); 2025 net return of 8% through the period reported, ahead of the
PivotalPath Equity Quant Index's 3%; AUM grown from ~$60M to ~$550M over three years; J.P. Morgan
extended up to $500M of capacity in 2025. This is a live fund with institutional counterparties, not
a screenshot or a backtest — the closest thing on our list to an actual verified track record.

This is the inverse of everything else RES008 has surveyed: not a debunk-fodder claim with thin or
staged evidence, but the one case where "crowd-sourced ML finds market edge" appears to have
survived years of live, real-money operation with institutional-grade oversight (JPM's capital
allocation implies real due diligence). It does not belong in the same bucket as the YouTube claims
or the OSS-stack repos.

## Why this verdict, not a test

- Numerai's own edge is the live, secret blend of thousands of submitted models plus their own
  proprietary allocation/risk layer — none of which is public. There is no reproducible recipe to
  pre-register; the "model" is Numerai's undisclosed meta-process, not any single public strategy.
- The performance numbers are third-party-reported (press coverage, Messari, hedgefund trackers),
  not from a source we can independently re-derive with our own bootstrap/cost methodology — testing
  it would mean auditing a live fund, a different kind of project entirely.
- Sharpe ratio appears in the sourcing (2.75) — exactly the statistic `PREREG_COMMON.md` bans from
  our own verdicts. We are not treating that number as if it clears our bar; we're noting it only as
  third-party context on the fund's own reputation, per this file's "context only" convention.

## Revisit if

- A future episode wants a "here's a crowd-sourced ML approach that's actually held up" counterpoint
  segment — useful precisely *because* the series otherwise debunks similar-sounding claims; fairness
  cuts both ways (see `00_claim_landscape.md`'s "what looked sound — and we say so" convention).
  Numerai is the strongest available example of that.
- Numerai or a contestant ever publishes a specific, reproducible strategy/feature recipe (rather
  than "submit to our proprietary blend") — that would be a genuinely new, testable claim.

## Track record note (context only, not a verdict input)

Nothing here reads as fraud. If anything this is evidence that the "measurable edge" bar RES008
applies is achievable — just apparently not by any of the YouTube claims, OSS repos, or open
recruiting competitions surveyed so far. Worth remembering as a calibration point: the series is not
claiming ML-for-markets never works, only that the specific claims tested so far don't hold up to
scrutiny.
