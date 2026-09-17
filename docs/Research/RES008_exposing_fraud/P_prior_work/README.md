# P_prior_work — video briefs for claims tested before RES008

This folder holds `VIDEO_BRIEF.md` drafts for claims that were tested and closed by **RES001** and
the earlier `Alternatives/Intel/quant_finance` study — before RES008's own pre-registration
discipline existed. See [`../01_prior_work.md`](../01_prior_work.md) for the full sweep and
[`../TRACKER.md`](../TRACKER.md) for the recorded verdicts these briefs quote.

**Nothing here is re-tested.** Every number in each brief is copied from the original source study;
this folder adds no new code, no new `out/`, and no new results. The evidence for each claim lives
at its own path, not here:

| Brief | Claim | Verdict (as recorded) | Evidence lives at |
|:--|:--|:--|:--|
| [`P01_ml_predicts_direction/`](P01_ml_predicts_direction/VIDEO_BRIEF.md) | "ML predicts stock direction" | `DISPROVED` | `docs/Research/Alternatives/Intel/quant_finance/lgbm_results.md` |
| [`P04_stop_after_k_losses/`](P04_stop_after_k_losses/VIDEO_BRIEF.md) | "Stop trading after k losses" improves results | `DISPROVED` mechanically — behavioural value only | `docs/Research/RES001_finding_the_edge/06_absorption_and_elimination/` |
| [`P06_contest_win_proves_skill/`](P06_contest_win_proves_skill/VIDEO_BRIEF.md) | A contest-winning return proves skill | `NOT SUPPORTED` | `docs/Research/RES001_finding_the_edge/03_volatility_regime_sizing/` §E |
| [`P20_P21_what_is_real/`](P20_P21_what_is_real/VIDEO_BRIEF.md) | Volatility regime forecasts how much the market moves (not which way); sector dispersion rotates with regime | `HOLDS` — as a risk statement that costs return | `docs/Research/RES001_finding_the_edge/03_volatility_regime_sizing/` Tests A–C · `…/04_gamma_transition_dispersion/` H2 |

One difference from a `C##_<slug>/` claim folder: P01 was tested under the
`Alternatives/Intel/quant_finance` study's own method, not a RES008/RES001-style pre-registration
commit. Its brief says so explicitly and does not cite a commit hash for it. P04 and P06 do carry
real pre-registration commits (RES001's `3b3c2e7d` and `55a66533`) and those are quoted as recorded.
