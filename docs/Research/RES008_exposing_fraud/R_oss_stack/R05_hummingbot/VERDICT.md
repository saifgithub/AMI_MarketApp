# R05 — Hummingbot

**Repo:** github.com/hummingbot/hummingbot · surveyed 2026-09-20 as part of an 8-repo stack survey
(see `../../02_oss_stack_survey.md`).

## What it is

An open-source framework for building and deploying automated market-making and trading bots. It
ships a reference strategy, "pure market making" (PMM): place symmetric bid/ask limit orders
around the mid-price, refresh on a timer, collect the spread. The project frames itself as a
toolkit, not a guaranteed-profit system.

## Our verdict

**TESTABLE, BUT NOT NOVEL — parked, not promoted.** PMM is the one concrete, describable mechanism
among the six non-FinRL repos: "symmetric-spread market making nets positive PnL after fees and
adverse selection on liquid pairs" is specific enough to pre-register in principle. But it is
textbook market-microstructure theory with decades of academic literature already on spread
capture vs. adverse selection — testing it would not be a new finding, it would be re-deriving a
known result under our own cost/statistics discipline.

## Why this verdict, not a full test

Two things keep this out of the current batch rather than becoming a `C##`:

1. It is functionally the **same claim class as C06** (`NOT SUPPORTED`: "an AI grid/band robot
   earns passive income in any market") — a different mechanism (symmetric quotes vs. grid levels)
   answering the same underlying question retail viewers actually ask: *does an automated
   market-neutral bot make money for free?* Running it as a fresh `C##` would largely duplicate
   C06's finding rather than add one.
2. Building it to RES008's bar (fixed universe, block-bootstrap intervals, real costs, matched
   placebo, no Sharpe) is a heavier lift than its novelty currently justifies.

## Revisit if

- A specific high-reach YouTube video promotes Hummingbot's PMM by name with a claimed return —
  that would justify a `C##` sourced from the video (reach-driven, matching how C01–C08 were
  selected), likely framed as a C06 sequel rather than a standalone claim.
- We want a second, mechanistically distinct data point for the broader "automated bot = passive
  income" claim family before publishing a wrap-up episode on that whole family.

## Track record note (context only, not a verdict input)

~17k GitHub stars, Hummingbot Foundation (organisation-backed), ~51 active contributors/quarter,
actively maintained. No independent academic benchmark or notable publicised blowup found at
survey time; market-making generally carries known adverse-selection/inventory risk (general
market-microstructure literature, not specific to this project).
