# C04 — "A 90% win rate proves the strategy works" — PRE-REGISTRATION

Written 2026-09-17, before any C04 code exists. Inherits [`../PREREG_COMMON.md`](../PREREG_COMMON.md).

## The claim, as taught

The headline number of the genre is the win rate: 75%, 88%, 90%, 99%. It is offered as sufficient
evidence of a profitable method, usually with no average win, average loss, or sample size.
Landscape class L4 — 4 videos read, 2.99M views (measured 2026-09-17). Sample sizes behind the
quoted rates, where given at all: 2 chart examples, 12 trades, 25 trades, 47 trades.

Two separable claims: **(a)** a high win rate implies positive expectancy; **(b)** a win rate
measured on a few dozen trades is a measurement.

## Design

### Part 1 — the win rate is a dial

Zero-information entries: random entry bars, random side (50/50 long/short, which neutralises
drift), one position at a time. Exits are a bracket. Seven geometries, take-profit : stop in units
of the instrument's volatility scale *s*:

`0.5:5 · 1:5 · 1:3 · 1:1 · 2:1 · 3:1 · 5:1`

*s* = the instrument's median ATR(14) as a percentage of price, measured on `DEFINE` only and then
frozen. Time exit at 60 bars. Instruments: `U-EQ`, `U-CRYPTO`, `U-FX`, daily, full history to
2026-08-31. 2,000 random entries per instrument per geometry, fixed seed. Common costs; gross also
reported. Conservative same-bar rule (stop first) as per the common file.

Measured per geometry, pooled across instruments: win rate; expectancy per trade in units of *s*
and in percent, net and gross, with block-bootstrap intervals over trades in time order; the
driftless random-walk reference win rate `stop ÷ (target + stop)`.

### Part 2 — how much a small sample can say

Analytic, no data: Wilson 95% intervals for 2/2, 9/12, 22/25, 31/47. And for a trader who tries
*k* ∈ {1, 5, 20} variants of a rule whose true win rate is *p* ∈ {0.50, 0.60, 0.70}, the
probability that the best variant shows ≥ 88% on 25 trades.

## Our hypothesis

H1: win rate is monotone in `stop ÷ (target + stop)` and within ±8 points of it for every
geometry — random entries reach ≥ 85% at `0.5:5` and ≤ 25% at `5:1`. H2: net expectancy is not
above zero for **any** geometry (interval includes or lies below 0), so a 90% win rate and a 20%
win rate are equally worthless without the payoff ratio. H3: the Wilson interval for 22/25 spans
more than 25 points.

## What would support the claim instead

Any geometry with win rate ≥ 85% **and** a net-expectancy interval strictly above zero, pooled →
a high win rate would then carry information by itself; `HOLDS` for that geometry, investigated
before anything is published.

## Not claimed

Not that win rate is useless — with the payoff ratio and a sample size it is half of expectancy.
The test is of the win rate quoted **alone**.
