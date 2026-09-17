# C05 — VIDEO BRIEF — The "99% win rate" strategy won 43%

**Verdict:** `PARTLY HOLDS` by our pre-registered rule — headline claim (80–99% win rate) fails in all 12 cells · **Pre-registration commit:** `3ac320eb` · **Results:** [`RESULTS.md`](RESULTS.md)
**Runtime target:** 10–12 min · **Format:** faceless, chart-driven, voice-over
**Claim class reach (measured 2026-09-17):** 2 videos · 2.17M views — includes the single most-viewed video in the survey

> **Read this first.** This is the one episode where our own rule scored *for* the claim on a
> secondary condition. The episode says so in the hook and spends a full beat on it. That is the
> point of the series; do not cut it for time.

## Search intent

- **Primary keyword:** 99% win rate strategy tested
- **Secondary:** UT Bot STC strategy backtest · best scalping strategy tested · high win rate strategy
- The primary keyword appears in the title, the first spoken sentence, and the first line of the description.
- The indicators are public formulas and are named. No platform's interface is shown.

## Title options (≤ 60 characters, all literally true)

1. *99% win rate strategy tested: the best version won 43.6%*
2. *We ran the "99% win rate" strategy 9,363 times*
3. *The 99% win rate strategy, tested. We got 33% to 44%.*

## Thumbnail concept

A dial labelled "WIN RATE" with the needle at 43 and a ghost needle at 99. Text: "99% → 43.6%".

## Hook (0:00–0:25) — spoken, verbatim

> "The ninety-nine percent win rate strategy, tested. Two free indicators, one confirming the
> other, and a title that says ninety-nine percent. We coded the rules exactly as given and let
> them trade — seven markets, three timeframes, nine thousand three hundred and sixty-three
> trades. The best version won forty-three point six percent of the time. And one thing we did
> not expect: by the rule we wrote down before testing, we still have to score this one
> 'partly holds'. We'll show you both."

## Beat sheet

| # | Beat | Time | Voice-over (gist) | On screen | Source of every number |
|:--|:--|:--|:--|:--|:--|
| 1 | Cold open | 0:00–0:25 | Hook above. | Trade counter running to 9,363; win-rate dial settling at 43.6. | `results.json` → sum of `n_trades` = 9,363; `V1_loose_60m.win_rate.estimate` 0.4359 |
| 2 | The stakes | 0:25–0:55 | Someone who expects nine wins in ten sizes their trades for nine wins in ten. At four in ten, the same sizing meets long losing runs it was never built for. | Our own mock chart with the two indicators; position-size field highlighted. | — |
| 3 | What would convince us | 0:55–2:00 | Written down first, two ways the claim could win. One: 80% wins on the hourly chart — the headline holds. Two: the entries earn more than random entries under the same stop and target, hourly and daily — "partly holds: a real signal, not a 99% one". We predicted neither. | `PREREGISTRATION.md`, commit `3ac320eb`, both conditions highlighted. | `PREREGISTRATION.md` |
| 4 | The test, as taught | 2:00–4:00 | The recipe: UT Bot alert for the trigger, Schaff Trend Cycle to confirm, stop at the recent swing, target 1.5 or 2 times the stop. Two published settings, two readings of the filter, three timeframes: 12 versions, 7 markets. Winning examples are easy to find — four trades in ten win. | The rules as a card; then three winning trades in a row, then the camera pulls back to all of them. | `PREREGISTRATION.md` recipe table; win rates from `results.json` |
| 5 | The fair test + reveal | 4:00–6:30 | All 12 versions: 33% to 44%. None reaches 44; the top of the widest interval is 46.7. Then the money: average profit per trade is below zero after costs in all 12, and before costs no version is clearly above zero. On the 5-minute chart — where this is taught — costs alone eat half of one R per trade. | `win_rate_vs_claim.png`: 12 dots far under the 80 and 99 lines. Expectancy bars, net and gross, zero line. Cost-in-R bars: 0.02 daily · 0.09 hourly · 0.52 five-minute. | `results.json` per cell: `win_rate`, `expectancy_r.net`, `expectancy_r.gross`, `avg_cost_r` (0.510–0.527 on 5m) |
| 6 | Why | 6:30–8:00 | Where a win rate comes from. Put your target 1.5 times as far as your stop and a coin flip wins 40% — one over one-plus-1.5. Make it 2 and it's 33%. Every version landed within about four points of those two numbers. The win rate was set by where the target sits, not by the indicator. | The line `1 / (1 + target)`, two markers at 40 and 33.3, the 12 dots dropping onto it. | Arithmetic; gaps computed from `results.json` (largest 4.0 points, `V2_loose_60m`) |
| 7 | What is true — and where our own rule went against us | 8:00–10:20 | On the hourly chart these entries *did* beat random entries: 43% against 35–41. By the rule we wrote, that plus the daily result is "partly holds", and that is the verdict. Then what we found afterwards — labelled as after-the-fact. Our yardstick was flawed: we measured in R, and random entries sit closer to their swing low, so they paid five to eight times the costs in R. On daily bars, every measure without that flaw puts the recipe level with random. On hourly bars the gap survives every check we built — but we can't yet separate timing from stop placement, and the long trades made all the money while the shorts lost in all 12 versions, in a sample where all seven markets rose. After costs: about zero. | The verdict card: "PARTLY HOLDS — by our rule". Then a stamp "AFTER THE FACT" over: cost-in-R comparison; the daily percentile table; long vs short bars. | `results.json` placebo bands; `posthoc_diagnostic.json`: `avg_cost_r`, `stop_dist_pct`, daily percentiles (0.058–0.666), by-side pooled (RESULTS §5) |
| 8 | Check the next one yourself | 10:20–11:00 | Two questions. What is the target-to-stop ratio — and what win rate does that ratio hand you for free? And: how many trades is this, chosen by whom? | The two questions as a card. | — |
| 9 | AMI + disclaimer | last 15 s | AMI Trade is a simulator: practise sizing and decisions on simulated money, with the record kept for you. Simulation-only, no edge promised. | AMI end card, disclaimer. | — |

## The one idea

A win rate is mostly a property of where the target and stop sit. This recipe's came out where its
geometry puts it — 33% to 44% — not at 99.

## What we must not say

- **Not "debunked", not "disproved".** The verdict is `PARTLY HOLDS` and the word is said on camera. What failed is the headline number.
- Not "the indicators are useless". On hourly bars the entries beat every random-entry arm we built.
- Not "it loses money" without the qualifier. After costs the average is below zero in all 12 versions, but on hourly and daily bars the interval includes zero. Only the 5-minute result is clearly negative — and that is 60 days of data.
- Nothing about where the 99% came from, and no suggestion anyone miscounted or misled. Two chart examples are not a sample; that is all we say.
- Do not quote the 55% hand count from the pre-registration on camera — it points at one specific video.
- Everything in beat 7 after the verdict card is post-hoc and carries that label on screen for as long as it is shown.
- Do not present the stop-geometry explanation as established. We showed the yardstick was flawed; we did not measure how much of the hourly gap it explains.
- "Swing low" is our 10-bar rule. A discretionary trader would place it differently; say so once.

## Description (first 160 characters are the search snippet)

99% win rate strategy tested: UT Bot + STC coded as taught, 9,363 trades, 7 markets, 3 timeframes.
Best version won 43.6%. Average trade after costs: below zero.

Pre-registered before any code existed. 12 versions (2 published settings × 2 readings of the
filter × 5-minute, 60-minute and daily bars) on BTC, ETH, SPY, QQQ, AAPL, NVDA, TSLA, costs
included, each compared with 500 sets of random entries under the same stop and target. By our own
pre-registered rule the verdict is "partly holds" — the hourly entries beat random ones — and the
results explain why we think part of that rule was badly built. After-the-fact analysis is
labelled as such in the repo.

Links: claim folder (pre-registration · code · outputs) · episode page · AMI Trade (UTM).
Disclaimer: educational content; AMI Trade is a simulation-only training product; nothing here is
investment advice. By policy we test claims and name no channel.

## Pinned comment

Pre-registered on 2026-09-17 in commit `3ac320eb`, before any test ran. Two of our three
predictions were wrong on this one, and our own rule scores the claim "partly holds" — RESULTS.md
§4 and §5 show exactly how, including the flaw we found in our own yardstick. Found an error?
A verified one gets a pinned correction.

## Shorts cut-down (≤ 40 s)

"Set your target 1.5 times your stop and a coin flip wins 40% of the time." → the line
`1 / (1 + target)` → "The '99% win rate' strategy, 9,363 trades: 43.6% at best." → "The win rate
came from the target, not the indicator." Full test on the channel.

## Chart pack (from `out/`)

| Figure | Use | Restyle notes (AMI hex, 16:9, dark) |
|:--|:--|:--|
| `win_rate_vs_claim.png` | Beat 5 | Keep the 80 and 99 lines and the two break-even lines; plain-word cell labels ("Setting 1 · strict · hourly"). |
| Win rate vs `1 / (1 + target)` (to draw) | Beat 6, Short | 12 dots from `results.json`, two horizontal markers at 40 and 33.3. |
| Expectancy bars, net and gross with intervals (to draw) | Beat 5 | From `expectancy_r`; zero line prominent. |
| Cost in R by timeframe (to draw) | Beats 5, 7 | Recipe 0.02 / 0.09 / 0.52; in beat 7 add the placebo's 0.13 / 0.53 / 3.2–4.0 under the "after the fact" stamp. |
| Long vs short, net % per trade (to draw) | Beat 7 | From RESULTS §5 table; "after the fact" stamp. |

## Compliance checklist

- [ ] No creator / channel / title / clip / thumbnail referenced, on screen or spoken
- [ ] No real charting platform's interface on screen — mock-ups are ours
- [ ] "We tested this claim" language; no *fraud*, *scam*, *liar*; no "debunked" for this episode
- [ ] Verdict `PARTLY HOLDS` spoken and shown
- [ ] Every number traced to `results.json` or `posthoc_diagnostic.json`; post-hoc numbers stamped
- [ ] Limits stated on camera: about 60 days of 5-minute data, two to three years of hourly, all seven markets rose over it, 10-bar swing rule
- [ ] No strategy offered in return; ends on method
- [ ] AMI by name; simulation-only; not investment advice
- [ ] EN script flagged for AR / MS translation at v1.0
