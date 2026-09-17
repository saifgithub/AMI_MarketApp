# C02 — VIDEO BRIEF — We asked three chatbots for 30 strategies

**Verdict:** `DISPROVED` · **Pre-registration commit:** `3ac320eb` · **Results:** [`RESULTS.md`](RESULTS.md)
**Runtime target:** 9–11 min · **Format:** faceless, chart-driven, voice-over
**Claim class reach (measured 2026-09-17):** 3 videos read · 3.28M views · at least 8 videos in the pattern

## Search intent

- **Primary keyword:** ChatGPT trading strategy tested
- **Secondary:** AI made me a trading strategy · chatbot trading strategy backtest · can AI write a profitable strategy
- The primary keyword appears in the title, the first spoken sentence, and the first line of the description.
- The keyword is the genre's search term, and the episode says in the first minute that **our** strategies were written by Claude models, not by the chatbot in the keyword. Our own product's assistant is AMI, by name.

## Title options (≤ 60 characters, all literally true)

1. *ChatGPT trading strategy tested? We tried 30 from chatbots*
2. *30 chatbot trading strategies. 0 beat buy-and-hold.*
3. *We asked 3 chatbots for a profitable strategy. 30 times.*

Title 1 is a question about the genre; if it reads as implying we tested that vendor's chatbot,
use 2 or 3.

## Thumbnail concept

A chat bubble reading "Here is a profitable strategy…" over a grid of 29 small equity curves, each
with a grey buy-and-hold line above it. Text: "30 strategies. 0 beat holding."

## Hook (0:00–0:25) — spoken, verbatim

> "ChatGPT trading strategy, tested — that's the search that brought you here, so here is what we
> did. Ten one-line prompts, the ones these videos use. Three chatbots — ours are Claude models,
> and we'll say which. Thirty strategies, coded by the chatbots themselves. Then twenty-two
> stocks, seven and a half years they were never tuned on, costs included. Strategies that beat
> simply holding: zero. Strategies that timed their entries better than random: zero. Strategies
> we could make look great in a screenshot: twenty-eight out of twenty-nine."

## Beat sheet

| # | Beat | Time | Voice-over (gist) | On screen | Source of every number |
|:--|:--|:--|:--|:--|:--|
| 1 | Cold open | 0:00–0:25 | Hook above. | Three counters: "beat holding 0", "beat random 0", "great screenshot 28/29". | `results.json`: H1 count 0 of 29; strategies ≥ 95th percentile 0; `as_shown.looks_profitable` 28 of 29 |
| 2 | The stakes | 0:25–0:50 | The video ends on a green equity curve, and the viewer's next step is to run that rule with real money — on the one ticker it was shown on. | Our own mock strategy-tester panel, "Net profit" highlighted. | — |
| 3 | What would convince us | 0:50–1:50 | Written down before a single strategy was generated: if half of them beat buy-and-hold on most stocks in the later period, or if eight of thirty beat 95% of random entries in both periods, the claim holds and we say so. We predicted at most six and at most three. | `PREREGISTRATION.md`, commit `3ac320eb`; the ten prompts scrolling. | `PREREGISTRATION.md` |
| 4 | The test, as taught | 1:50–4:00 | Same prompts, fresh chatbots that know nothing about the test, and the chatbot writes its own code so nobody can say we mis-read it. Then the screenshot, the way it's done: best ticker, no costs, no benchmark. 28 of 29 look profitable — from +34% to +2,398%. | The as-shown wall: 28 green curves, tickers and returns labelled. | `as_shown.best_ticker_gross_total_return` min 0.337, max 23.977; 28 of 29 |
| 5 | The fair test + reveal | 4:00–7:00 | Add the line the screenshot leaves out: holding the same stock. Only 10 of the 28 beat it — one shows +253% on a stock that made +3,274%. Now every stock, the years after, with costs. Beat holding on most stocks: 0 of 29. Of 578 strategy-and-stock pairs, 38 won — every one of them on the three stocks that went nowhere or down, plus one coin. The strategy that never places a trade "won" there too. Then skill: against random entries with the same number of trades, the median strategy lands at the 50th percentile. None reaches 95. | Same wall with grey buy-and-hold lines appearing above the curves. The 578-cell grid, 38 lit, all in three columns. `placebo_percentiles.png`. | `as_shown.beats_buy_hold_on_best_ticker` 10; `p01_opus` AMZN 2.526 vs 32.737; HOLDOUT cells 38 of 578 (BA 15, DIS 12, PFE 10, ETH 1); median S2 49.7, max 85.5 |
| 6 | Why | 7:00–8:30 | A chatbot has read every trading book, so it gives you the book: moving averages, RSI pullbacks, breakouts, MACD. One model gave the same RSI rule to four different prompts. These rules are in the market about a quarter of the time, in years when the typical stock returned 248%. And nothing is out-of-sample for a chatbot — it has read about all of these years, which should have *helped*. | The 29 rules sorted into five families. Exposure bar: 26%. | `catalogue.md`; `exposure_median` across strategies 0.264; median buy-and-hold 2.483 |
| 7 | What is true | 8:30–9:50 | The chatbots wrote working code: 26 of 30 ran first time and none peeked at the future. And they mostly didn't make the claim — 25 of 30 replies promised nothing, several opened by refusing to. Asked for "at least a 70% win rate", two of them gave a rule, said published tests show 70-odd percent, and they were nearly right: 66 and 64. It returned 18% and 41% per stock while holding returned 248. Most of these rules made money. They made less than doing nothing. | Quotes from the replies (ours, stored in the repo). The 66% / +18% vs +248% card, linking to the win-rate episode. | `gate_results.json` 26 / 3 / 1; `catalogue.md` 25 of 30; `p08_opus` 795 of 1,204, median net +0.184; `p08_sonnet` 2,234 of 3,519, +0.406 |
| 8 | Check the next one yourself | 9:50–10:30 | Three questions for any strategy screenshot: which other tickers? what did holding do? what happened after the dates on screen? | The three questions as a card. | — |
| 9 | AMI + disclaimer | last 15 s | AMI Trade is a simulator: a twelve-analyst team you direct, on simulated money, with the benchmark always on screen. Simulation-only, no edge promised. | AMI end card, disclaimer. | — |

## The one idea

A chatbot hands you the textbook, and the textbook's rules time entries no better than chance —
the screenshot looked good because someone picked the ticker and left out the benchmark.

## What we must not say

- Not "ChatGPT" as the thing we tested. We tested Claude Haiku 4.5, Sonnet 5 and Opus 5 and say so in the hook. No claim about any other vendor's model.
- Not "AI can't trade" or "chatbots are useless". They coded correctly and mostly declined to promise profits. The claim tested is that the chatbot supplies an edge.
- Not "these strategies lose money". Most made money; they made less than holding.
- Not "0 of 30". One strategy was excluded at the gate for a missing import — say "29 scored".
- 29 strategies are not 29 independent ideas (RESULTS §1). Do not multiply odds across them.
- Nothing on risk-adjusted returns. Lower exposure also means smaller drawdowns; we draw no conclusion either way and must not imply holding is "safer" or "better" for a given viewer.
- Verify before recording that the AMI end-card line ("benchmark always on screen") matches the shipped app; if not, use the standard line from the template.
- The quoted chatbot replies are ours, stored in `out/generated/`. Never show a reply from any video.

## Description (first 160 characters are the search snippet)

ChatGPT trading strategy tested? We had three chatbots write 30 strategies from the usual prompts.
Beat buy-and-hold: 0 of 29. Better than random entries: 0.

Pre-registered before any strategy was generated. Ten one-line prompts × three chatbots (Claude
Haiku 4.5, Sonnet 5, Opus 5 — not the chatbot in the search term), coded by the chatbots
themselves, checked for look-ahead, then run on 22 large US stocks and ETFs (2 cryptocurrencies
for the Bitcoin prompt), 2005–2018 and 2019–2026, costs included, against buy-and-hold and against
500 sets of random entries per stock. Every reply and every line of generated code is in the repo.

Links: claim folder (pre-registration · code · outputs) · episode page · AMI Trade (UTM).
Disclaimer: educational content; AMI Trade is a simulation-only training product; nothing here is
investment advice. By policy we test claims and name no channel.

## Pinned comment

Pre-registered on 2026-09-17 in commit `3ac320eb`, before any strategy was generated. All three
predictions held. One generated strategy was excluded for a coding error and one never trades —
both are in RESULTS.md §1, along with a first batch of replies we discarded before scoring because
our tooling had contaminated the prompts. Found an error? A verified one gets a pinned correction.

## Shorts cut-down (≤ 40 s)

"We asked a chatbot for a strategy with a 70% win rate." → its reply on screen → "It won 66%.
Nearly right." → "It made 18%. Holding made 248%." → "Win rate isn't return." Full test on the
channel.

## Chart pack (from `out/`)

| Figure | Use | Restyle notes (AMI hex, 16:9, dark) |
|:--|:--|:--|
| `placebo_percentiles.png` | Beat 5 | Plain-word labels ("Prompt 8 · Opus"); keep the 50 and 95 lines; note the one strategy with no trades. |
| `as_shown_vs_holdout.png` | — | **Do not use as is.** It plots returns relative to buy-and-hold, so the "screenshot" bars point the wrong way for the story. |
| As-shown wall (to draw) | Beats 4, 5 | 28 curves in **absolute** terms from `as_shown`; second pass adds the grey buy-and-hold line from `best_ticker_buy_hold_gross_total_return`. |
| 578-cell grid (to draw) | Beat 5 | 29 rows × tickers from HOLDOUT `cells[*].beats_buy_hold_net`; the lit cells fall in three columns. |
| Rule families (to draw) | Beat 6 | From `catalogue.md`. |

## Compliance checklist

- [ ] No creator / channel / title / clip / thumbnail referenced, on screen or spoken
- [ ] No real charting platform's tester on screen — the mock-up is ours
- [ ] Hook states which chatbots we used; no claim about any other vendor's model
- [ ] "We tested this claim" language; no *fraud*, *scam*, *liar*
- [ ] Every number traced to `results.json`, `gate_results.json` or `catalogue.md`
- [ ] Limits stated on camera: 29 not 30; not independent ideas; rising market; survivorship
- [ ] No strategy offered in return; ends on method
- [ ] AMI by name; simulation-only; not investment advice
- [ ] EN script flagged for AR / MS translation at v1.0
