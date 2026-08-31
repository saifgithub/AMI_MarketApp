# CR214 — the Room's edge, if it has one, is at its own horizon

**2026-08-31 (AT:R74).** Zero new convenes. This re-scores the 446 runs of CR164's
`r70-outcome-2` — the batch whose own headline reads *"no outcome edge is demonstrated"* —
at a horizon nobody had ever been able to score.

## Why this was available today and not on 2026-08-20

Phase B graded at **20 trading days**. The Room's stated horizons have a **median of 90
calendar days** and reach 365. Phase B said so itself, in its closing section:

> **What this does not answer.** *"Stated horizons have a median of 90 days and reach 365; the
> scoring horizon is 20 trading days. **The four-week numbers grade name selection, not whether
> these theses worked.** Nothing here can be read as 'the Room's judgement is/is not profitable
> over its own stated horizon' — that needs the oldest cohort to age past its horizon."*

The 2025 cohort has now aged. `H_LONG = 62` trading rows ≈ 90 calendar days.

## The numbers

Same batch, same DB, same seed. Existing cells reproduce byte-identically; only new cells appear.

| horizon | within-date paired spread | 95% CI | placebo-adjusted | 95% CI | dates |
|:--|--:|:--|--:|:--|--:|
| 4w (20d) | +1.46% | −1.80 … +4.67 | +1.37% | −1.59 … +4.34 | 18 |
| **~13w (62d)** | **+5.09%** | −1.41 … +12.88 | **+4.59%** | −1.45 … +12.11 | 16 |

**3.5× larger at the horizon the Room actually claimed.** Two properties make it worth
writing down rather than filing as noise:

1. **It survives the placebo.** The matched-random arm removes the "any selector looks good if
   it merely selects fewer" artifact — RES001's binding rule — and +5.09% only falls to
   +4.59%. The effect is in *which* names, not in *how many*.
2. **Signal-to-noise improves with the horizon.** Estimate ÷ CI half-width: **0.45 at 4w →
   0.71 at 13w**. A longer window widens the interval, so a spurious effect would typically
   get *relatively* noisier. This got tighter relative to its own error.

## Pre-registration — the reason this is not a fishing expedition

The 90-day cell was specified **before** the measurement ran, and the anchor is the commit
history, not this file (RES001 rule 1):

| | UTC |
|:--|:--|
| `a632476d` — CR214 doc specifying *"Score at 90 days as well as 20"* | **11:09:15** |
| `report_r70-outcome-2.md` generated | **11:31:34** |

The justification was written from Phase B's own caveat, not from a result.

## What this is NOT

- **Not significant.** Both intervals cross zero. This is a *larger* point estimate with a
  *wider* interval, not a demonstrated edge — the same distinction CR164 got wrong in the
  other direction when it called a non-measurement a null.
- **Effective n is below 16.** Sixty-two-day windows overlap far more than twenty-day ones, so
  the date-clustered bootstrap is optimistic here in a way it is not at 4w.
- **This is the ABLATED Room.** News, social and analyst consensus are `UNAVAILABLE` under
  as-of; it approves 9.0% against the live Room's 24–37%. Whatever this measures, it is not
  the Room that ships.
- **One batch, one horizon, one model generation** (Qwen3.6 — see [DEF385](../../defect/_registry/DEF385.row.md)).
- **No Sharpe, no portfolio claim, no P&L claim.** Selection edge only.

## Where it sits against everything else measured

| source | Room | dates | spread | interval / p |
|:--|:--|--:|--:|:--|
| CR164 Phase B, 4w (as published) | ablated | 18 | +1.15 pt | −2.05 … +4.43 |
| CR164 Phase B, **13w** (here) | ablated | 16 | **+5.09 pt** | −1.41 … +12.88 |
| CR035 live slate, ~3w | **live** | 1 (144 names) | +2.75 pt | p = 0.106, leave-one-out robust |
| CR157 live retro, within-date 4w | **live** | 4 | +1.19 pt | −1.63 … +3.83 |

Four estimates, four positive signs, across two Rooms and three populations, none individually
significant. That is what a real-but-small edge looks like when every instrument aimed at it is
underpowered. **It is also what chance looks like.** Separating the two is the whole job, and
only more independent dates do it.

> **A correction recorded here because it was published in-session:** the live retro panel was
> first reported at **−1.09 pt**. That figure pooled across dates and so partly measured *when*
> the Room convened rather than *what* it chose. The within-date estimator, which cancels the
> common market factor exactly, gives **+1.19 pt**. The pooled number was wrong for the
> question and is superseded — the same estimator error this CR exists to fix.

## What follows

1. **The 13w cell becomes a primary metric**, not a sensitivity — carried on every future
   report beside 5d/20d.
2. **Phase A (n=126) and the pilot (n=125) can be re-scored the same way**, free. Different
   prompt generations, so they are not poolable with Phase B (`weekly_room_retro`'s rule), but
   three independent 13w reads beat one.
3. **The sweep's scoring horizon must be 62d**, which costs dates: ~43 usable Fridays at 13w
   against 52 at 4w (DEF385's window). That trade is now clearly worth making.
4. **The live Room is where the signal should be strongest** if the ablations are what cap the
   backtest at a 9% approve rate. A repeat of the CR035 slate is ~150 convenes for a second
   independent live date — the cheapest high-value convene spend available.
