# RES006 — Results

Run 2026-08-31, seed 20260831, 10,000 bootstrap resamples. Method frozen in
[PREREGISTRATION.md](PREREGISTRATION.md), committed at `3b3c2e7d` before this code existed.
Raw: [out/results.json](out/results.json). SPY daily OHLCV, 5,448 rows.

## Headline

**No market-state rule we tested identifies a bad trade. The one trader-state rule we tested
is mildly harmful mechanically. Both results point the same way: "bad trade" is a fact about
the decision, not about the tape — and that is the one we can already compute.**

## H1 — effort without result. No advantage, and the sign leans the wrong way.

Down-absorption days (heavy volume, little price progression) vs **other down days**:

| Window | h | n | Absorption | Control | Diff | 95% CI |
|:--|--:|--:|--:|--:|--:|:--|
| Def | 1 | 517 | +0.015% | +0.109% | −0.094% | −0.227 … +0.038 |
| Def | 3 | 517 | +0.034% | +0.262% | −0.228% | **−0.454 … −0.004** |
| Def | 5 | 517 | +0.151% | +0.357% | −0.207% | −0.500 … +0.082 |
| Hold | 1 | 284 | +0.038% | +0.154% | −0.116% | −0.284 … +0.057 |
| Hold | 3 | 284 | +0.198% | +0.339% | −0.141% | −0.444 … +0.177 |
| Hold | 5 | 284 | +0.407% | +0.480% | −0.073% | −0.504 … +0.379 |

Creamer predicts absorption → reversal *up*. **All six point estimates are negative** — heavy
volume with no progress on a down day was followed by *worse* returns than an ordinary down
day. The one interval that excludes zero excludes it on the wrong side. The holdout is a clean
null.

**This does not refute order flow.** It refutes the daily-bar proxy for it. He reads delta at
each price level inside 5-minute candles; we compressed that to one volume number and one
close per day, which is roughly three orders of magnitude coarser and could plausibly destroy
the signal outright. The honest statement: **at the resolution we can reach, there is no
detectable advantage** — and we cannot reach his.

## H2 — participation floor. Null.

Skipping trades on below-median volume, against a random skip of identical frequency:

| Window | h | Skipped | Rule − placebo | 95% CI |
|:--|--:|:--|--:|:--|
| Def | 1 | 1832/3523 | −0.010% | −0.066 … +0.045 |
| Def | 3 | 617/1175 | +0.056% | −0.088 … +0.199 |
| Def | 5 | 351/705 | −0.077% | −0.339 … +0.169 |
| Hold | 1 | 1020/1924 | +0.003% | −0.082 … +0.085 |
| Hold | 3 | 340/641 | −0.050% | −0.315 … +0.194 |
| Hold | 5 | 206/384 | −0.060% | −0.509 … +0.345 |

Six of six include zero, signs mixed. A volume floor is not distinguishable from skipping the
same number of trades at random.

## H3 — stop after k losses. Null as predicted, and mildly negative.

| Window | h | k | Skipped | Rule − placebo | 95% CI |
|:--|--:|--:|:--|--:|:--|
| Def | 1 | 2 | 683/3523 | −0.017% | −0.045 … +0.012 |
| Def | 3 | 2 | 205/1175 | −0.078% | **−0.148 … −0.007** |
| Hold | 1 | 3 | 160/1924 | −0.027% | **−0.053 … −0.003** |
| Hold | 5 | 3 | 18/384 | −0.083% | **−0.171 … −0.006** |

Nine of twelve cells include zero. **The rule mean is below the placebo mean in 10 of 12
cells**, and all three intervals that exclude zero exclude it on the side that says the rule
*hurts*. Mechanically that is what mild mean-reversion implies: sitting out after losses sits
out part of the rebound.

**This was pre-registered as the predicted result, and it is the most useful finding in the
study.** Stopping after a losing streak cannot help a machine — trade outcomes on a mechanical
rule are close to independent, and where they are not, the dependence runs against the rule.

**So the entire value of Creamer's "stop after two losses" lies in the trader, not the
market.** He is not filtering bad market conditions. He is interrupting his own degradation:
*"if I take three losses in a row, there's like a 50/50 chance I start making bad decisions"*
[46:42]. The market provides no reason for that rule. His behaviour does.

## What this answers

Saiful asked how we identify bad trades and eliminate them. Across 24 pre-registered cells:

1. **You cannot identify a bad trade from market state.** Absorption: nothing, wrong sign.
   Volume floor: nothing.
2. **You cannot identify one from trade-outcome sequence either.** Loss-streak stops are
   mechanically counterproductive.
3. **Which leaves where Creamer actually puts it.** His bad trade is never "a trade in a bad
   market". It is *"I try and guess and I don't let it confirm itself first"* [43:09] and
   rule-bending [43:09] — and decisively, **a rule-bent trade that wins is still bad**
   [43:40]. That is a property of the decision, unavailable from any price series.
4. **We already compute it.** `ComplianceResult.violations`
   ([schemas/trade.py:203](../../backend/app/schemas/trade.py#L203)) runs a deterministic
   mandate check on every proposed trade. Nothing aggregates it into a behavioural read.

The elimination target is process violations, not market conditions — which is
[RES005](../RES005_trainable_skill/README.md)'s instrumentation CR, now supported by a test
built to be able to refute it.

## Caveats

- 3 of 24 cells cross at 95%; ~1.2 is expected from multiple comparisons alone. The three that
  cross are consistently signed, which is why H3 is read as a weak real effect rather than noise.
- Long-only SPY, no costs. Costs would make every filter arm look *better* (fewer trades), which
  is a further reason not to read H2/H3 nulls as evidence for filtering.
- Means are imprecisely estimable at this n (Lo 2002 / CR136). No Sharpe computed.
