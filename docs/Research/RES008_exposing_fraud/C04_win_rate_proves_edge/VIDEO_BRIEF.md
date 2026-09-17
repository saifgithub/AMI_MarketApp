# C04 — VIDEO BRIEF — We got an 89% win rate with a coin

**Verdict:** `DISPROVED` · **Pre-registration commit:** `3ac320eb` · **Results:** [`RESULTS.md`](RESULTS.md)
**Runtime target:** 8–10 min · **Format:** faceless, chart-driven, voice-over
**Claim class reach (measured 2026-09-17):** 4 videos · 2.99M views — and the win rate is the headline number in most of the other classes too

> **Series role.** This is the explainer the other episodes lean on. C05 (a "99%" recipe that won
> 43%), C07 (a rule that won 9 of 9 and earned a third of buy-and-hold) and C06 (a grid that won
> three baskets in four on its way to ruin) all link here. Release it early.

## Search intent

- **Primary keyword:** high win rate trading strategy
- **Secondary:** 90% win rate strategy · win rate vs risk reward · is win rate important in trading
- The primary keyword appears in the title, the first spoken sentence, and the first line of the description.

## Title options (≤ 60 characters, all literally true)

1. *High win rate trading strategy: 89% wins, loses money*
2. *We got an 89% win rate with coin flips. It lost money.*
3. *What a 90% win rate tells you (378,000 random trades)*

## Thumbnail concept

A dial labelled "WIN RATE" turned to 89%, with an equity line sloping down behind it. Text:
"89% wins. Coin flips."

## Hook (0:00–0:20) — spoken, verbatim

> "A high win rate trading strategy — here is ours. It wins eighty-nine percent of its trades,
> measured over fifty-four thousand of them, on twenty-seven markets. The entries are coin flips.
> And it loses money. Same coin, different setting: nineteen percent wins. The win rate was never
> telling you about the strategy. It was telling you where the target and the stop were."

## Beat sheet

| # | Beat | Time | Voice-over (gist) | On screen | Source of every number |
|:--|:--|:--|:--|:--|:--|
| 1 | Cold open | 0:00–0:20 | Hook above. | A dial turning from 89 to 19 while the same random entry markers stay put on the chart. | `results.json` → `part1_pooled_by_geometry`: `0.5:5` win rate 0.892, `n_trades` 54,000; `5:1` 0.1886; 27 instruments in `meta.universe` |
| 2 | The stakes | 0:20–0:45 | "90% win rate" is the number on the thumbnail, and it is usually the only number. Someone who trusts it sizes up — and the one trade in ten that loses is ten times the size of the ones that win. | Our own mock thumbnail wall: "88%", "90%", "99%" — no names, no real thumbnails. | — |
| 3 | What would convince us | 0:45–1:30 | Written down first: if any setting reaches 85% wins **and** makes money after costs with random entries, then a high win rate carries information on its own, and we'd say so. | `PREREGISTRATION.md`, commit `3ac320eb`. | `PREREGISTRATION.md` |
| 4 | The test | 1:30–3:00 | Entries with no information: random day, random direction. Exits: a profit target and a stop, sized to each market's own volatility. Seven settings, from "tiny target, huge stop" to "huge target, tiny stop". 2,000 trades per market per setting — 378,000 in all, 2005 to 2026, costs included. | The seven brackets drawn to scale on one chart. | `meta`: 7 geometries, `n_trades_per_cell_requested` 2000, 27 × 7 × 2,000 |
| 5 | The reveal | 3:00–5:00 | The dial: 89, 81, 73, 49, 34, 26, 19. Never more than 2.6 points from one line of arithmetic — stop divided by target plus stop — that you can work out before placing a trade. Then the money: no setting clearly above zero after costs, six of seven clearly below, and the three highest win rates are the three biggest losers. 89% wins, minus a third of a percent per trade. | `win_rate_dial.png` redrawn as two stacked panels: win-rate bars with the reference line; expectancy dots with intervals and a zero line. | win rates and `random_walk_reference_win_rate` per geometry; largest gap 2.55 points (`1:5`); `expectancy_pct.net` `0.5:5` −0.00332 (−0.00387 … −0.00280) |
| 6 | Why | 5:00–6:30 | Many small wins, paid for by rare large losses — and costs charged on every one of the many trades. We've met it three times in this series: a rule that won 9 trades of 9 and made 247% where holding made 836%; a "99%" recipe that won 43%, right where its target put it; a grid that won three baskets in four on its way to ruin. | Three cards, one per episode, each linking out. | C07 `derived_extras.json` (9 of 9, +247% vs +836%); C05 `results.json` (max 0.4359); C06 `results.json` (76.9% wins, 51.5% ruined ≤ 5 y under 2× doubling) |
| 7 | The small-sample problem | 6:30–7:50 | And the sample. 22 wins in 25 is "88%" — with a 95% interval from 70 to 96. 9 of 12 runs from 47 to 91. Two of two tells you nothing at all. Now let someone try 20 versions and show you the best: a rule that truly wins 70% — which the dial gives you for free — shows 88% half the time. | The four intervals as bars. Then the best-of-20 grid. | `part2_analytic.wilson_intervals`; `p_best_of_k_reaches_22_of_25["20"]["0.7"]` 0.4914 |
| 8 | What is true | 7:50–8:50 | Win rate isn't useless: with the average win, the average loss and the number of trades, it is half of what you need. And nothing here says a given 90% strategy loses — only that 90% can't be the proof. One honest oddity: in the two cryptocurrencies the *low* win-rate settings made money with random entries. Two coins, one history, not something we set out to test — but it's the claim upside down. | "Average win · Average loss · How many trades" card. Small crypto table, stamped "not a pre-registered test". | `part1_by_asset_class_by_geometry`: crypto `0.5:5` 0.8425 / −1.74%; `5:1` 0.2530 / +1.70% (+0.83 … +2.52) |
| 9 | Check the next one yourself + AMI | 8:50–9:30 | Three questions for any win rate: what's the average win against the average loss? How many trades? How many versions were tried? AMI Trade is a simulator; it keeps all three for you on simulated money. Simulation-only, no edge promised. | The three questions; AMI end card, disclaimer. | — |

## The one idea

A win rate, quoted alone, tells you where the target and stop were placed — not whether the
strategy makes money.

## What we must not say

- Not "win rate is meaningless". Alone, it is; with payoff ratio and sample size, it is half of expectancy.
- Not that any specific advertised strategy loses money. None was tested in this episode.
- Not "random trading loses money" as a law. Our gross figures are below zero because our fill rules are deliberately conservative (RESULTS §1). Say "none clearly above zero after costs".
- **The crypto split is not a strategy.** Two correlated coins, one history, not pre-registered, interval probably too narrow. It gets one sentence and a stamp, never a chart of its own, never in the title, thumbnail, description or Short. By policy we offer no edge in return.
- H3 was met narrowly (25.8 points against a threshold of 25). Do not call the Wilson result "huge"; show the interval and let it speak.
- The expectancy intervals are somewhat too narrow (overlapping resampled trades). Quote point estimates on camera; the sign is not in doubt at the high-win-rate end.

## Description (first 160 characters are the search snippet)

High win rate trading strategy, tested: coin-flip entries won 89% of 54,000 trades and lost money.
Same entries, different target and stop: 19%.

Pre-registered before any code existed. 378,000 random-entry, random-direction trades on 27
markets (22 stocks and ETFs, 2 cryptocurrencies, 3 currency pairs), 2005–2026, seven
target-to-stop settings, costs included. Plus the arithmetic of small samples: what 22 wins in 25
can and cannot tell you, and what happens when the best of 20 tries is the one that gets shown.

Links: claim folder (pre-registration · code · outputs) · episode page · AMI Trade (UTM).
Disclaimer: educational content; AMI Trade is a simulation-only training product; nothing here is
investment advice. By policy we test claims and name no channel.

## Pinned comment

Pre-registered on 2026-09-17 in commit `3ac320eb`, before any test ran. All three predictions
held, one narrowly (RESULTS.md §5). Our fill rules are conservative on purpose and that pushes the
before-cost figures slightly below zero — RESULTS.md §1 explains. Found an error? A verified one
gets a pinned correction.

## Shorts cut-down (≤ 40 s)

"This strategy wins 89% of its trades." → the dial → "The entries are coin flips. It loses money."
→ the dial turns → "Same coin: 19%. A win rate tells you where the stop is." Full test on the
channel.

## Chart pack (from `out/`)

| Figure | Use | Restyle notes (AMI hex, 16:9, dark) |
|:--|:--|:--|
| `win_rate_dial.png` | Beat 5, Short | **Redraw as two stacked panels** — the dual axis in the raw figure is hard to read. Top: win-rate bars plus the `stop ÷ (target + stop)` line. Bottom: net expectancy with intervals, zero line prominent. |
| The seven brackets to scale (to draw) | Beat 4 | One price path, seven target/stop pairs in multiples of *s*. |
| Wilson interval bars (to draw) | Beat 7 | 2/2, 9/12, 22/25, 31/47 from `part2_analytic`. |
| Best-of-k grid (to draw) | Beat 7 | 3 × 3 from `p_best_of_k_reaches_22_of_25`; highlight 49.1%. |
| Dial animation (to draw) | Beats 1, 5, thumbnail | Needle positions are the seven measured win rates. |

## Compliance checklist

- [ ] No creator / channel / title / clip / thumbnail referenced, on screen or spoken
- [ ] Mock thumbnails are ours and resemble no real one
- [ ] "We tested this claim" language; no *fraud*, *scam*, *liar*
- [ ] Every number traced to `results.json` (or the linked claims' outputs in beat 6)
- [ ] Crypto split: one sentence, stamped, nowhere else
- [ ] Limits stated on camera: conservative fills, daily bars, bracket exits only
- [ ] No strategy offered in return; ends on method
- [ ] AMI by name; simulation-only; not investment advice
- [ ] EN script flagged for AR / MS translation at v1.0
