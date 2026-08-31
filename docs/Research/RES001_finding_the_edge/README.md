# RES001 — Finding the edge

**Goal:** find a real, testable edge in public market data, starting from claims made by
practitioners and open-source frameworks.

**Result: we did not find one.** Across roughly fifty pre-registered tests, nothing we examined
produced positive expected return we could defend. One risk-control effect survived, and it is
public textbook knowledge that *costs* return. Everything else was a null — several of them
sharp enough to be worth publishing.

This research is **not for the product.** Output is knowledge: BOK lesson material, or a public
rebuttal. Nothing here changes production code.

---

## How to read this

| Part | What it covers |
|:--|:--|
| [01 — FinRL-X review](01_finrl_x_review.md) | Is AI4Finance's framework a usable basis for anything? |
| [02 — Practitioner claims](02_practitioner_claims.md) | Three YouTube traders, what they claim, who is selling what |
| [03 — Volatility regime sizing](03_volatility_regime_sizing/RESULTS.md) | Does regime modulate risk but not direction? |
| [04 — Transition + dispersion](04_gamma_transition_dispersion/RESULTS.md) | Does the gamma *flip* predict direction? Does dispersion rotate? |
| [05 — The trainable skill](05_trainable_skill.md) | What is the skill, and could a simulator train it? |
| [06 — Absorption + elimination](06_absorption_and_elimination/RESULTS.md) | Order-flow proxy benchmark; can bad trades be filtered out? |

## Method, and why it is the durable output

Every measured part follows the same discipline, adopted after part 01 found FinRL-X shipping a
strategy config (`v1.2.1` → `v1.2.2`) tuned against the very window that reported its result:

1. **Pre-register before running.** Hypothesis, thresholds, kill criteria and metrics are
   written and **git-committed before the code exists**. The integrity anchor is the commit
   history, not these files: `55a66533` (part 03), `a85a6e40` (04), `3b3c2e7d` (06).
2. **Define on 2005–2018, confirm on 2019–2026.** One shot at the holdout. Retuning burns it,
   and the writeup says so.
3. **Placebo arms.** Every "this filter helps" claim is tested against a matched-random control
   that removes or resizes exactly as many trades. Without that arm you are only measuring
   *trading less*.
4. **Block bootstrap, intervals, never p-values.** Daily data is heavily autocorrelated, so
   naive standard errors are invalid.
5. **No Sharpe, anywhere.** Mean returns are not precisely estimable at these sample sizes
   (Lo 2002). Second moments are, so the tests are built around them.

## What survived

**Volatility is forecastable.** Stressed vs calm regimes are followed by ~2× the realised
volatility — 2.44 (definition) and 2.08 (holdout) at h=5, all six intervals above 1.0.

**Regime-aligned sizing homogenises risk, and beats a placebo.** Variance of per-trade P&L,
vol-scaled ÷ shuffled-size control: 0.57–0.75 across six cells, every interval below 1.0. So
knowing the regime does work that varying size at random does not.

**Dispersion rotates with regime.** Cross-sectional dispersion relative to index vol is
1.29–1.39× higher in calm; mean pairwise correlation is 12–17 points higher in stress.

**None of these is an edge.** The sizing rule *reduced* mean return (+1.34% → +1.04% on the
holdout). Volatility clustering won Engle a Nobel in 2003 and is available to anyone with a VIX
quote. Correlations spiking in stress is among the most documented facts in equity markets.
These are real, public, and not profitable on their own.

## What did not survive

| Claim | Test | Outcome |
|:--|:--|:--|
| Regime predicts direction | 3 horizons × 2 windows | Null; point estimates **flip sign** across the sample split |
| The "gamma flip" predicts downside | 3 K × 3 h × 2 windows | **0 of 18**; definition-window signs run *opposite* to the prediction |
| Effort-without-result predicts reversal | 3 h × 2 windows | No advantage; all six point estimates lean the **wrong way** |
| A volume participation floor helps | vs matched random skip | Null, 0 of 6 |
| Stopping after k losses helps | vs matched random skip | Null, and **mildly harmful** — rule below placebo in 10 of 12 cells |

## The four findings worth publishing

1. **A championship return carries little information about skill.** A +100% month is the
   *expected maximum* among a few hundred zero-skill entrants at 4–6× SPY volatility. Stated as
   the conditional it is: entrant counts are not published, and "consistent with luck" is not
   "was luck". It says nothing about any particular champion.

2. **The practitioner who refused to claim direction was right; the one who claimed it could not
   support it.** Two of the three explicitly said gamma tells you volatility, not direction —
   and the data agrees, across two studies including one built specifically to catch what the
   first would miss. The third made a directional claim, called it "rigorously back tested",
   showed no backtest, and it failed 0 of 18. **On our operationalisation the data to
   back-test it does not exist**: 21 years yields 11–54 events.

3. **"Stop after two losses" cannot help a machine — so its entire value is behavioural.**
   Mechanically the rule is slightly counterproductive, because sitting out after losses sits
   out part of the rebound. It works for a human because the human degrades, not because the
   market does. That is a clean, testable separation of a behavioural intervention from a
   market one.

4. **Bad trades are not identifiable from market state.** Three independent attempts — absorption,
   volume floor, loss-streak — all came back empty. Which locates "bad trade" exactly where the
   most credible of the three practitioners puts it: a rule-bent trade that *wins* is still a
   bad trade. That is a property of the decision, unavailable from any price series.

## What we must not claim

- **Part 06 does not refute order flow.** It refutes a daily-bar proxy roughly three orders of
  magnitude coarser than the resolution order flow is read at. A null here is not evidence
  about tick data, and saying otherwise would be the same overclaiming we are criticising.
- **We cannot call anyone a fraud.** Creamer in particular is likely skilled: his mechanism is
  the one that *survived* (part 03), he laid out a falsifiable process, and his result came
  with audited broker statements. The defensible frame is "we tested these claims", never
  "these people are lying."
- **We have no edge to teach.** Anything written from this must say that plainly.
- Where an edge could still live, untested rather than refuted: real order flow and real dealer
  gamma (data we do not have), single-name cross-section (we tested SPY and nine sector ETFs),
  and longer-horizon fundamental signals.

## Data and constraints

SPY, `^VIX`, and nine sector SPDRs, daily, 2005-01-03 → 2026-08-28 (5,448 rows) via `yfinance`.

**VIX term structure is unavailable** — `^VIX3M`, `^VIX9D` and `^VXV` return no history from
Yahoo (verified). That curve is the closest free analogue to dealer gamma positioning, so every
regime test here substitutes VIX *level* percentile: still forward-looking implied volatility,
but not the curve, and not gamma exposure.

All code is under this folder and runs on the Mac against `backend/.venv`. It imports nothing
from `backend/app/` and writes nothing outside these directories.
