# R08 — Jesse

**Repo:** github.com/jesse-ai/jesse · surveyed 2026-09-20 as part of an 8-repo stack survey (see
`../../02_oss_stack_survey.md`).

## What it is

A Python crypto trading framework for defining, backtesting, optimising, and live-trading
strategies, with an "Optimize Mode" (parameter tuning) and a "JesseGPT" assistant. Docs illustrate
a "Golden Cross" (moving-average crossover) example strategy, shipped with no performance numbers
attached.

## Our verdict

**NO TESTABLE CLAIM.** Same shape as Freqtrade (R02) and NautilusTrader (R04): a framework, not a
strategy claim. The project's own disclaimer is explicit — "for educational purposes only... USE
AT YOUR OWN RISK... no responsibility for your trading results," identical in substance to
Freqtrade's. The Golden Cross example is a mechanism (MA crossover entry/exit) concrete enough to
test in principle, but the project asserts no result for it — there is nothing to falsify, only a
generic, decades-old technical-analysis pattern with no project-specific claim attached.

## Why this verdict, not a test

Testing "does a moving-average crossover work" is not testing Jesse — it is testing a textbook
indicator that predates this project by decades and is not what makes Jesse distinct. If MA
crossover specifically becomes worth testing, it should be sourced from a YouTube claim that
promotes it by name with a stated result, not from this framework's illustrative docs example.

## Revisit if

- A high-reach video promotes a *specific* Jesse strategy file with a claimed backtest result —
  that recipe, not the framework, becomes the C## candidate.
- "JesseGPT" (LLM-assisted strategy generation) is promoted with a specific claimed edge — that
  would functionally resemble **C02** ("a chatbot wrote me a profitable strategy," already
  `DISPROVED`) with Jesse as the execution layer rather than a generic broker/exchange API; if the
  same underlying finding (looks profitable as a screenshot, fails net of costs on a holdout) is
  expected to hold, a fresh test would mostly confirm a known result rather than discover one.

## Track record note (context only, not a verdict input)

~6.5k GitHub stars, actively maintained, smaller community-driven organisation (`jesse-ai`) than
the larger crypto-bot projects on this list. No independent academic evaluation or notable
publicised blowup found at survey time.
