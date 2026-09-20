# R02 — Freqtrade

**Repo:** github.com/freqtrade/freqtrade · surveyed 2026-09-20 as part of an 8-repo stack survey
(see `../../02_oss_stack_survey.md`).

## What it is

An open-source crypto trading bot framework: exchange connectivity, a backtesting engine,
hyperparameter optimisation ("hyperopt"), and dry-run/live execution. Strategies are Python
classes the user writes; the project ships no default strategy with claimed returns.

## Our verdict

**NO TESTABLE CLAIM.** The project's own docs carry an explicit disclaimer — "for educational
purposes only... USE AT YOUR OWN RISK... no responsibility for your trading results." There is no
recipe here to test: it is an engine, not a strategy.

## Why this verdict, not a test

Same reasoning as R03/R04/R08: an execution/backtest framework is not wrong or right about the
market, it just runs whatever rule a user supplies. Testing Freqtrade itself would mean inventing
a strategy and testing that invention — a different, much larger project than reading a claim off
a video.

## Revisit if

- A specific, high-reach YouTube video shows a *particular* Freqtrade strategy file with a claimed
  backtest result. That strategy's rule set becomes the candidate for a new C##, sourced from the
  video, not from the framework.
- Community-published strategy repos (external to Freqtrade core) are named directly with claimed
  live results worth checking — noted at survey time that scattered blog posts exist (one claiming
  "2509% profit" backtest) but these are third-party claims, not the project's, and backtest-vs-live
  divergence is itself a recurring topic in the project's own issue tracker.

## Track record note (context only, not a verdict input)

~54k GitHub stars, organisation-backed (`freqtrade` GitHub org), actively maintained with frequent
releases. No formal independent academic evaluation found at survey time.
