# 02 — Open-source trading-stack survey: is there an edge to test?

Surveyed 2026-09-20, at Saiful's request, from a list of 8 repos he framed as a stack —
**data → strategy → backtest → risk → execution → agent**. Unlike `00_claim_landscape.md`, these
are not YouTube claims with a measured reach; they are named open-source projects. The question is
narrower than "is this popular" — it is **does the project itself assert, or ship, a specific,
falsifiable trading edge** that RES008's method (placebo or buy-and-hold, net of costs, pre-
registered) could test. Most infrastructure has no such claim by design: a connector or an
execution engine is not wrong or right about the market, it just moves orders. Testing it would be
testing our own arithmetic, which is the C04/C05 mistake in reverse.

Method: read each project's own README/docs (not third-party blog claims about it) for (a) what it
is, (b) whether it states or bundles a specific edge claim, (c) whether a concrete recipe exists
inside it tight enough to pre-register, (d) any independent track record.

## Findings

| Repo | What it is | Edge claim from the project itself | Concrete recipe inside? | Verdict |
|:--|:--|:--|:--|:--|
| AI Hedge Fund (virattt) | Multi-agent LLM personas (Buffett/Munger/Graham-style + functional agents) debate to a buy/hold/sell call. Explicitly "a proof of concept... to explore the use of AI," no live execution. | None. | No — LLM reasoning is not a fixed rule set; nothing to pre-register. | **No testable claim.** |
| Freqtrade | Crypto bot framework: exchange connectivity, backtest engine, hyperopt, dry-run/live. | None — explicit "educational... USE AT YOUR OWN RISK" disclaimer. No bundled strategy ships with claimed returns. | No — strategies are user-written; the framework itself has no strategy content. | **No testable claim.** (A specific third-party strategy built on it would be a separate, new claim — not this repo.) |
| CCXT | Exchange API wrapper unifying 100+ venues, 8 languages. | None — pure connector, no strategy surface at all. | No. | **No testable claim.** Clearest case of the eight. |
| NautilusTrader | Rust-native event-driven backtest/live execution engine. | None — example indicators/backtests are explicitly labelled educational, not production strategies. | No — same shape as Freqtrade: engine, not a strategy. | **No testable claim.** |
| Hummingbot | Market-making/trading-bot framework; ships a reference "pure market making" (PMM) strategy — symmetric bid/ask around mid-price, collect the spread. | None — framed as a toolkit, not a profit guarantee. | Partially — PMM's mechanism is concrete enough to pre-register ("symmetric-spread MM nets positive PnL after fees/adverse selection on liquid pairs"). | **Testable, but not novel.** Textbook market-microstructure mechanism, decades of academic literature already exists on spread-capture vs. adverse selection; would not be a new finding, and per PREREG_COMMON's own statistics discipline (no Sharpe, block-bootstrap intervals, real costs) is a heavier build than its novelty justifies right now. |
| Eliza / elizaOS | General-purpose AI agent framework (chat, memory, plugins, wallet ops) — not trading-specific. | None in the framework itself. | No — trading logic would be entirely user/plugin-supplied. | **No testable claim.** Separately: the adjacent `ai16z`/ELIZAOS token (branded "autonomous AI trading agent") is the subject of a federal class-action alleging it was manually operated and misrepresented as self-investing, with the token down >99.9% from peak. That is a **token/marketing fraud story**, not a strategy-performance claim, and it is about the token launch, not the open-source framework's code. Worth a line in a future "how to spot a wrapped fraud" episode, not a pre-registration. |
| FinRL (AI4Finance-Foundation) | Deep-RL framework for finance: environments, data pipelines, DRL algorithms (A2C/DDPG/PPO/SAC/TD3/ensemble) for training a user's own agent. | The framework claims no fixed edge, but its own published papers (FinRL-Meta, NeurIPS Datasets & Benchmarks workshop; annual FinRL Contest) report specific numbers on a defined benchmark: an ensemble DRL agent Sharpe 1.53 vs. DJIA's own Sharpe 1.32 over 2020-07→2022-03; individual runs report even higher Sharpes. Later contest years reportedly show *worse* raw profitability than the DJIA baseline despite better risk-adjusted figures. | Yes, partially — algorithm, universe (DJIA-30), date range and reward function are documented and reproducible from the papers. | **Testable, mixed evidence already exists.** This is the one repo on the list with an actual quantified, source-cited claim. But it is a single historical window, contradicted by the project's own later contest results, and RES008's statistics discipline explicitly bans Sharpe ratios and annualised figures from short windows — the claim as published does not even clear our own pre-registration bar without being rebuilt on our terms (fixed universe, block-bootstrap interval, real costs, no Sharpe). |
| Jesse | Crypto strategy framework: define/backtest/optimize/live-trade; ships a "Golden Cross" (MA crossover) example. | None — explicit "educational... USE AT YOUR OWN RISK" disclaimer, same as Freqtrade. The example ships with no performance numbers. | Mechanism is concrete (MA crossover) but carries no claim to falsify — it is textbook technical analysis, not an assertion the project makes about itself. | **No testable claim.** MA crossover as a generic mechanism is already well-covered ground, not specific to Jesse. |

## What this means for RES008

Six of eight are **pure infrastructure** — connectors, engines, and agent scaffolding that carry no
edge claim because they are not in the business of claiming one; they are tools other people's
strategies run on. Testing them would mean inventing a strategy ourselves and testing *that*, which
is a different (and much bigger) project than the read-a-claim-off-a-video model this series is
built on.

Two carry something concrete enough to name:

- **Hummingbot's PMM** is a real, describable mechanism, but it is a well-studied strategy class
  (spread capture vs. adverse selection), not a claim this project makes about itself. If ever
  tested, it competes for a slot against every other "market making earns passive income" claim —
  which is functionally **the same claim class as C06** (already `NOT SUPPORTED`: grid/DCA/mean-
  reversion robot passive income), just a different mechanism (symmetric quotes vs. grid levels).
  Not a new finding; folding it into a C06 sequel is the only version of this worth doing, and only
  if the reach numbers justify it.
- **FinRL's DRL benchmark** is the only one of the eight with an actual quantified, source-cited
  performance claim from the project's own ecosystem. It is also the only one where independent
  evidence *already exists and disagrees with itself* year over year — which is a finding in its
  own right (published benchmarks flip sign across contest cycles) and arguably a more interesting
  episode than "we re-ran it and it didn't hold": **the claim already falsifies itself in public,
  across its own contest history**, without RES008 spending compute.

None of the eight is being promoted to `C##` from this pass — none has the tight, single-recipe,
reach-measured shape that earned C01–C08 their slot (see `00_claim_landscape.md`, "Selection for
the first batch"). They are logged as backlog (`B10`–`B13` in `TRACKER.md`), each with its own
folder and `VERDICT.md` under [`R_oss_stack/`](R_oss_stack/) (R01–R08, one per repo) so a later
revisit reads the standing verdict and its stated promotion trigger instead of re-surveying from
scratch. FinRL (R07) and Hummingbot (R05) are the only two with anything to pre-register if a
future batch needs a repo-sourced (rather than video-sourced) claim.

## Provenance note

No video, channel, or creator is referenced in this file. This is a survey of named public
open-source projects and their own documentation/papers — no `_internal/` entry is needed, and none
of the usual "don't name a creator" scrub concerns apply, because a GitHub org and a paper's
authors are not the target of this series (the series targets *claims*, not projects). Kept in mind
regardless: no line here should read as an endorsement or a condemnation of any project — the
verdict is narrowly "does it assert an edge we can test," not "is it good software."
