# RES004 — Results

Run 2026-08-30, seed 20260830, 10,000 bootstrap resamples. Method frozen in
[PREREGISTRATION.md](PREREGISTRATION.md), committed at `a85a6e40` **before** this code
existed. Raw output: [out/results.json](out/results.json).

SPY + `^VIX` + nine sector SPDRs, 5,448 rows. Definition 2005–2018, holdout 2019–2026.

## Headline

**The two practitioners who refused to make a directional claim were right. The one who made
one cannot support it.**

| Claim | Source | Verdict |
|:--|:--|:--|
| Regime predicts forward **volatility** | all three | **Holds** (RES003 A, ~2× both windows) |
| Regime should modulate **size** | Creamer, Ireland | **Holds**, beats placebo (RES003 C) |
| Regime carries no **direction** | Creamer, Ireland | **Supported** (RES003 B null) |
| The flip predicts **downside** | Rader | **Not supported — 0 of 18 cells** |
| **Dispersion** rotates with regime | Rader | **Holds**, but it is a known stylised fact |

## H1 — the "JEX flip". Not supported.

Mean forward SPY return on flip days minus matched control (stressed days that are *not*
flips, so the level effect is controlled out). Rader predicts **negative**.

**Zero of eighteen intervals exclude zero.** Selected cells:

| Window | K | h | n flips | Flip | Control | Diff | 95% CI |
|:--|--:|--:|--:|--:|--:|--:|:--|
| Def | 5 | 5 | 54 | +0.241% | +0.143% | +0.098% | −0.546 … +0.979 |
| Def | 20 | 3 | 25 | +0.769% | +0.067% | **+0.703%** | −0.055 … +1.404 |
| Hold | 5 | 5 | 30 | −0.101% | +0.568% | −0.669% | −1.770 … +0.341 |
| Hold | 20 | 5 | 11 | +0.290% | +0.552% | −0.262% | −1.345 … +0.861 |

Two things sink it beyond the intervals:

1. **The definition window runs the wrong way.** All nine definition cells are *positive* —
   flip days were followed by *higher* returns than matched stressed days, the opposite of the
   prediction. The holdout is mixed. A claim whose point estimate flips sign across the sample
   split has no stable direction.
2. **The setup is too rare to have been backtested at all.** Twenty-one years of daily data
   yields **11 to 54 flip events** depending on K. At n=11, a strategy's edge cannot be
   distinguished from a coin flip by anyone, with any method. Rader states all three of his
   strategies are "rigorously back tested and built upon truths in the market" and shows no
   backtest. **On our operationalisation the data to back-test this does not exist**, and that
   is a statement about the sample size, not about his software.

The honest caveat cuts the other way too: our VIX-percentile proxy is *not* his GEX flip level.
A real dealer-positioning flip may be a sharper event than a VIX median crossing. But the
rarity problem is worse, not better, with a stricter definition — a rarer trigger means fewer
events, not more evidence.

## H2 — dispersion rotation. Holds, in both windows.

Cross-sectional sector dispersion ÷ SPY realised vol, and mean pairwise correlation:

| | Definition 2005–18 | Holdout 2019–26 |
|:--|:--|:--|
| dispersion/index-vol, calm | 0.873 | 1.074 |
| dispersion/index-vol, stressed | 0.678 | 0.774 |
| **calm ÷ stressed** | **1.287** (1.105–1.495) | **1.388** (1.207–1.612) |
| avg pairwise corr, calm | 0.567 | 0.403 |
| avg pairwise corr, stressed | 0.690 | 0.577 |
| **stressed − calm** | **+0.123** (+0.048–+0.203) | **+0.174** (+0.083–+0.261) |

All four intervals exclude their null. In calm regimes dispersion is ~30–40% higher relative
to index volatility and cross-sectional correlations are 12–17 points lower. Rader's
"trade single names in positive gamma, trade the index in negative gamma" is directionally
right about the market structure.

**As pre-registered, this is a calibration check rather than a discovery.** Correlations
spiking in stress is one of the most documented facts in equity markets. He is restating a
stylised fact accurately — which is worth something, but it is not the proprietary edge the
video frames it as. Note also that sector dispersion is a *conservative* proxy for the
single-name dispersion he actually describes.

## What it means for AMI Trade

Nothing changes in RES003's conclusion, and one thing is added.

- **The direction door stays shut.** RES003's null survived the sharpest available attack —
  a transition-based test built specifically to find what a level-based test would miss.
  A regime term modulates size. It does not pick sides.
- **Dispersion is a real, measurable regime property** and it is a second moment, so it is
  estimable at our sample size. If the Room ever reasons about *breadth* — whether today
  favours concentration or spread — this is the honest input for it.

Neither finding touches production code. A CR would be needed to build either.
