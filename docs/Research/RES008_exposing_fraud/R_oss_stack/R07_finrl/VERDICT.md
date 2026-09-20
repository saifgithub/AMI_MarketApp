# R07 — FinRL (AI4Finance-Foundation)

**Repo:** github.com/AI4Finance-Foundation/FinRL · surveyed 2026-09-20 as part of an 8-repo stack
survey (see `../../02_oss_stack_survey.md`).

## What it is

A deep reinforcement-learning framework for finance: environments, data pipelines, and DRL
algorithms (A2C, DDPG, PPO, SAC, TD3, ensemble) for training a user's own trading agent. The
framework itself claims no fixed edge — positioned as "the first open-source framework for
financial RL," for education and research.

## Our verdict

**TESTABLE, MIXED EVIDENCE ALREADY EXISTS — the strongest candidate of the eight, still not
promoted to `C##`.** Unlike the other seven repos, FinRL's own ecosystem (FinRL-Meta, a NeurIPS
Datasets & Benchmarks workshop paper; the annual FinRL Contest) publishes specific, falsifiable
numbers on a defined benchmark: an ensemble DRL agent Sharpe ratio of 1.53 vs. the DJIA's own
Sharpe of 1.32 over 2020-07→2022-03, with individual algorithm runs (A2C, TD3) reporting even
higher Sharpes and annual returns in some published configurations. This is the one repo-sourced
claim specific enough — algorithm, universe (DJIA-30), date range, reward function — to
pre-register and attempt to reproduce.

We are not running that test right now, for two reasons:

1. **The claim as published does not clear our own pre-registration bar.** `PREREG_COMMON.md`
   bans Sharpe ratios entirely and bans annualised figures from windows shorter than three years —
   the headline 2020-07→2022-03 window is under two years. Reproducing FinRL's claim on our terms
   would mean rebuilding it from scratch (fixed universe, block-bootstrap interval, real
   transaction costs, no Sharpe, win-rate/return-vs-placebo framing instead) — a materially
   different and larger undertaking than reading a claim off a video.
2. **The claim already contradicts itself across FinRL's own history.** Later FinRL Contest years
   are reported to show competing teams' strategies achieving better risk-adjusted returns but
   *worse* raw profitability than the DJIA baseline — i.e., the "DRL beats the index" finding does
   not hold consistently even within the project's own benchmarking effort.

## Why this verdict, not a full test yet

Point 2 is arguably the more interesting finding on its own: a benchmark that flips sign across
its own contest cycles is doing some of RES008's work for us, publicly, for free. An episode built
around "the most rigorous of the eight benchmarks already disagrees with itself year over year" may
be more useful than spending compute to add one more data point that would land somewhere in the
range already bracketed by the published contest results.

## Revisit if

- We want to actually run a from-scratch DRL-vs-DJIA test under RES008's own discipline as a
  flagship "we rebuilt an academic AI-trading benchmark under honest rules" episode — this is the
  most defensible use of engineering time among the eight repos, but a real project (data
  pipeline, DRL training compute, multiple seeds) rather than a desk review.
- A specific FinRL Contest year's results get picked up and mis-cited by a YouTube creator as
  proof of a durable edge — that mis-citation becomes the new C## claim, sourced from the video, in
  the usual pattern.

## Track record note (context only, not a verdict input)

Actively maintained, backed by the AI4Finance Foundation, published in peer-reviewed/workshop
venues (NeurIPS Datasets & Benchmarks track, arXiv) with an ongoing annual contest — the strongest
academic footprint of the eight, and the only one with anything resembling independent
year-over-year replication (which is precisely what surfaced the self-contradiction above).
