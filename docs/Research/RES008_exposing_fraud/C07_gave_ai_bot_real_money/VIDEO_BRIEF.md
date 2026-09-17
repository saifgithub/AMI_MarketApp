# C07 — VIDEO BRIEF — What one winning week proves

**Verdict:** `DISPROVED` · **Pre-registration commit:** `3ac320eb` · **Results:** [`RESULTS.md`](RESULTS.md)
**Runtime target:** 9–11 min · **Format:** faceless, chart-driven, voice-over
**Claim class reach (measured 2026-09-17):** 2 videos · 6.12M views — the largest of any class surveyed

## Search intent

- **Primary keyword:** AI trading bot tested
- **Secondary:** I gave an AI bot money · trading bot results one week · does RSI strategy work
- The primary keyword appears in the title, the first spoken sentence, and the first line of the description.
- "AI trading bot" is the genre's search term and is used only as that. Our own product is AMI, by name.

## Title options (≤ 60 characters, all literally true)

1. *AI trading bot tested: a random bot wins 1 week in 2*
2. *We built 2,000 bots with zero skill. Half beat the market.*
3. *How long until a trading bot's results mean anything?*

## Thumbnail concept

A wall of small equity lines, half green, half red, one circled. Text: "2,000 bots. Zero skill."

## Hook (0:00–0:20) — spoken, verbatim

> "AI trading bot, tested with real money: it runs for a week, it beats the market, the video gets
> six million views. We tested that a different way. We built two thousand bots that have no
> skill at all — they pick stocks at random — and ran every week since 2005. In any given week,
> half of them beat the market. One in seven beat it by three points. So what did that winning
> week tell you?"

## Beat sheet

| # | Beat | Time | Voice-over (gist) | On screen | Source of every number |
|:--|:--|:--|:--|:--|:--|
| 1 | Cold open | 0:00–0:20 | Hook above. | 2,000 faint equity lines; a one-week window slides along; counter of "beat SPY this week" hovering near 50%. | `results_part2.json` → `zero_skill_bot.week_vs_spy`: `share_beats_spy` 0.5056, `share_beats_spy_by_3pt` 0.1483; `meta.n_bots` 2000; reach from `TRACKER.md` |
| 2 | The stakes | 0:20–0:50 | After a video like that the viewer rents the bot or copies the rule — and sizes it like the video did, most of the account per trade. | Our own mock "bot P&L: +4.1% this week" panel. | — |
| 3 | What would convince us | 0:50–2:00 | Written down first. If a random bot beat the index in fewer than a quarter of weeks, a winning week would mean something. And for the one rule that was actually disclosed: if its entries beat 95% of random entries, in two separate periods, that's real timing. | `PREREGISTRATION.md`, commit `3ac320eb`. | `PREREGISTRATION.md` |
| 4 | The test, as taught | 2:00–4:00 | The disclosed rule: buy when RSI drops under 30, sell above 70. Run it on 22 large stocks. And it looks wonderful: it wins 8 trades in 10. On one stock, 9 out of 9. | Trade list scrolling, green ticks. "227 wins of 284". | `derived_extras.json` → `rsi_rule_pooled_trades`: DEFINE 227/284 (0.799), HOLDOUT 118/155 (0.761); AAPL HOLDOUT 9 of 9 |
| 5 | The fair test + reveal | 4:00–7:00 | Two comparisons the videos don't make. Against simply holding: the rule earned less on 19 of 22 stocks, then 20 of 22 in the later period — that 9-for-9 stock returned +247% against +836% for holding it. Against random entries with the same number of trades: 57th percentile. Indistinguishable from chance. Then the zero-skill bots: a coin flip per week, ±5 points either way in the middle 90%; four winning weeks in a row, one time in sixteen. | Bars: rule vs buy-and-hold per ticker. Placebo distribution with the rule's marker at 57–58. `one_week_vs_spy.png`. | `results_part1.json` pooled: `n_tickers_beat_buy_hold_net` 3 and 2 of 22; `mean_placebo_percentile` 0.573 (0.482–0.676), 0.583 (0.505–0.657); AAPL row: 2.467 vs 8.362; `week_excess_percentiles` p5 −0.0498, p95 +0.0527; `derived_extras.json` four-in-a-row 0.0618 |
| 6 | Why | 7:00–8:40 | A week of one bot's trades is a handful of bets on volatile stocks. The gap between bot and index swings about 3¼ points a week by chance. An edge worth having — say five points a *year* — is a tenth of a point a week. To see it through that noise you need about 4,500 weeks. Eighty-seven years. | The arithmetic, one line at a time. | `sample_size_arithmetic`: sigma 0.03243, mu 0.00096 → 4,549 weeks (87.5 years); monthly 966 months (80.5 years) |
| 7 | What is true | 8:40–9:50 | This cuts both ways: a *losing* week proves nothing either, and nothing here says the bots in those videos are bad — their logic isn't public, so nobody can check, including us. The months that look best are the ones where everything went up: in those, even random long trades win 6 in 10. And we assume every week shown really happened as shown. | `trending_month_winrate.png`: 60.9% vs 52.7%. | `trending_month_conditional`: `trend_trade_win_rate` 0.6088, `unconditional_trade_win_rate` 0.5265, 479 of 5,427 windows |
| 8 | Check the next one yourself | 9:50–10:30 | The question: how many independent periods is this result, and what would a random bot have done over the same ones? One week is one. | The question as a card. | — |
| 9 | AMI + disclaimer | last 15 s | AMI Trade is a simulator: many decisions, simulated money, a record long enough to read. Simulation-only, no edge promised. | AMI end card, disclaimer. | — |

## The one idea

One winning week is what no skill looks like half the time — the result was never the evidence.

## What we must not say

- Nothing about any specific bot or product. Undisclosed logic is untested; say so on camera.
- Not that results were faked or cherry-picked. We assume they happened as shown.
- Not "RSI doesn't work". One rule, long/flat, 22 large stocks, daily and hourly bars.
- The 80% / 76% win rate and the 9-of-9 are derived from per-ticker rows after the run — true, traceable, not pre-registered. Label them "derived" in the description.
- The trade-win-rate intervals printed in `summary.txt` are far too narrow (correlated trades). Quote point estimates only: "about 6 in 10".
- The zero-skill bot's gap sizes (±5 points a week) come from its design — three positions in volatile large caps, the same concentration as the videos. A diversified bot would show smaller gaps; the coin flip stays.
- No claim that 87 years is exact; it is the two-standard-error arithmetic at the measured volatility.

## Description (first 160 characters are the search snippet)

AI trading bot tested: 2,000 bots with zero skill beat the market in 50.6% of weeks since 2005.
Here is what a one-week or one-month result can and cannot show.

Pre-registered before any code existed. Part 1: the one disclosed rule (RSI under 30 buy, over 70
sell) on 22 large US stocks, 2005–2018 and 2019–2026, against buy-and-hold and against random
entries. Part 2: 2,000 random-entry bots, every 5-day and 21-day window since 2005, against SPY,
plus the track-record length a real edge would need. Derived figures are labelled in the repo.

Links: claim folder (pre-registration · code · outputs) · episode page · AMI Trade (UTM).
Disclaimer: educational content; AMI Trade is a simulation-only training product; nothing here is
investment advice. By policy we test claims and name no channel.

## Pinned comment

Pre-registered on 2026-09-17 in commit `3ac320eb`, before any test ran. All four predictions held;
one only narrowly (RESULTS.md §4) and we say why its printed interval is too tight. Reproduce:
RESULTS.md §6, about 25 minutes. Found an error? A verified one gets a pinned correction.

## Shorts cut-down (≤ 40 s)

"A trading rule that won 9 trades out of 9." → the trade list → "It made 247%. Holding the same
stock made 836%." → "Win rate isn't return." Full test on the channel.

## Chart pack (from `out/`)

| Figure | Use | Restyle notes (AMI hex, 16:9, dark) |
|:--|:--|:--|
| `one_week_vs_spy.png` | Beats 1, 5 | Histogram of weekly excess return, zero line, shade ≥ +3 points and print 14.8%. |
| `trending_month_winrate.png` | Beat 7 | Two bars, 60.9% vs 52.7%; no error bars (see "must not say"). |
| Rule vs buy-and-hold, 22 tickers × 2 windows (to draw) | Beat 5 | From `results_part1.json` per-ticker `net_total_return` vs `buy_hold_total_return`. |
| Placebo distribution with marker (to draw) | Beat 5 | Percentiles 57 / 58 with their intervals. |
| 2,000 bot lines (to draw) | Beats 1, thumbnail | Re-run `run_part2.py` to regenerate the arrays; plot a 200-line sample. |

## Compliance checklist

- [ ] No creator / channel / title / clip / thumbnail referenced, on screen or spoken
- [ ] No real bot's or broker's interface on screen — mock-ups are ours
- [ ] "We tested this claim" language; no *fraud*, *scam*, *liar*
- [ ] Every number traced to `results_part1.json` / `results_part2.json` / `derived_extras.json`
- [ ] Limits stated on camera: undisclosed bots untested; results assumed genuine; bot design drives gap size
- [ ] No strategy offered in return; ends on method
- [ ] AMI by name; simulation-only; not investment advice
- [ ] EN script flagged for AR / MS translation at v1.0
