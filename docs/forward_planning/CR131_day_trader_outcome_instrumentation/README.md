# CR131 — instrument the Day Trader preset so it teaches instead of just permitting

**Filed:** 2026-07-30 (AT:R65) · **Origin:** Saiful accepted the Day Trader preset (CR129) and
approved instrumenting it as its own CR.

## Why this exists

CR129 adds a **Day Trader** preset that sets every user risk limit permissive — Saiful's reasoning:
*"if we do not let them fail in a safe environment, they will fail with real money."* Correct, and
consistent with CR101's L3 (in a simulation-only trainer the blow-up IS the lesson).

But **a preset that only removes limits is a faster way to lose with nothing learned.** The failure
mode is a user switching it on, losing steadily, and drawing no conclusion — which is exactly what
happens with real money and exactly what this app exists to prevent. The safe environment is only
worth anything if the user can *see what happened to them* afterwards.

This CR is the seeing.

## What to build

**A measured outcome comparison, shown to any user who has run the Day Trader preset**, against the
published baselines CR129 is already grounded in:

- **Barber & Odean (66,465 households, 1991–1996)**: most-active cohort **11.4%**/yr, least-active
  **18.5%**, market 17.9% — and before costs both groups picked stocks about equally well, so the
  whole gap was activity.
- **Barber, Lee, Liu & Odean (Taiwan, 1992–2006)**: under **1%** of day traders reliably profitable,
  **>80%** losing in a typical half-year, survival **44%** at one year, **24%** at two, **15%** at
  three.

The user's own numbers, computed from `sim_trades`, placed beside those. Minimum set:

1. **Trade frequency** — trades/day and /week while the preset was active vs before it.
2. **Realised P&L** while active vs before, annualised where the window supports it.
3. **Win rate and average win/loss** — the disposition-effect view: are losers held longer?
4. **Turnover**, the Barber–Odean metric, so the comparison is like-for-like rather than rhetorical.
5. **Where they sit on the survival curve** — "you are in month N; 15% of day traders are still
   trading at month 36."

## Rules

- **Never fabricate a comparison from a thin sample.** A user three days in has no annualisable
  return. Say so plainly — *"too early to compare"* — rather than extrapolating. This project has a
  standing rule against presenting an estimate as a measurement, and a chart that annualises four
  trades would break it spectacularly.
- **Do not moralise.** Numbers, not warnings. The Barber–Odean gap is more persuasive than any
  copy we could write, and a lecture invites the user to dismiss the data with it. Brand voice:
  analyst-to-analyst, numbers > adjectives.
- **This must work for the user who WINS.** A day trader who is up must see that too, honestly,
  including that <1% sustain it and that a short winning window is the single most common precursor
  to overconfidence (Barber & Odean's own explanation for excess trading). Do not bury a good
  result; contextualise it.
- **The baselines are US/Taiwan retail equity data.** State the provenance in-surface. It is
  reference material, not a claim about this user's market.

## Dependencies

**DEPENDS-ON CR129** — there is no preset to instrument until it exists, and the switch event this
CR reads is journalled by CR129.

Related: **CR132** (the day-trader lesson track this data should link into), **CR051** (existing
daily-usage analytics — reuse its aggregation path rather than building a second one), **DEF166**
(clamped closes stamp `realised_pnl` on full quantity — **read this before trusting P&L
aggregates**, it is open and it corrupts exactly the number this CR reports).
