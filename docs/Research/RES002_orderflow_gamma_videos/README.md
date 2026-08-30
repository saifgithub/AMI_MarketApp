# RES002 — Orderflow + gamma-exposure practitioner claims

Three videos, three practitioners, no connection between them. Transcripts pulled with the
`youtube-extract` skill (CR212). Reviewed 2026-08-30.

**Every one of the three is selling something.** That does not make them wrong, but it is the
first fact about each document and it belongs at the top.

| # | Source | Sells | Claim shape |
|:--|:--|:--|:--|
| 1 | Chris Creamer via IQCapital (`PL7LKUsCgIQ`, 58m) | Prop-firm evaluations ($9 futures / $1 crypto) | Orderflow entries on MNQ, first 90 min |
| 2 | Nick Ireland / ninjagex (`bXVHsViQuyE`, 23m) | Checklist lead magnet + a paid GEX data vendor | SPY options off a gamma map |
| 3 | Rader Trader (`WBqxiVthqEk`, 43m) | Paid membership (theraderreport.com) | Three gamma strategies, backtested (unshown) |

## Their evidence, ranked

**Creamer** is the strongest: a fully drawn-out, falsifiable process, and a Robbins Cup
result that is at least externally recorded. Self-reported 60–65% win rate at 1.5R, profit
factor ~1.8, no sample size given.

**Ireland** is the weakest: three cherry-picked green months shown ($9,486 / $9,352 / $6,649),
"I have red months too" with none displayed, an unnamed testimonial ("HVAC made over
$16,000"), and a "$1k/day" title against a $29,711 account — 3.4%/day, which does not
reconcile with the months he shows. He also spends five minutes arguing price action has no
predictive power and then triggers entries on a bull-flag breakout.

**Rader** shows no P&L at all and asserts his strategies are "rigorously backtested" without
showing a backtest. But his mechanism section is the most precise of the three.

## What is worth keeping

**Creamer's entry grammar** (19:02–20:34, 30:46). Not the orderflow data — the *shape*:
location gate drawn before the open → effort-vs-result → **two-attempt confirmation** (never
act on the first failure; require a second attempt that fails at a better level) → stop placed
**beyond the level that failed**, not at a fixed percentage. His own definition of a bad trade
is skipping the confirmation: *"I don't let it confirm itself first, I just try and anticipate
it."*

This lands on live code. `Verdict.entry` ([schemas/room.py:41](../../backend/app/schemas/room.py#L41))
is a scalar *price*, with no field able to express "act only if X occurs". And
[room_runner.py:1801-1802](../../backend/app/services/room_runner.py#L1801-L1802) mints
`entry * 0.94` / `entry * 1.13` when the PM states no levels — arbitrary constants standing in
for structural invalidation, which the code already half-distrusts via
`level_provenance: "ami_default"`.

**The convergence across all three** on regime: gamma/volatility regime governs *how much to
risk*, not *which way to go*. Creamer: negative gamma means faster moves. Ireland: size down
30–50%, take 1R instead of 2R. Rader: negative gamma is a "reflexive cycle", positive gamma is
range-compressing. All three also arrive independently at heavy non-participation — Ireland
took zero trades Mon/Tue/Wed of the week he presents.

**This is what RES003 went and tested.** Result: the mechanism is real; the trophy is not
evidence. See [RES003](../RES003_volatility_regime_sizing/RESULTS.md).

## What Rader adds that the other two do not — and that RES003 did NOT test

Rader breaks the convergence in a way worth naming, because he makes a **directional** claim
where the other two explicitly refuse to.

1. **The "JEX flip"** (18:39–24:01). After 5–20 consecutive positive-gamma closes, the *first*
   close or gap into negative gamma predicts **downside** — an opening-range-break short, then
   an "afternoon roll" short into the 11:00–13:00 chop. This is a claim about a **transition**,
   not a level.

   **RES003's Test B classified regime by static VIX-percentile terciles and would miss a
   transition effect entirely.** So the B null does not speak to this claim. Untested.

2. **Dispersion rotation** (14:18–17:53). In positive gamma, index ranges compress and flow
   rotates to single names, so trade individual tickers; in negative gamma, index moves
   dominate relative to market cap, so trade indices. This is a second-moment claim about
   **dispersion**, which makes it estimable at our sample size.

Both are testable on data we already have. Neither has been tested. They are the obvious
RES004 if Saiful wants it.

## Out of scope regardless

Instrument (micro futures, 0DTE options), horizon (5-minute candles), and data (footprint
ladders, level 2, real GEX) are all outside what AMI Trade is or has. Nothing about the
execution layer transfers — simulation-only is locked.
