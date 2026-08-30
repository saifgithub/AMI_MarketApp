# RES004 — Pre-registration

**Committed before any code ran.** Frozen 2026-08-30. Follows RES003's method exactly
(same data, same windows, same block bootstrap); only the hypotheses are new.

## Why this is separate from RES003

RES003 classified regime by **static VIX-percentile terciles** and found no dependable
directional effect. Rader Trader (RES002, video 3) makes a claim about a **transition**, not a
level — and a static classifier cannot see a transition. His claim is therefore untested, not
refuted. Bolting it onto RES003 after seeing RES003's results would be the exact retuning this
process exists to prevent, so it gets its own registration.

## Hypotheses

**H1 — the "JEX flip".** After a run of consecutive "positive gamma" closes, the *first* close
into "negative gamma" predicts **downside**, over and above the level effect.

**H2 — dispersion rotation.** In calm regimes, cross-sectional dispersion is high relative to
index volatility (favouring single names); in stressed regimes, index moves dominate
(favouring the index).

## Operationalisation

No GEX is available to us (RES003 established `^VIX3M`/`^VIX9D`/`^VXV` have no Yahoo history).
VIX percentile rank over a trailing 504 days, lagged one day, stands in for the gamma sign —
below the 50th percentile is the "positive gamma" analogue, above is "negative gamma".

**H1.** A *flip day* is the first close above the 50th percentile after **K consecutive closes
below it**, K ∈ {5, 10, 20} (Rader's stated "5, 10, 20, 30 days"). Forward simple returns at
h ∈ {1, 3, 5} trading days.

> **The control is the whole design.** Flip days are stressed days by construction, so
> comparing them to all days confounds the transition with the level — which is what RES003
> already measured. The comparison is **flip days vs non-flip days that are also above the
> 50th percentile.** Any effect that survives that control is a transition effect.

Statistic: mean forward return, flip − matched control. Rader predicts **negative**.

**H2.** The nine original sector SPDRs (`XLK XLF XLE XLV XLI XLY XLP XLU XLB`) — chosen over a
mega-cap basket because they carry no survivorship bias and have full history from 2005.
Sector dispersion is a *conservative* proxy for the single-name dispersion Rader describes: if
it shows up between sectors, it is real between names.

- `dispersion_t` = cross-sectional standard deviation of the nine daily returns, 21-day mean.
- `ratio_t` = `dispersion_t` ÷ SPY 21-day realised vol.
- `avg_corr_t` = mean pairwise correlation of the nine, trailing 21 days.

Compare calm vs stressed terciles (RES003's classifier, unchanged). H2 predicts `ratio` higher
in calm and `avg_corr` higher in stressed.

## Windows, inference, kill criteria

Definition 2005–2018, holdout 2019–2026, one shot. Stationary block bootstrap, expected block
length 2h (H1) / 42 days (H2), 10,000 resamples, 95% intervals. No p-values, no Sharpe.

- **H1 kill:** interval includes zero. Note upfront: 3 K × 3 h × 2 windows = 18 cells, so
  roughly one spurious crossing at 95% is expected. A single crossing cell is not a finding;
  a consistent sign across K and h in *both* windows is.
- **H2 kill:** dispersion-ratio interval includes 1.0 across regimes. Expected to pass —
  correlations spiking in stress is a well-established stylised fact, so like RES003's Test A
  this is closer to a calibration check than a discovery, and it will be reported as such.
