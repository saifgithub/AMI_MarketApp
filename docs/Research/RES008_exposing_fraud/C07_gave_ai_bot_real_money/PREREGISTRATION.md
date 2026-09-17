# C07 — "I gave an AI bot real money and it beat the market" — PRE-REGISTRATION

Written 2026-09-17, before any C07 code exists. Inherits [`../PREREG_COMMON.md`](../PREREG_COMMON.md).

## The claim, as taught

A bot is funded with a real account, runs for one week or one month, finishes ahead of the index
(or of a rival), and the result is presented as evidence that the bot works. Landscape class L7 —
2 videos read, **6.12M views**, the largest reach of any class in the survey (measured 2026-09-17).
In one the "AI" is a proprietary rules indicator (untestable, no model involved); in the other a
chatbot suggested the idea and a developer hand-coded an **RSI oversold/overbought** rule, run for
five trading days with nearly the whole account in each trade. One month-long run was, by its
creator's own account, in a trending market where the bot "does exceptionally well".

Two separable claims: **(a)** the disclosed rule has an edge; **(b)** a one-week or one-month
result can show that any bot has one.

## Part 1 — the disclosed rule

RSI(14), long when RSI < 30, flat when RSI > 70, long/flat only. `U-EQ` daily (`DEFINE`,
`HOLDOUT`) and 60-minute (~730 days). `next_open`, 5 bps. Versus buy-and-hold (paired) and versus
the matched-random placebo (500 reps per ticker).

## Part 2 — what a short window can show

A **zero-skill bot**: up to 3 concurrent long positions drawn at random from 10 tickers (AAPL
MSFT AMZN GOOGL NVDA TSLA DIS JPM KO WMT), holding 1–3 days, equal size, 5 bps. 2,000 simulated
bots over 2005–2026. For every 5-trading-day and every 21-trading-day window:

- share of windows in which the zero-skill bot beats SPY; beats it by ≥ 1, ≥ 3 points;
- the same for the Part 1 RSI rule;
- **conditional on a trending window** (equal-weight basket of the 10 names up ≥ 8% over the
  21 days): the zero-skill bot's trade win rate and return.

And the sample-size arithmetic from the measured tracking error: how many weeks (months) of
results are needed before a genuine +5 points-per-year edge separates from zero at two standard
errors.

## Our hypothesis

H1: the RSI rule does not beat buy-and-hold net in the majority of tickers in either window, and
its placebo percentile is unremarkable (pooled mean in [30, 70]). H2: the zero-skill bot beats SPY
in 40–60% of one-week windows — a one-week "win" is a coin flip. H3: in trending months the
zero-skill bot wins ≥ 60% of its trades, i.e. a 31-wins-in-47 month needs no skill to produce.
H4: the required track record for a +5 pt/yr edge exceeds 3 years.

## What would support the claim instead

- RSI rule at or above the 95th placebo percentile pooled, in both windows → `PARTLY HOLDS` for
  the rule (real timing skill), reported as such;
- zero-skill bot beats SPY in < 25% of one-week windows → a weekly win would be informative after
  all, and claim (b) stands.

## Reuse

P06 (RES001): a +100% month is the expected maximum among a few hundred zero-skill entrants. The
episode uses it; it is not re-tested.
