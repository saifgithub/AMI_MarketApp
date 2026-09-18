# C05 — SCRIPT — The "99% win rate" strategy won 43%

**Episode:** week 8, subject to the publish-or-hold decision (B09) · **Verdict:** `PARTLY HOLDS` · **From:** [`VIDEO_BRIEF.md`](VIDEO_BRIEF.md) · **Numbers:** [`RESULTS.md`](RESULTS.md), [`out/results.json`](out/results.json)
**Length:** 1,190 spoken words = 7 min 56 s of speech at 150 words a minute; with the pauses marked below (charts building in silence), ≈ 9 min 4 s · **Charts:** [`charts/`](charts/)

How to read this file: **VO** is spoken word for word. **SCREEN** is what the editor shows while it
is spoken. **№** lists every number in the beat and where it comes from — if a number is not in
that list, it must not be said. Numbers are written as they should be read aloud.

---

## 1 · Cold open — 0:00

**VO**
The ninety-nine percent win rate strategy, tested. Two free indicators, one confirming the other,
and a title that says ninety-nine percent. We coded the rules exactly as given and let them
trade — seven markets, three timeframes, nine thousand three hundred and sixty-three trades. The
best version won forty-three point six percent of the time. And one thing we did not expect: by
the rule we wrote down before testing, we still have to score this one "partly holds." We'll show
you both.

**SCREEN** Trade counter running to 9,363. Win-rate dial settling at 43.6, ghost needle at 99.

**№** 9,363 trades — sum of `n_trades` across `results.json` cells · 43.6% — `V1_loose_60m.win_rate.estimate`

## 2 · The stakes — 0:33

**VO**
Here's why the number matters before we even get to testing it. Someone who believes nine wins in
ten sizes their trades for nine wins in ten — bigger positions, because the plan feels close to
safe. At four wins in ten, that same sizing runs straight into losing streaks it was never built
to survive. The win rate on the label changes how much of your account you're willing to risk on
the next trade. That's the whole reason it's worth checking before you use it, not after.

**SCREEN** Our own mock chart with two generic indicator lines; a position-size field highlighted,
then dimmed.

**№** —

## 3 · What would convince us — 1:09

**VO**
Before we touched any code, we wrote down two separate ways this claim could win, and committed
it in public. One: an eighty percent win rate on the hourly chart — the headline holds outright.
Two: the entries make more money than random entries under the same stop and target, on the hourly
and the daily bars — not ninety-nine percent, but a real signal underneath it. We predicted
neither would happen.

**SCREEN** Screen-record of `PREREGISTRATION.md` at commit `3ac320eb`; highlight the eighty percent
line and the random-entry condition.

**№** 80% threshold, both conditions — `PREREGISTRATION.md`

## 4 · The test, as taught — 1:38

**VO**
The recipe: one indicator flips on a trend change, a second confirms it's turning the right way,
you enter, and you exit at a fixed stop and a fixed target — one and a half times the stop, or
twice it, in the two published versions. A quick word on "R", because we'll use it a lot: one R is
just the distance from your entry to your stop, in price terms. A target set at one and a half R
means you're aiming to win one and a half times what you're risking. We built the rules exactly as
taught, two readings of the confirmation because the instructions are loose about it, on three bar
sizes: five minutes, sixty minutes, and daily. Twelve versions in all, seven markets each. Winning
examples are easy to find. Four trades in ten win — and that's the good version.

**SCREEN** The rules as a plain-language card. Then three winning trades in a row on a mock chart,
camera pulling back to show the full run of trades around them.

**№** 1.5 R and 2 R targets, two variants, two filter readings, three timeframes = 12 cells,
7 markets — `PREREGISTRATION.md` / `meta.target_r`

## 5 · The reveal — 2:37 (speech 1:23 + 0:25 as the bars land)

**VO**
Here is every version's win rate, lowest to highest. Thirty-three point two, twice. Thirty-three
point six. Thirty-six point five. Thirty-seven point three, twice. Thirty-eight point two.
Thirty-eight point seven. Thirty-nine point four. Forty point one. Forty-three. And the best of
the twelve, forty-three point six. Not one version won more often than it lost. Even the most
generous reading of the best one — the top of its range — stops at forty-six point seven. The
claim was eighty to ninety-nine.

Now the money — what we call expectancy, which just means the average result per trade once you
average in the wins and the losses together. After costs, every single one of the twelve versions
comes back negative on average. Before costs, none of them is clearly above zero either — the
range in every version still touches zero. And on the five-minute chart — the bar size this is
actually taught on — costs alone eat about half of one R every trade. Half your target, gone to
fees and spread before the trade even has a chance to work. That's why costs bite hardest on the
fastest chart: you're paying the same cost on a much smaller move, over and over, many times a day.

**SCREEN** Chart `01`, the twelve dots against the 80 and 99 lines. Then chart `03`, expectancy
bars, net and gross, zero line held on screen. Then chart `04`, the cost-in-R bars, five-minute
bar highlighted.

**№** 43.0 / 43.6 / 37.3 / 37.3 / 40.1 / 39.4 / 36.5 / 33.2 / 38.2 / 38.7 / 33.6 / 33.2% — `win_rate.estimate` per cell · none above 46.7 — widest upper interval, `V1_loose_60m.win_rate.upper` · net expectancy negative in 12 of 12 cells — RESULTS §3 · gross (before-costs) interval includes zero in 12 of 12 cells — `expectancy_r.gross.{lower,upper}` per cell · cost of about 0.52 R on 5-minute bars — `avg_cost_r` pooled by timeframe

## 6 · Why — 4:25 (speech 1:08 + 0:15 as the dots settle onto the line)

**VO**
Here's the arithmetic behind that number, and it's arithmetic anyone can check before they place a
trade — no history, no backtest, just the target and the stop. This is what we mean by "breakeven
win rate": the minimum fraction of trades you need to win, before costs, just to come out flat. If
your target is one and a half times your stop, a coin flip breaks even at forty percent wins — one
divided by one plus one and a half. Make the target twice the stop, and breakeven drops to
thirty-three point three. You don't need an indicator to hit either of those numbers. You need a
coin. Every one of our twelve versions landed within about four points of one of those two
breakeven numbers. The win rate wasn't coming from the indicators. It was coming from where the
target and the stop were placed — the same arithmetic that shows up whenever a strategy is built
this way, on any market, with any entry.

**SCREEN** The line `1 / (1 + target)` drawn on chart `02`, markers at 40 and 33.3, the twelve dots
settling onto it.

**№** breakeven 40.0% at 1.5 R, 33.3% at 2 R — arithmetic, `1/(1+target_r)` · largest gap 4.0 points — RESULTS §2

## 7 · What held — and where our own rule went against us — 5:48 (speech 2:06 + 0:15 on the "after the fact" stamp)

**VO**
Now the part we didn't expect. On the hourly chart, these entries beat random entries — entries
with no information in them at all, given the same stop and the same target. Forty-three point six
percent, against a random band of thirty-five point seven to forty point five. That is the second
condition we wrote down before testing, and it held. By our own rule, that makes the verdict
"partly holds," not "not supported." We say that plainly, because the rule is the rule.

Here's what we found after we saw that result — and we're labelling it exactly that: after the
fact, not pre-registered. We measured the edge in R, which is profit divided by each trade's own
stop distance. Costs are a flat percentage of price. A trade with a small stop pays a huge cost
once you divide by that stop. And our random entries usually sat right on a nearby low, so their
stops were smaller than the real recipe's — they paid five to eight times more in cost, in R terms
alone. On the daily bars, once we re-measure without dividing by the stop, the recipe is level with
random on every measure we have. That leg of "partly holds" looks like our own yardstick, not a
signal.

The hourly result is more stubborn. It survives every version of the fix we tried. But we can't
yet separate genuine timing from where the stop happened to sit, all seven markets rose across this
sample, and the money came entirely from the long side — the short trades lost in every one of the
twelve versions. After costs, hourly nets out close to zero either way. This is a real finding, not
a footnote, and we're re-running it with a fairer yardstick — logged as backlog item B09 — and
we'll publish that result whichever way it comes out.

**SCREEN** Verdict card: "PARTLY HOLDS — by our own rule." Stamp "AFTER THE FACT — NOT
PRE-REGISTERED" over: chart `04`'s placebo bars, then chart `05`, long vs short.

**№** hourly win rate 43.6% vs random band 35.7–40.5% — `results.json` `V1_loose_60m` win_rate and placebo p5/p95 · cost paid in R: recipe 0.09 (60m) vs random entries 0.53 (60m) — `avg_cost_r` recipe vs `posthoc_diagnostic.json` `avg_cost_r.placebo_p50`, pooled · daily re-measured without dividing by stop: recipe indistinguishable from random on every measure but one — RESULTS §5 daily table · short side net negative in 12 of 12 cells — RESULTS §5 by-side table · hourly net near zero after costs — RESULTS §5 ("+0.08% to +0.16%")

## 8 · Check the next one yourself — 8:09 (speech 0:24)

**VO**
Two questions for the next "high win rate" recipe you're shown. What is the target-to-stop ratio —
and what win rate does that ratio hand any entry for free, indicator or none? And: how many trades
is this built on, and who picked the version you're looking at?

If those two answers aren't on the screen, the win rate is decoration.

**SCREEN** The two questions as a card.

**№** —

## 9 · AMI + disclaimer — 8:33 (speech 0:19 + 0:12 end card) — ends ≈ 9:04

**VO**
AMI Trade is a simulator. You direct a team of twelve analysts, on simulated money, and the record
of every decision is kept for you. It is simulation-only, and it promises no edge. The test, the
code and every number from this video are in the description.

**SCREEN** AMI end card. Disclaimer card: "Educational content. AMI Trade is a simulation-only
training product. Nothing here is investment advice."

**№** —

---

## Production notes

- **Do not say** (from the brief): "debunked" / "disproved" / "busted" / "myth" / "fraud" / "scam" /
  "fake" / "liar" / "exposed" / "destroyed" anywhere in this episode · "the indicators are useless" ·
  "it loses money" without the after-costs qualifier · the 55% hand-count figure from the
  pre-registration (points at one specific video) · the stop-geometry explanation presented as
  established rather than a flawed yardstick we found afterwards.
- All brief figures checked against `out/`: nothing in the brief's beat sheet was dropped for lack
  of support. The brief's beat-5 "top of the widest interval is 46.7" is spoken directly and cited
  in the № list (`V1_loose_60m.win_rate.upper`). The brief's beat-3 "55% hand count" is the one
  brief figure deliberately **not** spoken — it is on the must-not-say list, not missing from
  `out/`.
- Every "after the fact" number in beat 7 is spoken and shown only under that label, exactly once
  each, as the brief requires; it does not change the verdict and the script never implies it does.
- "Swing low" is our 10-bar rule, not a discretionary trader's swing point — said once, in
  Production notes only, since the brief's beat sheet does not allocate it a spoken sentence; if a
  future cut wants it on camera, add one clause to beat 4 or 7.
- No creator, channel, title, clip, thumbnail or platform interface is referenced anywhere. Indicator
  families are described generically ("one indicator flips on a trend change, a second confirms it")
  rather than named, since the spoken script never needs the UT Bot / STC names to make the point;
  RESULTS.md and the brief may name them in text.
- Quote point estimates on camera; intervals live on the charts, except the hourly-vs-random band in
  beat 7, which is the point being made and is spoken.
- EN script — flag for AR / MS translation at v1.0.
