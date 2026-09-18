# C06 — SCRIPT — The grid bot's profit number vs the account

**Episode:** week 10 · **Verdict:** `NOT SUPPORTED` · **From:** [`VIDEO_BRIEF.md`](VIDEO_BRIEF.md) · **Numbers:** [`RESULTS.md`](RESULTS.md), [`out/results.json`](out/results.json)
**Length:** 1,291 spoken words = 8 min 36 s of speech at 150 words a minute; with the pauses marked below (charts building in silence), ≈ 9 min 38 s · **Charts:** [`charts/`](charts/)

How to read this file: **VO** is spoken word for word. **SCREEN** is what the editor shows while it
is spoken. **№** lists every number in the beat and where it comes from — if a number is not in
that list, it must not be said. Numbers are written as they should be read aloud.

---

## 1 · Cold open — 0:00

**VO**
A grid trading bot makes money whether the market goes up or down — set it, leave it, collect
the income. Videos teaching that have around nine hundred thousand views. So we tested the grid
trading bot: twenty-two thousand runs in all. Take the main setting — nine and a half thousand of
them. The bot's own profit number was green in ninety-nine point six percent. The account was down
in thirty-seven percent. Both numbers are correct, and this video is about the gap between them.

**SCREEN** Chart `01` (the two-number card): "grid profit positive 99.65%" in amber, "account
negative 36.80%" in blue, both building in over the hook. Reach line ("~0.9M views") small,
bottom corner.

**№** 0.92M views, 3 videos — `VIDEO_BRIEF.md` reach line · 22,356 total runs across both
mechanisms and all arms — `grid.n_total_runs` · 9,522 runs in the daily 1× arm that the two
headline shares are measured on — `grid.pooled["daily|pooled|lev=1.0x"].n_runs` · 99.65% —
`…share_grid_profit_positive` · 36.80% — `…share_true_pnl_negative`

## 2 · The stakes — 0:39 (speech 0:32)

**VO**
Here's what that looks like from a chair. You fund the bot. The tutorial's income figures
usually assume leverage, so you turn some on. Then you watch one number on the dashboard: grid
profit. It only goes up, trade after trade, and you read it as your balance. It isn't. It's a
running total of the small trades the bot has already closed. What it's still holding, it doesn't
show you — and that's the part this video measures.

**SCREEN** A generic bot panel we drew ourselves: "Grid profit +$412", ticking upward. No real
product's interface, no logo, no name.

**№** —

## 3 · What would convince us — 1:14 (speech 0:48)

**VO**
Before we ran anything, we wrote down what would change our minds, and posted it in public, dated
and timestamped, before a single line of test code existed. Here's the rule: if a setting kept the
whole account flat or up in ninety percent of ninety-day runs, across a window with two bear
markets in it, that would support the claim. We also wrote down four predictions of our own, in
advance, about how the test would come out. Two of those four turned out wrong, and we're going to
tell you exactly which and why — because that's the deal we made with ourselves before we saw a
single result. A test you can't fail isn't a test.

**SCREEN** Screen-record of `PREREGISTRATION.md` at commit `3ac320eb`, dated 2026-09-17; highlight
"What would support the claim instead" and H1–H4.

**№** 90% threshold, two bear markets — `PREREGISTRATION.md` ("What would support the claim
instead") · 4 predictions, 2 wrong — `RESULTS.md` §4 (H2, H4 "not met")

## 4 · The test, as taught — 2:07 (speech 1:23 + 0:08 for the counter)

**VO**
The mechanism, exactly as the tutorials set it up. Pick a price range around where the market is
now. Draw evenly spaced lines through that range — a grid. Place a small buy order at every line
below the current price, and a small sell order at every line above it. When price falls to a
line, the buy fills: the bot now owns a little more of the coin, slightly cheaper. When price
later rises back up to the next line, the sell fills: that same little slice is sold for a small,
locked-in profit. Repeat that all day, every day, and you get a lot of small wins. We built this
exactly as the exchanges describe it: ten, twenty, or thirty percent wide ranges, ten, twenty, or
fifty lines, on Bitcoin and Ethereum, a new ninety-day run started every week, going back over a
decade, with a small trading fee charged on every fill. Count only the completed buy-low,
sell-high pairs — the number the dashboard actually shows you — and the picture is almost entirely
green: positive in ninety-nine point six five percent of nine thousand, five hundred and
twenty-two runs. That's the bot's own number. It's not wrong. It's just not the whole account.

**SCREEN** Animated grid over a price path: buy/sell lines lighting up as price crosses them.
Counter running up to 9,522 in the corner. Then "grid profit positive — 99.65%" stamped on.

**№** 10/20/30% ranges, 10/20/50 lines = 9 settings — `PREREGISTRATION.md` ("Mechanism 1") · BTC,
ETH, 90-day runs weekly — `PREREGISTRATION.md` · 99.65% of 9,522 runs —
`grid.pooled["daily|pooled|lev=1.0x"].{share_grid_profit_positive, n_runs}`

## 5 · The fair test and the reveal — 3:38 (speech 1:30 + 0:10 across the cards, bar and counter)

**VO**
Now do the fair version of the same math. Instead of only counting finished trades, mark the
whole account: cash plus whatever coin the bot is still sitting on, valued at today's price, not
the price it was bought at. Same nine and a half thousand runs, same settings. The account was
down in thirty-six point eight percent of them. Not one in a hundred, the way the dashboard's
number implies. More than one in three.

Over ninety days, the typical run made three point three five percent — a real, positive median.
But the middle of the range isn't the whole story. One run in twenty lost thirty-seven percent or
worse. The best run in twenty made eleven point five percent. Notice that gap: the worst case is
more than three times the size of the best case. That's not a coincidence — it's because price
left the grid's drawn range entirely in seven runs out of every eight, in one direction or the
other.

And when we added the leverage the "passive income" tutorials tend to lean on to make the numbers
look bigger — five times leverage — one run in three ended in liquidation. That's not a rough
patch. That's the exchange closing the account out at zero because the loss reached the size of
the money that was put up.

**SCREEN** Chart `01` and chart `02` side by side — the bot's number against the account's, the
gap held on screen. Then the percentile bar, chart `03`: −37.2% … +3.35% … +11.5%. Then the
range/liquidation panel, chart `04`, the 32.54% counter landing last. (No per-run scatter exists —
see Production notes.)

**№** 36.80% of the same 9,522 daily 1× runs — `grid.pooled["daily|pooled|lev=1.0x"].{share_true_pnl_negative, n_runs}` · median +3.35%,
p05 −37.2%, p95 +11.5% — `grid.pooled["daily|pooled|lev=1.0x"].{median_true_pnl_frac,
p05_true_pnl_frac, p95_true_pnl_frac}` · 7 runs out of 8 (87.71%) —
`grid.pooled["daily|pooled|lev=1.0x"].share_left_range` · one run in three liquidated at 5×
(32.54%) — `grid.pooled["daily|pooled|lev=5.0x"].share_liquidated`

## 6 · Why — 5:18 (speech 1:15 + 0:06 on the payoff sketch)

**VO**
Here's why the dashboard and the real account tell two different stories. A grid sells a little
every time price ticks up one line, and buys a little every time it ticks down one line. Inside
the range, that's a genuine, countable profit: small spreads, collected over and over, all day.
But once price breaks out of the drawn range, the picture splits in two. Break out upward, and the
bot has already sold everything it owned below that level — it just sits in cash from there,
watching a move it isn't part of any more. Break out downward, and the bot has spent its way down
buying every line on the way, and is now holding all of that coin, marked at a loss it hasn't
realized. So the upside is capped at roughly the width of the grid you drew. The downside is the
coin's own downside — however far it falls, the bot is still holding what it bought. The
dashboard's profit number only ever counts the trades that finished. It has no line, anywhere, for
the coins still parked in the account.

**SCREEN** Payoff sketch: capped top (flat line above the range), open bottom (line falling away
below it). Two example runs from the data, one that broke out up and one that broke out down.

**№** upside capped near +11.5% (p95), downside open near −37.2% (p05) —
`grid.pooled["daily|pooled|lev=1.0x"].{p95_true_pnl_frac, p05_true_pnl_frac}` · breakout split
59.74% up / 47.29% down (of runs; not mutually exclusive) —
`grid.pooled["daily|pooled|lev=1.0x"].{share_left_range_up, share_left_range_down}`

## 7 · What is true — 6:39 (speech 1:48 + 0:08 across the two cards)

**VO**
So which two of our four predictions missed, and why does it matter? We expected the grid to
lose to simply buying the coin and holding it. It didn't: it beat buy-and-hold in fifty-one
percent of runs. Basically a coin flip, not a loser. That's worth sitting with: a grid is a
legitimate way to get paid for providing liquidity inside a range. It is a real, definable
position — a bet that price stays roughly where it is. Its upside is just capped, and the
tutorials that sell it as one-way income don't say that part.

The other version of this claim swaps the coin grid for a currency band: sell when price stretches
above its recent average, buy more each time it stretches further, with no stop-loss at all if
it keeps going against you — that "keep adding" rule is sometimes called doubling down, or
martingale. That version wins about three baskets in every four, and earns two to seven tenths of
a percent a month at the median, across three major currency pairs and two decades of daily
prices. We expected a higher win rate than that, and we were wrong about that too. Here's the
catch buried in the good-sounding number: the position size that gets you to the top of that
range — seven tenths of a percent a month — is the exact same size that gets the account wiped out
within five years, in twenty-nine to fifty-two percent of the start dates we tested. Turn up the
size, and the income and the ruin both go up together, from the same lever.

**SCREEN** "Our predictions: 2 of 4 wrong" card (chart `07`). Then the band-grid table (chart
`08`): win rate, monthly return and 5-year ruin, size increasing left to right.

**№** beat buy-and-hold in 51.09% — `grid.pooled["daily|pooled|lev=1.0x"].share_beat_buy_hold` ·
band-grid win rate 73–77% (73.0–76.9% across sizings) — `band_grid.pooled[*].basket_win_rate` ·
median monthly return 0.2–0.7% (0.23%–0.73% across sizings) —
`band_grid.pooled[*].median_monthly_return_while_alive` · 5-year ruin 29–52% (28.8% at constant
2×, 51.5% at martingale 2×, both ≈0.7%/month) — `band_grid.pooled["daily|pooled|constant|
unit=2.0x"|"daily|pooled|martingale|unit=2.0x"].share_ruined_within_5y`

## 8 · Check the next one yourself — 8:35 (speech 0:28 + 0:03 end of card)

**VO**
So, two questions for the next "passive income" bot result someone shows you. Is that
percentage the whole account — including whatever it's still holding — or only the trades that
have already closed? And what happened to that same number the last time price left the range it
was drawn for? If neither answer is on screen, you're looking at half the picture, dressed up as
the whole thing.

**SCREEN** The two questions as a card.

**№** —

## 9 · AMI + disclaimer — 9:06 (speech 0:19 + 0:13 end card) — ends ≈ 9:38

**VO**
AMI Trade is a simulator. You direct a team of twelve analysts, on simulated money, and the
record of every decision is kept for you. It is simulation-only, and it promises no edge.
The test, the code and every number from this video are in the description.

**SCREEN** AMI end card. Disclaimer card: "Educational content. AMI Trade is a simulation-only
training product. Nothing here is investment advice."

**№** —

---

## Production notes

- **Do not say** (from the brief and the verdict discipline): "debunked", "disproved", "busted",
  "myth", "fraud", "scam", "fake", "liar", "exposed", "destroyed" · that grid trading "doesn't
  work" or loses to holding the coin (it doesn't — 51.09% beat buy-and-hold, our H2 was wrong) ·
  any reference to a channel, creator, video, thumbnail, course, exchange, bot vendor or platform,
  or any real product's interface · an annualised rate from the 90-day median · the hourly arm's
  figures as a headline (context only, per the brief).
- The word "AI" is never spoken on camera as our own description of the mechanism — the script
  calls it "a grid trading bot" / "the grid bot", matching how beat 1's hook quotes the claim, and
  refers to the mechanism itself throughout beats 4–7. AMI Trade is named only in beat 9, as our
  product, never as "the AI."
- Numbers not found in `out/results.json` or `RESULTS.md` that the brief's beat sheet gestured
  toward but that are not spoken: the exact per-cell figures behind "22,356 total runs" (grid
  1×/5× hourly/daily = 9,522 + 9,522 + 1,656 + 1,656 = 22,356, verified by direct sum — this
  breakdown itself is not spoken, only the pooled total) · the specific "$3,000 to ~$115,000 and
  to zero" anecdote from `PREREGISTRATION.md`'s "claim, as taught" section — that describes one
  video's story, not a measured result, so it is omitted entirely rather than spoken as if it were
  one of our numbers.
- `grid_dashboard_vs_truth.png` and `band_grid_equity.png`, the brief's two named source figures,
  do not exist as literal per-run scatter/equity-curve charts — see `charts/README.md`, "What the
  brief asked for that could not be supported." Beat 5's SCREEN cue and beat 7's table cue
  reference the substitute charts (`01`–`04`, `07`, `08`) that carry the same finding from pooled
  aggregates; production should not attempt to source or fabricate a per-run scatter or an
  individual equity-curve path.
- Beat 6's breakout-direction figures (59.74% up / 47.29% down) sum to more than the 87.71% total
  because a single 90-day run can leave the range on both sides; said as "of runs," not
  presented as parts of one whole, to avoid implying they sum to 100%.
- Beat 7's band-grid ranges ("73–77%" win rate, "two to seven tenths of a percent," "twenty-nine
  to fifty-two percent" ruin) are pooled-cell ranges across the six constant/martingale ×
  0.5×/1×/2× sizings, matching the way RESULTS.md's own prose (§3, §5) rounds and ranges them,
  rather than a single cell's number presented as if it were the only one.
- EN script — flag for AR / MS translation at v1.0.
