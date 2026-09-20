# R04 — NautilusTrader

**Repo:** github.com/nautechsystems/nautilus_trader · surveyed 2026-09-20 as part of an 8-repo
stack survey (see `../../02_oss_stack_survey.md`).

## What it is

A Rust-native, event-driven trading engine spanning backtesting, simulation, and live execution
across asset classes and venues, positioned toward institutional/professional quant users.
Example indicators and demo backtests ship with the docs but are explicitly labelled educational,
not production strategies.

## Our verdict

**NO TESTABLE CLAIM.** No P&L figures, Sharpe ratios, or profitability claims anywhere in the
project's own material. Same shape as Freqtrade (R02) and Jesse (R08): an execution engine, not a
strategy — the user supplies the logic that runs identically in backtest and live.

## Why this verdict, not a test

The engine's job is to run a strategy faithfully and fast; it makes no assertion about whether any
particular strategy run on it would make money. Testing "does NautilusTrader work" would be a
software-correctness question, not a trading-edge question, and out of scope for this series.

## Revisit if

- A specific strategy built on NautilusTrader is publicised with a claimed live or backtested edge
  — that claim, not the engine, would be the candidate.
- The company behind it (Nautech Systems) publishes institutional performance data (none found at
  survey time; they offer managed/institutional services alongside the OSS engine, which suggests
  real usage but no public disclosure was located).

## Track record note (context only, not a verdict input)

Actively maintained, company-backed. No independent published evaluation found at survey time.
