# C05 DEVIATIONS

Recorded at run time, most literal reading kept in each case.

- STC 'rising'/'falling' operationalised as STC[t] > STC[t-1] / STC[t] < STC[t-1] (simple one-bar-back comparison) -- the pre-registration describes the direction qualitatively without a lookback, and a single prior bar is the most literal reading of a two-point trend description.
- Entry filter (STC confirmation) evaluated at the SAME bar as the UT Bot cross, using that bar's own STC value and its comparison to the prior bar -- both indicators are read causally at the signal bar's close, matching 'a signal on bar t enters at the open of t+1'.
- Daily timeframe 'full history': loaded from 1990-01-01 (before any of the 7 instruments' first bar) through the pinned data end 2026-08-31; each instrument starts at its own first available bar, per PREREG_COMMON.
- A bar where a variant's long and short signals fire simultaneously (both filters true at once) keeps the long signal and drops the short one on that bar, rather than skipping both or taking both -- occurrences logged per (variant, reading, timeframe, ticker) below if any occur.
- 'Run pytest bare' was run scoped to this claim's own directory (`pytest C05_99pct_scalping_recipe -q`), not repo-root-wide: a bare repo-root `pytest` fails on collection because C03_tune_until_spectacular/code/test_indicators.py and this claim's code/test_indicators.py share a basename with no __init__.py in either code/ dir (pytest cannot disambiguate two same-named modules at repo-root rootdir) -- a pre-existing repo-wide convention (every prior claim's tests are likewise run scoped to that claim's own folder, per C03/C04 precedent), not something introduced here, and not something this claim is allowed to fix by editing another claim's files.
