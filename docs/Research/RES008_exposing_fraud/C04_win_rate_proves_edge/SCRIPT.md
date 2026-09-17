# C04 — SCRIPT — We got an 89% win rate with a coin

**Episode:** week 1 · **Verdict:** `DISPROVED` · **From:** [`VIDEO_BRIEF.md`](VIDEO_BRIEF.md) · **Numbers:** [`RESULTS.md`](RESULTS.md), [`out/results.json`](out/results.json)
**Length:** 1,111 spoken words = 7 min 25 s of speech at 150 words a minute; with the pauses marked below (charts building in silence), ≈ 9 min 25 s · **Charts:** [`charts/`](charts/)

How to read this file: **VO** is spoken word for word. **SCREEN** is what the editor shows while it
is spoken. **№** lists every number in the beat and where it comes from — if a number is not in
that list, it must not be said. Numbers are written as they should be read aloud.

---

## 1 · Cold open — 0:00

**VO**
A high win rate trading strategy — here is ours. It wins eighty-nine percent of its trades,
measured over fifty-four thousand of them, on twenty-seven markets. The entries are coin flips.
And it loses money. Same coin, different setting: nineteen percent wins. The win rate was never
telling you about the strategy. It was telling you where the target and the stop were.

**SCREEN** Dial frame `05a` (needle at 89). Random entry markers scatter across a price chart.
On "same coin", cut to dial frame `05c` (needle at 19) — the entry markers do not move.

**№** 89.2% and 54,000 trades — `part1_pooled_by_geometry["0.5:5"]` · 27 markets — `meta.universe` · 18.9% — `["5:1"].win_rate`

## 2 · The stakes — 0:25

**VO**
"Ninety percent win rate" is the number on the thumbnail, and it is usually the only number.
If you believe it, you do the reasonable thing: you size up. Nine wins in ten feels safe. What
the thumbnail doesn't tell you is how big the tenth trade is — and in the strategy we just showed
you, the one that loses is ten times the size of the ones that win.

**SCREEN** Our own mock thumbnail wall — "88%", "90%", "99%" in generic styling. No real
thumbnail, no name, no logo. Then one bracket drawn on a chart: small target, stop ten times
further away.

**№** "ten times" — the 0.5 : 5 bracket, target 0.5 s, stop 5 s (`PREREGISTRATION.md`)

## 3 · What would convince us — 0:55

**VO**
Before we ran anything, we wrote down what would change our minds, and committed it in public.
Here it is. If any setting reaches an eighty-five percent win rate **and** makes money after
costs — with entries that carry no information at all — then a high win rate means something on
its own, and we would say so in this video. We also wrote down three predictions. The win rate
would follow one line of arithmetic. No setting would make money. And a small sample would turn
out to say much less than it seems to. You can check the date on that file against the date on
the results.

**SCREEN** Screen-record of `PREREGISTRATION.md` at commit `3ac320eb`; highlight "What would
support the claim instead" and H1–H3.

**№** 85% threshold, H1–H3 — `PREREGISTRATION.md`

## 4 · The test — 1:40 (speech 1:12 + 0:13 for the brackets to build)

**VO**
The entries: a random day, and a coin flip for direction — half the trades long, half short, so a
rising market can't help. No indicator, no pattern, nothing.

The exits: a profit target and a stop-loss. To make that fair across a sleepy currency pair and
Bitcoin, both are sized in units of each market's own typical daily range, measured up to 2018
and then frozen.

Seven settings. At one end, a tiny target with a stop ten times further away. In the middle,
target and stop the same distance. At the other end, a target five times further than the stop.

Twenty-two large stocks and funds, three currency pairs, two cryptocurrencies. Two thousand
trades per market per setting — three hundred and seventy-eight thousand trades in all, from 2005
to August 2026. Every trade pays costs: five hundredths of a percent a side on stocks, ten on
crypto, two on currencies. And when a single day touches both the target and the stop, we count
it as a loss. We'd rather be harsh on the strategy than flatter it.

**SCREEN** Chart `02` — the seven brackets side by side, to scale (green target above the entry
line, red stop below), revealed left to right. Then a counter running to 378,000.

**№** 7 settings, 2,000 per cell, 27 × 7 × 2,000 = 378,000 — `meta` · costs 5 / 10 / 2 bps a side — `PREREG_COMMON.md` · stop-first rule — RESULTS §1

## 5 · The reveal — 3:05 (speech 1:05 + 0:40: each bar lands in silence, then the money panel)

**VO**
Here is the win rate for each setting. Eighty-nine percent. Eighty-one. Seventy-three.
Forty-nine. Thirty-four. Twenty-six. Nineteen.

Same entries every time. Same coin.

Now the orange line. That is one piece of arithmetic: the stop distance, divided by the target
plus the stop. It is what a pure random walk would give you, and you can work it out on a napkin
before you place a trade. Across all seven settings, the measured win rate is never more than
two point six points away from it.

So that's the win rate. Here is the money.

After costs, no setting is clearly above zero. Six of the seven are clearly below it. And look at
which ones are worst: the three highest win rates are the three biggest losers. The
eighty-nine percent strategy loses a third of a percent of the trade's value, every trade, on
average. The only setting whose range even reaches zero is the one that wins nineteen percent
of the time.

**SCREEN** Chart `01`, top panel only, bars appearing one at a time with their numbers. Then the
orange line draws on. Then the bottom panel rises into frame; the three left-hand dots pulse.

**№** 89.2 / 80.8 / 73.2 / 49.3 / 33.5 / 26.1 / 18.9% — `win_rate.estimate` per setting · largest gap 2.55 points, at 1 : 5 — vs `random_walk_reference_win_rate` · net −0.33% (−0.39 … −0.28) at 0.5 : 5; six intervals below zero, 5 : 1 is +0.04% (−0.04 … +0.12) — `expectancy_pct.net` (stored as fractions)

## 6 · Why — 4:50 (speech 1:12 + 0:13 on the three cards)

**VO**
The mechanism is simple. With a small target and a far stop, a win earns you half a unit and a
loss costs you five. One loss takes back ten wins. Before costs that roughly washes out — ours
comes out slightly below zero, because of that harsh rule about ambiguous days. Then you pay
costs on every one of those many small trades, and it goes clearly negative.

We found the same thing in three other tests in this series. A rule that won nine trades out of nine on one
stock — and made two hundred and forty-seven percent, where simply holding that stock made eight
hundred and thirty-six. A recipe advertised at ninety-nine percent that won forty-three point
six at best — right where its target put it. And a grid robot that closed about three baskets in
four at a profit, and with a doubling rule was wiped out within five years from just over half
of all the start dates we tried.

High win rate, every time. Different outcomes, every time. The win rate wasn't the thing to
look at.

**SCREEN** One bracket with "+0.5" and "−5" labels. Then three cards, one per episode, each with
its two numbers, each a link.

**№** gross −0.078 s at 0.5 : 5 — `expectancy_units_s.gross` · 9 of 9, +247% vs +836% — C07 `out/derived_extras.json` · 43.6% — C05 `out/results.json` (`V1_loose_60m`) · 73–77% of baskets; 76.9% wins and 51.5% of start dates ruined within five years under 2× doubling — C06 `out/results.json`

## 7 · The small-sample problem — 6:15 (speech 0:54 + 0:26 on the two charts)

**VO**
There is a second problem, and it's the sample.

Twenty-two wins out of twenty-five. That's eighty-eight percent, and it sounds like a
measurement. Its ninety-five percent range runs from seventy to ninety-six. Nine wins out of
twelve: anywhere from forty-seven to ninety-one. Two out of two — which is sometimes all a video
shows — runs from thirty-four to a hundred. It tells you nothing.

Now add selection. Suppose someone tries twenty versions of a rule and shows you the best one.
Take a rule that truly wins seventy percent of the time — which, remember, our coin gets for
free just by moving the stop. The best of twenty versions shows twenty-two wins out of
twenty-five about half the time.

Nobody has to cheat for that to happen. You only have to keep the good one.

**SCREEN** Chart `03` — the four interval bars, widest last. Then chart `04` — the best-of-k
grid, the 49% cell lighting up.

**№** 22/25: 70.0–95.8% · 9/12: 47–91% · 2/2: 34–100% — `part2_analytic.wilson_intervals` · best of 20 at a true 70%: 49.1% — `p_best_of_k_reaches_22_of_25["20"]["0.7"]` · 73.2% at 1 : 3 — beat 5

## 8 · What is true — 7:35 (speech 0:49 + 0:11)

**VO**
Win rate is not useless. Put it next to the average win, the average loss and the number of
trades, and it is half of what you need to know. It is only on its own that it tells you
nothing.

And nothing here says that a particular strategy advertised at ninety percent loses money. We
didn't test those. We showed that ninety percent can't be the proof.

One honest oddity, because it's in our data. In the two cryptocurrencies, the *low* win rate
settings made money with random entries — two coins, one history, not something we set out to
test, and the same settings lost on the stocks and the currencies. It isn't a strategy. It is
the claim upside down.

**SCREEN** Card: "Average win · Average loss · How many trades". Then chart `06` with its stamp
on screen for as long as the chart is.

**№** crypto 5 : 1: 25.3% wins, +1.70% a trade (+0.83 … +2.52); 0.5 : 5: 84.3% wins, −1.74% — `part1_by_asset_class_by_geometry` (on the chart only; **not spoken as figures**)

## 9 · Check the next one yourself — 8:35 (speech 0:37 + 0:13 end card) — ends 9:25

**VO**
Three questions for the next win rate you're shown. What is the average win against the average
loss? How many trades is that? And how many versions were tried before this one?

If those three numbers aren't on the screen, the win rate is decoration.

AMI Trade is a simulator. You direct a team of twelve analysts, on simulated money, and the
record of every decision is kept for you. It is simulation-only, and it promises no edge.
The test, the code and every number from this video are in the description.

**SCREEN** The three questions as a card. AMI end card. Disclaimer card: "Educational content.
AMI Trade is a simulation-only training product. Nothing here is investment advice."

**№** —

---

## Production notes

- **Do not say** (from the brief): "win rate is meaningless" · "random trading loses money" as a law · any figure from the crypto split · "huge" about the Wilson result (it met our threshold narrowly: 25.8 points against 25).
- Quote point estimates on camera; the intervals are on the charts. They are somewhat too narrow (RESULTS §1) and the chart footers say where they come from.
- Beat 9's AMI line describes the product in general terms on purpose. If a more specific line is wanted ("keeps your average win and loss for you"), check it against the shipped app first.
- No creator, channel, title, clip or thumbnail is referenced anywhere. The thumbnail wall in beat 2 is ours and must not resemble a real one.
- EN script — flag for AR / MS translation at v1.0.
