# C08 — "A chatbot's stock picks beat the market" — PRE-REGISTRATION

Written 2026-09-17, before any C08 code runs and **before any chatbot is asked anything**.
Inherits [`../PREREG_COMMON.md`](../PREREG_COMMON.md).

## The claim, as taught

Ask a chatbot for ten stocks to beat the S&P 500, hold them a year, compare with an index ETF;
the chatbot that finishes ahead "won". Landscape class L8 — 2 videos read, 2.76M views (measured
2026-09-17). In one, four chatbots each got one prompt, one run, ten stocks, one year; three
finished ahead of the index by 3 to 22 points and one behind by ~8. In the other — to its credit —
the creator ran the prompt nine times and reported that no run beat the index.

Three separable claims: **(a)** one ten-stock portfolio beating the index over one year is evidence
of picking skill; **(b)** a chatbot's picks are an independent view of the market; **(c)** a
chatbot's picks can be validated by back-testing them.

## Universe

`U-LARGE100` — 100 large US companies, frozen in
[`code/universe_large100.py`](code/universe_large100.py) at pre-registration. Benchmark inside the
universe: its own equal-weight mean (survivorship cancels). SPY is reported beside it, with the
caveat that a survivor list flatters every portfolio drawn from it relative to SPY.

## Part 1 — what luck alone does (no chatbot involved)

For each 12-month window starting on the first trading day of every month, 2006-01 → 2025-08:
10,000 random equal-weight ten-stock portfolios from the names with data at the window start.

- share that beat the universe mean; share that beat SPY;
- distribution of excess return over the universe mean: IQR, 5th–95th percentile;
- how often a random portfolio lands +3, +13, +22 points ahead or −8 behind — the gaps in the video;
- analytic: probability that ≥ 3 of 4 independent coin-flip portfolios beat the benchmark.

## Part 2 — what chatbots actually pick

Verbatim prompt from the video: `I would like to outperform the S&P 500 in the next year. Can you
propose 10 stocks I should buy?` Three Claude models (Haiku 4.5, Sonnet 5, Opus 5) × 10
independent fresh runs = 30 responses. Disclosed deviation: the videos used other vendors'
chatbots; we use the ones available to us. Recorded: tickers; refusals (a refusal is a result —
one chatbot in the video declined too).

- **Stability:** mean pairwise Jaccard overlap of pick sets, within and across models.
- **Popularity / momentum tilt:** for picks inside `U-LARGE100`, their percentile rank on trailing
  36-month and 12-month total return as of 2026-08-31, against the universe (50 = no tilt).
- Share of picks falling outside the universe (reported; they are excluded from the tilt measure).

No forward performance is or can be measured here — the future has not happened. That is the point
of claim (c).

## Part 3 — hindsight

Prompt, same three models × 10 runs: `It is January 2, 2019. I would like to outperform the
S&P 500 over the next five years. Can you propose 10 stocks I should buy? Answer as of that date.`
For each response's in-universe picks: equal-weight 5-year total return 2019-01-02 → 2023-12-29,
placed as a percentile within 10,000 random ten-stock portfolios over the same dates.

## Our hypothesis

H1: a random ten-stock portfolio beats the universe mean in 40–55% of draws, and the 5th–95th
spread of one-year excess return exceeds 30 points — so +3 to +22 on one draw is inside the noise
and "3 of 4 beat the index" has a coin-flip probability of about 31%. H2: mean Jaccard across
runs ≥ 0.4 and picks sit at or above the 65th percentile on trailing 36-month return — the picks
are the recent large winners, a popularity tilt, not an independent forecast. H3: back-dated
picks land at or above the 90th percentile of random portfolios on average — hindsight, which
makes any back-test of chatbot picks inside the model's training period meaningless.

## What would support the claim instead

- Part 1: the 5th–95th spread is under 10 points → a one-year gap of +13 or +22 *would* be
  informative; claim (a) stands.
- Part 2: mean Jaccard < 0.2 **and** trailing-return percentile within 45–55 → the picks are
  neither stable nor momentum-tilted; H2 is wrong and we say so.
- Part 3: back-dated picks average within the 35th–65th percentile → no measurable hindsight; the
  back-test objection is dropped.

## Not claimed

We cannot and do not say chatbot picks will underperform. Nobody can test that on past data — which
is equally true for the people claiming they outperform.
