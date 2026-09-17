# C08 — VIDEO BRIEF — Ten stocks from a chatbot vs ten stocks from a hat

**Verdict:** `NOT SUPPORTED` · **Pre-registration commit:** `3ac320eb` · **Results:** [`RESULTS.md`](RESULTS.md)
**Runtime target:** 9–11 min · **Format:** faceless, chart-driven, voice-over
**Claim class reach (measured 2026-09-17):** 2 videos · 2.76M views

## Search intent

- **Primary keyword:** chatbot stock picks tested
- **Secondary:** AI stock picks beat the market · can a chatbot pick stocks · AI portfolio vs S&P 500
- The primary keyword appears in the title, the first spoken sentence, and the first line of the description.
- "AI stock picks" is the search term for the genre and is used only as that. Our own product is AMI, by name.

## Title options (≤ 60 characters, all literally true)

1. *Chatbot stock picks tested against 2.36 million random ones*
2. *We asked chatbots for 10 stocks, 30 times. 19 said no.*
3. *Chatbot stock picks "as of 2019": 94th percentile. Why?*

## Thumbnail concept

A bell-shaped spread of grey dots (random portfolios) with one highlighted dot at "+13". Text:
"Skill? 1 in 6 by luck."

## Hook (0:00–0:20) — spoken, verbatim

> "Ask a chatbot for ten stocks to beat the S&P 500, hold them a year, and see who wins. Videos
> running that experiment have two point seven million views. We tested chatbot stock picks a
> different way: first we let two point three six million random portfolios play the same game, to
> see what luck alone does. Then we asked the chatbots — thirty times. Nineteen times, the answer
> was no."

## Beat sheet

| # | Beat | Time | Voice-over (gist) | On screen | Source of every number |
|:--|:--|:--|:--|:--|:--|
| 1 | Cold open | 0:00–0:20 | Hook above. | Dots raining into a distribution; counter to 2,360,000. | `part1.meta`: 236 windows × 10,000 draws; `refusal_rates`; reach from `TRACKER.md` |
| 2 | The stakes | 0:20–0:50 | If the chatbot's portfolio "won", the viewer buys ten stocks on the strength of one run and one year. | Ten tickers on a card, a "+13% vs index" badge. | — |
| 3 | What would convince us | 0:50–2:00 | Written down before any chatbot was asked: if luck's spread were under 10 points, a 13-point win would mean something. If the picks changed run to run and showed no tilt to recent winners, they'd look like an independent view. If back-dated picks landed mid-pack, back-testing them would be fair. | `PREREGISTRATION.md`, commit `3ac320eb`. | `PREREGISTRATION.md` |
| 4 | The test, as taught | 2:00–3:30 | The format: one prompt, one run, ten stocks, one year, compare to the index. In the videos, portfolios finished 3, 13 and 22 points ahead, and one 8 behind. | The four gaps as bars. | Gaps quoted in `PREREGISTRATION.md` |
| 5 | The fair test + reveal | 3:30–7:00 | Part 1 — ten stocks from a hat, 100 large companies, every 12-month window since 2006. The middle 90% of luck spans 28 points in a typical year. Ahead by 13 or more: about one random portfolio in six. Ahead by 22: one in sixteen. Part 2 — the exact prompt, 30 fresh conversations, three chatbots: 19 refusals. The one that answered named nearly the same stocks each time — three names in 11 of 11 replies — sitting at the 74th percentile of three-year past return. Part 3 — "it is January 2019, pick ten": 94th percentile against random. And all 30 replies said: I already know what happened. | `random_portfolio_spread.png` with the four video gaps marked on it; refusal grid 3 × 10; pick-frequency bars; `hindsight_percentiles.png`. | `gap_table.json`: `within_window_spread_5_95.median` 28.07, `vs_spy.ahead_by_at_least` +13 → 0.170, +22 → 0.062; `part2_stability_and_frequency`: 11 replies, `most_picked_names`; `part2_momentum_tilt.36m.mean_percentile` 73.87 (71.59–76.47); `part3_hindsight.pooled` 94.30 (91.21–97.10); `n_replies_with_future_knowledge_caveat` 30 |
| 6 | Why | 7:00–8:30 | Two mechanisms. One: ten stocks for one year is a small sample of a noisy thing — one draw can't separate skill from the 28-point spread. Two: a chatbot's knowledge of stocks *is* the past. Ask it about the past and it remembers the winners; ask it about the future and it names the recent winners. Neither is a forecast. | Split screen: "one draw" on the distribution · timeline with the model's knowledge cut-off. | as above |
| 7 | What is true | 8:30–9:40 | The chatbots said most of this themselves: every reply that named stocks also said most professionals fail to beat the index. Leaning toward large recent winners has been a reasonable portfolio at times — it is the momentum factor, and you don't need a chatbot for it. And a trap for everyone: random tens from *today's* famous companies "beat the index" 68% of the time in a back-test, because today's list already knows who survived. We also missed one of our own thresholds: we predicted a spread above 30 points; the typical year gave 28. | "68% — survivorship, not skill" card; "our prediction: >30 · measured: 28" card. | `pooled.beat_spy_share` 0.683; `beat_universe_share` 0.452; `gap_table.json` spread |
| 8 | Check the next one yourself | 9:40–10:20 | The question: how many times was it run, and how wide is luck over that horizon? One run, one year is an anecdote. | The question as a card. | — |
| 9 | AMI + disclaimer | last 15 s | AMI Trade is a simulator: you run a twelve-analyst team on simulated money and practise the process — many decisions, not one draw. Simulation-only, no edge promised. | AMI end card, disclaimer. | — |

## The one idea

One portfolio over one year is one ticket in a lottery 28 points wide — and back-testing a chatbot's
picks measures its memory, not its judgement.

## What we must not say

- That chatbot picks underperform, or will. **No forward performance was measured.** Do not imply it.
- Anything about chatbots we did not test. We tested three Claude models in September 2026 and say so on screen; refusal rates elsewhere will differ, and the videos' chatbots did answer.
- Do not present 68% as a success rate for stock picking — it is the survivorship artefact, and the beat explaining it is mandatory if the number appears.
- The stability figure (0.535) is ten replies from one model plus one from another. Say "the one that answered", not "chatbots agree".
- No stock named on screen as a recommendation. Tickers appear only as "what it said", with the frequency count.

## Description (first 160 characters are the search snippet)

Chatbot stock picks tested: 2.36 million random ten-stock portfolios show what luck does in a year,
then we ask three chatbots the same question 30 times.

Pre-registered before any chatbot was asked. Part 1: random portfolios from 100 large US companies,
236 twelve-month windows since 2006. Part 2: the exact prompt, 30 fresh conversations, picks
compared for overlap and tilt. Part 3: the same question back-dated to January 2019, scored against
10,000 random portfolios. Models tested: Claude Haiku 4.5, Sonnet 5, Opus 5.

Links: claim folder (pre-registration · code · all 60 replies) · episode page · AMI Trade (UTM).
Disclaimer: educational content; AMI Trade is a simulation-only training product; nothing here is
investment advice and no stock shown is a recommendation. By policy we test claims and name no channel.

## Pinned comment

Pre-registered on 2026-09-17 in commit `3ac320eb`, before any chatbot was asked. All 60 raw replies
are in the repo, plus a first pass we threw away and why. One of our own thresholds missed (we said
> 30 points of spread; a typical year gave 28). Reproduce: see RESULTS.md §7.

## Shorts cut-down (≤ 40 s)

"Asked to pick ten stocks 'as of January 2019', the chatbots landed in the 94th percentile." →
`hindsight_percentiles.png` → "All thirty replies also said: I already know what happened. A
back-test of a chatbot is a memory test." Full test on the channel.

## Chart pack (from `out/`)

| Figure | Use | Restyle notes (AMI hex, 16:9, dark) |
|:--|:--|:--|
| `random_portfolio_spread.png` | Beats 1, 5 | Mark +3 / +13 / +22 / −8 as vertical lines with their luck frequencies from `gap_table.json`. |
| `hindsight_percentiles.png` | Beat 5, Short | 20 dots on a 0–100 scale against the random distribution; label the mean 94.3 and interval. |
| Refusal grid (to draw) | Beat 5 | 3 rows × 10 cells, filled = named stocks. From `refusal_rates`. |
| Pick-frequency bars (to draw) | Beat 5 | Top 7 names with counts out of 11; caption "what it said — not a recommendation". |

## Compliance checklist

- [ ] No creator / channel / title / clip / thumbnail referenced, on screen or spoken
- [ ] Models tested named on screen; no claim about untested chatbots
- [ ] "We tested this claim" language; no *fraud*, *scam*, *liar*
- [ ] Every number traced to `results.json` / `gap_table.json`, with its window and interval
- [ ] Limits stated on camera: no forward test, thin Part 2 sample, our missed threshold
- [ ] No ticker presented as a recommendation; disclaimer covers it
- [ ] No strategy offered in return; ends on method
- [ ] AMI by name; simulation-only; not investment advice
- [ ] EN script flagged for AR / MS translation at v1.0
