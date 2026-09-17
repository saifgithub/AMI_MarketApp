# C06 — VIDEO BRIEF — The grid bot's profit number vs the account

**Verdict:** `NOT SUPPORTED` · **Pre-registration commit:** `3ac320eb` · **Results:** [`RESULTS.md`](RESULTS.md)
**Runtime target:** 9–11 min · **Format:** faceless, chart-driven, voice-over
**Claim class reach (measured 2026-09-17):** 3 videos · 0.92M views

## Search intent

- **Primary keyword:** grid trading bot tested
- **Secondary:** do grid bots work · grid bot passive income · grid bot results
- The primary keyword appears in the title, the first spoken sentence, and the first line of the description.

## Title options (≤ 60 characters, all literally true)

1. *We tested grid trading bots. The dashboard hides the loss.*
2. *Grid trading bot tested: 22,356 runs, one missing number*
3. *Grid bot: green 99.6% of the time. Account down 37%.*

## Thumbnail concept

Two numbers side by side, same size: **99.6%** (green, labelled "bot says") and **37%** (red,
labelled "accounts down"). Four words maximum: "Same runs. Both true."

## Hook (0:00–0:20) — spoken, verbatim

> "A grid trading bot makes money whether the market goes up or down — set it, leave it, collect
> the income. Videos teaching that have around nine hundred thousand views. So we tested the grid
> trading bot: twenty-two thousand runs. The bot's own profit number was green in ninety-nine point
> six percent of them. The account was down in thirty-seven percent. Both numbers are correct, and
> this video is about the gap between them."

## Beat sheet

| # | Beat | Time | Voice-over (gist) | On screen | Source of every number |
|:--|:--|:--|:--|:--|:--|
| 1 | Cold open | 0:00–0:20 | Hook above. | The two numbers, then the scatter building point by point. | `grid.pooled["daily\|pooled\|lev=1.0x"]`: `share_grid_profit_positive` 0.9965, `share_true_pnl_negative` 0.3680; `grid.n_total_runs` 22,356; reach from `TRACKER.md` |
| 2 | The stakes | 0:20–0:50 | What happens next: a viewer funds a bot, often with leverage because the tutorial's returns assume it, and reads the dashboard as their balance. | A generic bot panel we drew ourselves — "Grid profit +$412" — no real product UI. | — |
| 3 | What would convince us | 0:50–2:00 | We wrote down beforehand what would support the claim: any setting whose account was flat-or-up in 90% of 90-day runs, across a window that contains two bear markets. And four predictions of our own. Two of those turned out wrong — we'll show you which. | Scroll of `PREREGISTRATION.md`; commit `3ac320eb`, dated 2026-09-17. | `PREREGISTRATION.md` |
| 4 | The test, as taught | 2:00–4:00 | The mechanism exactly as the tutorials set it up: a price range, evenly spaced lines, buy each line down, sell each line up. ±10/20/30%, 10/20/50 lines, BTC and ETH, a new 90-day run every week, 10 bps a side. Count the completed pairs and you get their picture: green almost every time. | Animated grid on a price path; counter of completed pairs. Then: "grid profit positive — 99.65% of 9,522 runs". | `share_grid_profit_positive` 0.9965, `n_runs` 9,522 |
| 5 | The fair test + reveal | 4:00–7:00 | Now mark the whole account, including the coins the bot is still holding. Down in 36.8% of runs. Median run +3.35% over 90 days; one run in twenty lost 37% or worse; the best one in twenty made 11.5%. Price left the range in 88% of runs. Then 5× leverage, which the income figures usually need: one run in three liquidated. | The scatter (`grid_dashboard_vs_truth.png`): every point right of zero, a third of them below it. Then the percentile bar: −37.2% … +3.35% … +11.5%. Then the 5× liquidation counter: 32.54%. | `share_true_pnl_negative` 0.3680; `median_true_pnl_frac` 0.0335; `p05` −0.372; `p95` 0.1148; `share_left_range` 0.8771; `grid.pooled["daily\|pooled\|lev=5.0x"].share_liquidated` 0.3254 |
| 6 | Why | 7:00–9:00 | A grid sells winners early and keeps buying losers. Inside the range it collects small spreads. Above the range it has sold everything and watches. Below the range it has bought every line down and holds the lot. Upside capped near the grid's width, downside the coin's. The dashboard counts only finished pairs — it has no line for the unfinished ones. | Payoff sketch: capped top, open bottom. Two example runs from the data, one each side. | `p95` 0.1148 vs `p05` −0.372; `share_left_range_up` 0.5974, `share_left_range_down` 0.4729 |
| 7 | What is true | 9:00–10:00 | We predicted the grid would lose to simply holding the coin. It didn't: it beat buy-and-hold in 51% of runs — a coin flip. A grid is a legitimate way to be paid for providing liquidity in a range. It is a short-volatility position, and the honest tutorials say when it loses. The forex band version: wins three baskets in four, earns 0.2–0.7% a month on daily bars, and the size that gets you 0.7% is ruined within five years from 29–52% of start dates. We also predicted a higher win rate than it has. | "Our predictions: 2 of 4 wrong" card. Band-grid table. | `share_beat_buy_hold` 0.5109; `band_grid.pooled["daily\|pooled\|…"]`: win rates 0.730–0.769, median monthly 0.0023–0.0073, 5-y ruin 0.288 (constant 2×) and 0.515 (martingale 2×), `n_eligible` 198 |
| 8 | Check the next one yourself | 10:00–10:40 | One question for any bot video: is the number on screen the account's value, or only the closed trades? Ask to see equity, including open positions, through a falling market. | The question as a card. | — |
| 9 | AMI + disclaimer | last 15 s | AMI Trade is a simulator: practise process with a twelve-analyst team and no real money. We promise no edge. | AMI end card, disclaimer. | — |

## The one idea

A grid bot reports the trades it has finished and stays quiet about the coins it is still holding.

## What we must not say

- That grid trading "doesn't work" or loses to holding — it matched buy-and-hold (51.09%) and the median 90-day run was positive. Our H2 was wrong; say so.
- Anything about a particular product. Commercial bots do not disclose their logic; we tested the generic mechanism.
- No annualising the +3.35% median. It is a 90-day median from overlapping runs, not an income rate.
- The hourly arm (≈ 2 years) is context only — median −0.18%, negative in 50.24% of runs — never the headline.
- Results are BTC/ETH spot grids and three FX pairs. Nothing beyond them.

## Description (first 160 characters are the search snippet)

Grid trading bot tested over 22,356 runs: the bot's profit number was positive 99.6% of the time
while the account was down in 37% of runs. Here is why both are true.

We pre-registered the test before running it, including four predictions of our own — two of which
were wrong. Spot grids on BTC and ETH (2014–2026), ±10–30% ranges, 10–50 lines, 90-day runs started
weekly, costs included; then the same at 5× leverage; then the forex "band grid" with no stop.

Links: claim folder (pre-registration · code · outputs) · episode page · AMI Trade (UTM).
Disclaimer: educational content; AMI Trade is a simulation-only training product; nothing here is
investment advice. By policy we test claims and name no channel.

## Pinned comment

Pre-registered on 2026-09-17 in commit `3ac320eb`, before any test ran. Reproduce:
`pytest C06_ai_grid_bot_passive_income/code` then `python C06_ai_grid_bot_passive_income/code/run_c06.py`
(≈ 14 min). Two of our four predictions failed — see RESULTS.md §4. Found an error? Tell us; a
verified one gets a pinned correction.

## Shorts cut-down (≤ 40 s)

"Grid bot profit: green in 99.6% of runs. Account: down in 37%." → the scatter, points falling below
zero → "The bot counts the trades it finished, not the coins it's still holding." Full test on the
channel.

## Chart pack (from `out/`)

| Figure | Use | Restyle notes (AMI hex, 16:9, dark) |
|:--|:--|:--|
| `grid_dashboard_vs_truth.png` | Beats 1 and 5 — the reveal | Unlevered runs only. Axes as % of starting capital; shade the lower-right quadrant ("bot says profit, account says loss") and print its share, 36.8%. Build the points in over 4–5 s. |
| `band_grid_equity.png` | Beat 7 | Keep the 20%-of-start ruin line. Add a 2× martingale run that ruins, taken from the same simulator, so the picture matches the 51.5% figure spoken over it. |
| Percentile bar (to draw) | Beat 5 | −37.2% · +3.35% · +11.5% from `results.json`; asymmetric on purpose. |

## Compliance checklist

- [ ] No creator / channel / title / clip / thumbnail referenced, on screen or spoken
- [ ] No real product's interface on screen — the dashboard mock-up is ours
- [ ] "We tested this claim" language; no *fraud*, *scam*, *liar*
- [ ] Every number traced to `results.json`, with its window and interval
- [ ] Limits of the test stated on camera, including our two failed predictions
- [ ] No strategy offered in return; ends on method
- [ ] AMI by name; simulation-only; not investment advice
- [ ] EN script flagged for AR / MS translation at v1.0
