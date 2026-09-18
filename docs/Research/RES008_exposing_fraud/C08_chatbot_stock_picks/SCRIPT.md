# C08 — SCRIPT — Ten stocks from a chatbot vs ten stocks from a hat

**Episode:** week 6 · **Verdict:** `NOT SUPPORTED` · **From:** [`VIDEO_BRIEF.md`](VIDEO_BRIEF.md) · **Numbers:** [`RESULTS.md`](RESULTS.md), [`out/results.json`](out/results.json)
**Length:** 1,237 spoken words = 8 min 15 s of speech at 150 words a minute; with the pauses marked
below (charts building in silence), ≈ 9 min 4 s · **Charts:** [`charts/`](charts/)

How to read this file: **VO** is spoken word for word. **SCREEN** is what the editor shows while it
is spoken. **№** lists every number in the beat and where it comes from — if a number is not in
that list, it must not be said. Numbers are written as they should be read aloud.

---

## 1 · Cold open — 0:00 (speech 0:28 + 0:05 for the grid to settle)

**VO**
Ask a chatbot for ten stocks to beat the S&P 500, hold them a year, and see who wins. Videos
running that experiment have two point seven million views. We tested chatbot stock picks a
different way: first we let two point three six million random portfolios play the same game, to
see what luck alone does. Then we asked the chatbots — thirty times. Nineteen times, the answer
was no.

**SCREEN** Grey dots raining into a bell-shaped spread. Counter climbing to 2,360,000. Cut to a
3-row-by-10-cell grid, most cells dimming to "declined."

**№** 2.36 million random portfolios: 236 windows × 10,000 draws — `part1_random_portfolios.json["meta"]` (`n_windows` × `n_draws_per_window`) · 19 of 30 declined — `results.json["refusal_rates"]` / RESULTS §3–4

## 2 · The stakes — 0:33 (speech 0:54)

**VO**
Picture the version of this video that ends with a win. The chatbot's ten stocks finish ahead of
the index. The thumbnail says so. And if you believe that one result, the reasonable next move is
to go buy those ten stocks — on the strength of one run, one year, one chatbot.

Here's the problem with that move. One run is one data point. It's like watching someone flip a
coin once, land on heads, and calling them lucky at coin flipping. To actually know whether the
chatbot has an edge, you'd need to watch it make that same kind of call many times, in many
different years, and see whether it wins more often than chance alone would. A single win — or a
single loss — tells you almost nothing on its own.

**SCREEN** A card: ten greyed-out ticker slots, "?" where the names would be, a badge reading
"+13% vs index."

**№** —

## 3 · What would convince us — 1:27 (speech 0:33)

**VO**
We wrote this down before asking a single chatbot anything. If luck's own spread, over one year,
were under ten points, then a thirteen-point win would mean something. If the picks changed from
run to run and showed no lean toward stocks that already went up, they'd look like an independent
view. And if picks made "as of" a past date landed in the middle of the pack, back-testing a
chatbot would be a fair test. None of that happened. Here's what did.

**SCREEN** Screen-record of `PREREGISTRATION.md` at commit `3ac320eb`; highlight "What would
support the claim instead."

**№** commit `3ac320eb` — `PREREGISTRATION.md` header

## 4 · The test, as taught — 2:00 (speech 0:26)

**VO**
Here's the format these videos use. One prompt. One run. Ten stocks. Hold a year. Compare to the
index. In the videos we looked at, three chatbots finished ahead — by three points, thirteen, and
twenty-two — and one finished about eight points behind. Four results, from four one-time runs.
Not enough runs to tell luck from skill — but enough to make a thumbnail.

**SCREEN** Four bars: +3, +13, +22, −8, plain and unstyled, no logos.

**№** +3 / +13 / +22 / −8 — `PREREGISTRATION.md` ("the claim, as taught") · "four results" — count of
the four gaps above

## 5 · The fair test — 2:26 (speech 1:34 + 0:15 for the chart to build and the lines to land)

**VO**
So we built the control group those videos skip: pure luck. A hundred large US companies, frozen
before we ran anything. Every twelve-month window since 2006 — two hundred and thirty-six of them.
In each one, ten thousand portfolios of ten stocks, picked at random. No chatbot involved at all.

In a typical year, the middle ninety percent of these random portfolios spans about twenty-eight
points, top to bottom. That's the width of luck alone, on this exact game — pick any ten names out
of a hat, hold them a year, and that's the spread of outcomes you'd see, before anyone claims any
skill at all.

Finishing thirteen points ahead of the index — the middle result from those videos — happens to a
random, ten-stock, no-opinion portfolio about one time in six. Finishing twenty-two ahead: about
one time in sixteen. A hat with no view on the market gets there that often, doing nothing.

One caution on those two numbers, and it cuts against us: they are measured against the index, and
our hundred-company list is a list of today's winners, so beating the index from it is easier than
it should be. Measured against the list's own average instead — the fairer yardstick — thirteen
points ahead happens about one time in twelve, and twenty-two about one in thirty. Either way, one
run cannot tell you which you are looking at.

**SCREEN** Chart: spread of random ten-stock portfolios, 5th–95th band, with +3 / +13 / +22 / −8
marked as vertical lines and their frequencies labelled.

**№** 100 companies, 236 windows, 10,000 draws each — `part1_random_portfolios.json["meta"]` ·
28 points, median within-window 5th–95th spread — `gap_table.json["within_window_spread_5_95"]["median"]`
· +13 → one in six (17.0%) vs the index — `gap_table.json["vs_spy"]["ahead_by_at_least"]["+13"]` ·
+22 → one in sixteen (6.2%) vs the index — `gap_table.json["vs_spy"]["ahead_by_at_least"]["+22"]` ·
+13 → one in twelve (8.3%) vs the list's own average — `gap_table.json["vs_universe"]["ahead_by_at_least"]["+13"]`
· +22 → one in thirty (3.2%) vs the list's own average — `gap_table.json["vs_universe"]["ahead_by_at_least"]["+22"]`
· survivorship caution — RESULTS §2 ("Why 68% beat SPY — read this before quoting it")

## 6 · What the chatbots actually pick — 4:15 (speech 0:48 + 0:10 for the grid and bars)

**VO**
Then we asked the chatbots ourselves. The exact prompt from the videos, sent fresh thirty times,
across three models. Nineteen of those thirty times, the chatbot declined to name a single stock
— it just explained why picking stocks is hard. Everything past this point rests on the eleven
replies that did answer, and ten of those eleven came from one model.

When it did answer, it named nearly the same handful of companies almost every time. Three names
showed up in eleven replies out of eleven. And those picks, checked against three years of past
returns, sit around the seventy-fourth percentile of the whole hundred-company list. Fifty would
mean no lean at all. Seventy-four means: recent large winners, repeated.

**SCREEN** Refusal grid, 3 rows × 10 cells, row labels "Claude Haiku 4.5 / Sonnet 5 / Opus 5,"
filled cells lighting up as "answered." Then a pick-frequency bar chart, tickers labelled only as
"what it said — not a recommendation."

**№** 30 replies, 19 declined — `results.json["refusal_rates"]` totals · 11 of 30 answered, 10 of
11 from one model — RESULTS §3 / `part2_3_analysis.json["part2_stability_and_frequency"]["n_replies_with_picks"]`
· 3 names in 11 of 11 replies — `part2_3_analysis.json["part2_stability_and_frequency"]["most_picked_names"]`
· 73.9th percentile on trailing 36-month return — `part2_3_analysis.json["part2_momentum_tilt"]["36m"]["mean_percentile"]`

## 7 · The hindsight test — 5:13 (speech 1:10 + 0:10 for the dots to settle)

**VO**
Last part. We asked the same three chatbots to pick ten stocks as of January 2nd, 2019 — and told
them to answer as if they didn't know what came next.

Here's why that matters. A chatbot learns from text written up to a certain point in time — its
knowledge cutoff. Ask it about a year that already happened before that cutoff, and it isn't
guessing. It's remembering. That's the trap in "backtesting" a chatbot's picks: if the test period
falls before the model learned the news, you're not testing foresight, you're testing whether it
did its reading.

Every single one of the thirty replies said, in its own words, that it already knows what
happened after that date, and can't un-know it. Then it answered anyway.

Scored against ten thousand random portfolios from that same starting day, those back-dated picks
landed, on average, around the ninety-fourth percentile. Fifteen of the twenty usable replies
scored above the ninety-sixth percentile. That is not a forecast. That's a chatbot picking the
companies it already knows won.

**SCREEN** Chart: dots for each reply against the random-portfolio distribution, mean at 94.3
labelled with its range. A small on-screen caption: "the model already knows what happened here."

**№** 30 of 30 replies flagged future knowledge — `part2_3_analysis.json["part3_hindsight"]` /
`summary.txt` refusal section · mean 94.3rd percentile (91.2–97.1) — `part2_3_analysis.json["part3_hindsight"]["pooled"]`
· 15 of 20 above the 96th percentile — `part2_3_analysis.json["part3_hindsight"]["per_reply"]`

## 8 · Why, and what we got wrong — 6:33 (speech 1:29)

**VO**
Two mechanisms, not one. First: ten stocks for one year is a small sample of something noisy —
one draw can't tell skill from a twenty-eight-point spread of pure luck. Second: a chatbot's
knowledge of the market is the past. Ask about a year that already happened, and it remembers who
won. That's not a view on what's next. It's a memory test wearing a forecast's clothes.

One more honest number, because it's ours to own. Random tens picked from today's already-famous
hundred companies "beat the index" sixty-eight percent of the time — not because picking from that
list takes skill, but because every name on it already survived to become famous. Any back-test of
a list of companies you have heard of today carries that flattery, ours included.

And we missed one of our own marks. We wrote down in advance that a year's spread of luck would run
above thirty points. Pooled across all the years it did — thirty-two. But within a typical single
year, the measure that actually matches "one portfolio, one year", it was twenty-eight. Our
pre-registration never said which of the two we meant, so we score it as not cleanly met. That is
the whole reason this episode stops at "not supported" instead of the stronger word: not one of the
chatbot's marks, one of ours.

**SCREEN** Split screen: "one draw" pointer on the luck distribution / a calendar with the
model's training cut-off marked. Then two cards: "68% — a survivor list, not a skill test" and
"our call: over 30 · measured: 32 pooled, 28 within a year — not cleanly met."

**№** 68.3% of random portfolios beat SPY — `results.json["part1_random_portfolios"]["pooled"]["beat_spy_share"]`
· predicted above 30, measured 32.1 pooled and 28.1 within a typical window, scored not cleanly met —
RESULTS §5, H1 second clause · none of the claim-supporting conditions met — RESULTS §5

## 9 · Check the next one yourself — 8:02 (speech 0:52 + 0:10 end card) — ends ≈ 9:04

**VO**
Every chatbot reply that named stocks also said, on its own, that most professional managers fail
to beat the index. So three questions for the next "the chatbot's portfolio beat the market"
video. How wide is luck over that stretch of time — the twenty-eight points we just showed you, or
something else? Was the period being tested before or after the model already learned how it
turned out? And how many portfolios, or how many tries, sit behind the one result on screen?

AMI Trade is a simulator. You direct a team of twelve analysts, on simulated money, and the record
of every decision is kept for you. It's simulation-only, and it promises no edge. The test, the
code and every number from this video are in the description.

**SCREEN** The three questions as a card. AMI end card. Disclaimer card: "Educational content.
AMI Trade is a simulation-only training product. Nothing here is investment advice. No stock
shown is a recommendation."

**№** all 11 answering replies also flagged manager underperformance — RESULTS §3 ("All 11 replies
that named stocks also said...")

---

## Production notes

- **Runtime:** ≈ 9 min 4 s (1,237 spoken words), inside the brief's 9–11 min target and the
  1,100–1,400-word range. Timecodes are the cumulative measured speech plus the pauses marked in
  the beat headings; re-measure after any edit to the VO.
- **Do not say:** "debunked," "disproved," "busted," "myth," "fraud," "scam," "fake," "liar,"
  "exposed," "destroyed." Verdict is `NOT SUPPORTED` because one clause of our own H1 (5th–95th
  spread above 30 points) is scored **not cleanly met** — 32.1 pooled but 28.1 within a typical
  window, and the pre-registration did not say which reading it meant (RESULTS §5). Beat 8 says
  that on camera and names it as the reason for the softer verdict. None of the three
  claim-supporting conditions was met.
- **No ticker spoken as a pick.** Tickers referenced in the brief (AVGO, LLY, TSM, AMZN, GEV, JPM,
  GOOGL, and the Part 3 "typical list": MSFT, AMZN, AAPL, GOOGL, V, MA, NVDA, ADBE, NFLX, CRM) are
  SCREEN-only, in the pick-frequency chart, captioned "what it said — not a recommendation." None
  is spoken.
- **Models named on screen, not spoken by product name beyond beat 6's "one model" framing** — the
  brief requires models named on screen (Haiku 4.5, Sonnet 5, Opus 5); put the three names as a
  screen caption in beat 6 rather than spoken, to keep the VO in plain language ("the chatbots we
  tested" / "one model"). This satisfies the compliance checklist item without narrating brand
  names aloud.
- **Numbers not spoken though present in the brief/RESULTS, and why:**
  - The 0.535 overall Jaccard stability figure and the within/across-model breakdown (0.603 /
    0.229) — RESULTS explicitly flags this as "one model's consistency with itself plus one reply
    from another," too thin to state as a headline stability number without the caveat eating the
    beat's runway. Beat 6 instead states the plainer, equally-supported fact (3 names in 11 of 11
    replies) and leaves Jaccard off-camera; the brief's own "must not say" list requires framing
    it as "the one that answered," which the surrounding VO already does implicitly (10 of 11 from
    one model, stated).
  - 45.2% (beat-universe-mean share) and the IQR (11.17pp) — supporting detail already implied by
    "middle ninety percent spans 28 points"; omitted to protect word count, not because unsupported.
    The `vs_universe` frequencies ARE now spoken in beat 5, because RESULTS §2 names the universe
    mean as the fair benchmark and warns against quoting the vs-SPY figures on their own.
  - "3 of 4 beat the index ≈ 31% by coin flip / 62% at the measured rate" — this is a good number
    but duplicates the +13/+22 frequency point already made in beat 5 with the same "one draw is
    inside the noise" lesson; cut for time, not because it's unsupported. Available in RESULTS §2
    if a re-cut wants it.
  - 12-month tilt (59.4th percentile) — omitted; the 36-month figure alone carries beat 6's point
    and two tilt numbers would blur on camera.
- **Not supported from out/ — omitted:** none. Every number in the brief's beat sheet was found
  in `results.json`, `part2_3_analysis.json`, or `gap_table.json` and is spoken or explicitly
  deferred above.
- Quote point estimates on camera; intervals live on the charts (beats 5, 6, 7 charts carry the
  95% ranges).
- Beat 9's AMI line reuses the exemplar's general wording verbatim; check against the shipped app
  before a future re-cut if a more specific line is wanted.
- No creator, channel, title, clip or thumbnail is referenced anywhere.
- EN script — flag for AR / MS translation at v1.0.
