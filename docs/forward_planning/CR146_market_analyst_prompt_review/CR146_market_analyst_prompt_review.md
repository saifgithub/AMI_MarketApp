# CR146 — Market Analyst — stop asking for the trade, ask for the levels

**Filed:** 2026-08-08 · **Status:** proposed · **Decision:** Saiful, 2026-08-08 — *"book CRs one for
each agent."* One CR per agent so each remedy is decided on its own evidence rather than bundled.

**Source:** CR143 Phase 1/3b plus two independent reviews of this agent — a blind prompt-coherence
audit ([`external_review/room/market_analyst.md`](../CR143_agent_prompt_audit/external_review/room/market_analyst.md))
and a codebase-verified data-sufficiency audit ([`external_review/room/kimi/market_analyst_data_sufficiency.md`](../CR143_agent_prompt_audit/external_review/room/kimi/market_analyst_data_sufficiency.md)).
Both are hypotheses. Everything below survived a **supplier check** (does the code inject the data the
prompt claims?) and a **parser check** (does anything read the output the instruction shapes?), and
every rate is re-derived here against the committed corpus rather than inherited.

---

## Why

**The output-style block asks this agent for a trade. The data supports a chart read, the role text
says the trade belongs to the Trader, and the model has quietly been dropping the demand for both
reasons.** Measured over the epoch corpus, n=18 Market Analyst turns:

| Output-style bullet | measured compliance |
|---|---|
| *"State the timeframe you're analyzing"* | 10/18 (56%) |
| *"Identify the setup (breakout, breakdown, mean reversion, trend continuation)"* | 16/18 (89%) |
| *"Acknowledge when a setup is not present"* | 14/18 (78%) |
| **"Provide specific levels: entry, target, stop-loss"** | **0/18** — no turn states a parseable triple |
| **"Risk-reward ratio (e.g. '3:1 R:R')"** | **0/18** — no turn states a numeric ratio |

Two of five bullets are dead instructions. Dropping them is the *correct* resolution — the grounding
directive forbids inference and no volatility measure exists anywhere in the codebase
(`app/trading_math/indicators.py` is 53 lines: `rsi`, `rsi_tone`, `sma`; no ATR, no stdev), so a stop
distance and therefore an R:R cannot be derived from the seven scalars the fact sheet supplies. But
the demand stays in every prompt, and **the turn where the model does comply is the expensive one**:
`_verify_and_annotate_geometry` runs on *every* prose agent, not just the Trader
(`room_runner.py:3526`), and on a full entry/stop/target triple it appends

> *"…drawdown contribution ≈ N pt at the mandate's X% single-name cap — These are the figures of
> record."*

— a **sizing figure in AMI's own voice, on the turn of the agent whose prompt says "Recommend final
position sizing. That's the Trader."** Six of eighteen epoch mandates carry a 100.0% single-name cap
(CR153), so that figure would not be small.

The exposure is latent, not theoretical. 13/18 turns use the word *entry*; **3/18 use all three level
words in one turn**; and **1/18 already produces a wrong partial parse** — NVDA 2026-08-07 19:53,
*"a **stop-loss** below the 50-day low of **$189.8**"* → `_LEVEL_PATTERNS["stop"]` captures **50**,
scanning the 11 digit-free characters of *" below the "* and landing on the `50` of "50-day". Nothing
rendered only because `entry` and `target` each fell outside the 15-char gap. This is DEF237's class
(the missing plausibility backstop) arriving on the one agent that is instructed to produce its
inputs. **This CR removes the instruction; DEF237 still owns the backstop.**

### Second finding — this agent is not the clean one

CR145's row states *"Only market_analyst is clean"*, and this CR's own stub was seeded with
*"cleanest of the four analysts — sentiment 2/18, news 1/18"*. Re-derived per-turn over the same
corpus and hand-verified, all five instances quoted:

| lane cited | turns | instance |
|---|---|---|
| retail sentiment (a Reddit datum) | **3/18** | KTOS 19:27 *"the high RSI and falling retail sentiment suggest a pullback"*; NVDA 19:53 *"sentiment remains bullish with **28%** bullish retail mentions"*; KTOS 20:13 *"Retail sentiment is bearish (**-0.10**) with falling mentions"* |
| **earnings** (date / quarter / countdown) | **3/18** | AVGO 19:28 *"Earnings catalyst on **2026-09-02** (26 days) adds event risk to any current positioning"*; LITE 19:28 *"with **Q3 earnings** in **4 days**, technical risk is elevated"*; NVDA 19:53 *"ahead of earnings on **2026-08-26**"* |
| valuation | 1/18 | KTOS 20:13 *"to justify current valuations"* — a lane word with no lane datum behind it |
| news headline / FOMC | 0/18 | — |
| **any of the above** | **5/18 (28%)** | |

The seeded figure undercounts twice. Sentiment is 3/18 under any literal reading — all three turns
contain the string *"retail sentiment"* or *"retail mentions"*. And neither figure counted
**earnings**, which is the *first* item on this agent's own "You DO NOT" list: *"Read fundamentals or
earnings. That's the Fundamentals Analyst."*

**CR145's Tier C argument survives; its wording does not.** The same method over the same 18 convenes
puts this agent far below the others — news_analyst cites valuation 17/18, technicals 15/18,
sentiment 9/18; fundamentals_analyst cites technicals 14/18; social_media_analyst cites technicals
11/18. Market is the lowest of the four by a wide margin. It is the *least* leaky analyst, not a
clean one, and CR145's row should be amended to say so when it is next touched.

---

## Scope — three tiers, ordered by cost

### Tier A — delete four demands the system cannot honour (prompt-only, free, ships alone)

**`content/agents/market_analyst.md` — Output style.** Drop *"Provide specific levels: entry, target,
stop-loss"* and *"Risk-reward ratio (e.g., '3:1 R:R')"*. Replace with: name the levels the data
actually holds (the 50-day range low/high and where the last close sits inside it) and the condition
that would confirm or invalidate the setup. Turning levels into an entry/stop/target is the Trader's
job and `trader.md` already asks for it in the layout the parser was written against.

- *Supplier check:* seven scalars render (`room_prompts.py:694-711` + `_range_line` at `:795-813`).
  No ATR, no stdev, no volatility of any kind exists to size a stop with.
- *Parser check:* `_verify_and_annotate_geometry` (`room_runner.py:1886`, called at `:3526` for every
  prose agent) needs a full triple. It fired **2×** across the whole 216-turn epoch — both on the
  Neutral Debator, never on this agent. Removing the demand costs nothing downstream.
- *Measured cost of keeping it:* 0/18 compliance, 3/18 latent, 1/18 already mis-parsing.

**Same file — Inputs.** *"Daily price history (yfinance OHLCV), when live market data is enabled"*
overstates what arrives. The OHLCV is fetched, consumed inside `compute_technicals`
(`technicals.py:103-106`) and dropped; the agent receives derived scalars. State that.

**Same file — Voice.** *"breakout from a 3-month base"* — the base is 50 candles
(`technicals.py:148-149`), ≈2.4 months, inside a 3-month fetch. *"RSI clearing 70 off an oversold
base"* needs an RSI series; one scalar is supplied. Both examples model claims the agent cannot make.

**`app/agents/overlay_generator.py::_market_analyst_block` — delete the leverage line.**
*"Never recommend leverage above what {max_drawdown_pct}% drawdown can absorb"* appears in **18/18**
epoch prompts, and **the simulator has no leverage or margin concept at all** — no match for
leverage/margin/borrow in `sim_engine.py` or the models; the only other hits in the tree are a
concierge keyword filter and a BOK lesson id. An instruction about a capability the product does not
have is prompt weight with a hallucination surface attached (CLAUDE.md: prompt instructions are not
controls — this one has nothing to control).

**Same function — the `Path.ACTIVE` branch and the R:R floors.** The active-path branch emits
*"Emphasise short-timeframe signals (1H–weekly). Specify entry/exit/stop levels"* while the base
prompt six lines up says *"No intraday (1H) timeframe — only the daily bars actually fetched"* and
`_HISTORY_PERIOD = "3m"` → `_PERIOD_MAP["3m"] = ("3mo", "1d", 65, …)` fetches daily bars only.
**Unexercised on this epoch — 0/18 prompts carry it** (all 18 users were `long_horizon`), so this is
a code-read finding, not a measured failure. Fix it anyway: it is a one-line contradiction waiting
for the first active-path user. The risk-tier R:R floors (`R:R ≥ 3:1` at risk ≤2, `R:R ≥ 2:1` at
risk ≥4 — 0/18 and 1/18 in this epoch) go with the R:R demand.

### Tier B — render the numbers already computed and thrown away (small diff, coupled to CR145)

| value | computed | fate today |
|---|---|---|
| SMA-20 (`sma_short`) | `technicals.py:114` | consumed by the alignment test at `:126-127`, dropped |
| SMA-50 (`sma_long`) | `technicals.py:115` | same |
| volume ratio (`recent_vol` / `baseline_vol`) | `technicals.py:135-136` | collapsed to a three-state tone at `:138-144` |

The prompt tells the agent it is given *"a 20/50-day moving-average trend read"*. It is given the
**label**, not the values — it cannot verify or reason from the read it is told it has. Same for
volume: *"in-line with 20-day average"* is a tone string where a ratio (`0.9×`) was computed and
discarded.

Also here, cheaply: **the fact sheet carries two different prices for the same thing.** `Reference
price` (the quote) and `last close` (the final candle of the 3m history) diverge in **7 of the 16**
post-fix prompts — small (max 0.27%, NBIS $189.22 vs $189.31) but real, and one turn treated them as
two facts: *"Price at **$189.31** … and the final close **$189.22** firmly inside this wide band"*.
Two prices on a sheet read by the agent whose entire job is price.

**Why this is Tier B and not Tier A:** `_format_profile(profile)` takes no `agent_id`, so three new
technical numbers land on **all twelve** agents' sheets. The fundamentals analyst already cites
technicals 14/18 and the social analyst 11/18 — adding technical detail to the shared block widens
exactly the leak CR145 Tier C exists to close. **Sequence this after CR145 Tier C, or accept the
widening knowingly.**

### Tier C — a longer window, so "monthly/quarterly trend" is producible (one extra fetch + a cache decision)

`_market_analyst_block` says *"Emphasise monthly/quarterly trend. Skip noise-level intraday signals"*
in **18/18** epoch prompts. The computation behind the sheet fetches `_HISTORY_PERIOD = "3m"` ≈ 65
daily candles. **One quarter of data cannot produce a quarterly trend.**

Available with no new provider: `_PERIOD_MAP["2y"] = ("2y", "1d", 504, …)` (`market_data.py:156`,
added by CR136) — enough for SMA-100/200 or a genuine 13-week read.

Three costs to decide before building:

1. **A second yfinance `.history()` call per ticker per convene.** `CachingProvider`'s history cache
   is keyed `f"{ticker}:{period}"` with a 60s TTL (`market_data.py:400-404`), so a new period is a
   new cache key. Back-to-back runs amortise; spaced runs multiply Yahoo exposure — the same
   rate-limit class CR145 Tier D is gated on.
2. **The all-or-nothing contract must hold.** `compute_technicals` never raises and returns `None` on
   a short / non-finite / synthetic series (`:97-108`, `:160-162`); the runner then degrades the
   whole block to `UNAVAILABLE` (`room_runner.py:523-524`) and the renderer prints *"not available
   this call"*. A missing 2y series must not silently shorten the long-trend read — it needs its own
   `field_state` key or it rides the existing one.
3. **It must go through `history_with_source`, not raw `history()`.** DEF229's synthetic-feed refusal
   (`technicals.py:97-99`) is what stops a yfinance outage fabricating indicators off the mock walk.
   A new window inherits that only if it takes the same path.

**Cheaper alternative, decide explicitly:** soften the overlay line to the window that exists —
*"Emphasise the daily trend across the 50-day range; skip intraday noise."* Free, honest, and it
closes the same gap from the other end. Tier C is only worth its cost if a genuine multi-quarter
trend read is wanted as a product feature, not merely to make one sentence true.

---

## Acceptance

- **Tier A:** no Market Analyst prompt — base, overlay, or assembled — instructs a level triple, an
  R:R, leverage, or a 1H timeframe. The Inputs list matches `_format_profile`'s technicals block
  field-for-field. `_verify_and_annotate_geometry` still fires **0 times** on this agent,
  re-measured on ≥30 convenes.
- **Tier B:** SMA-20/50 and the volume ratio render under `field_state` provenance;
  `test_prompt_data_parity.py` green and non-vacuous; cross-lane citation by the *other three*
  analysts re-measured and not worse than the table above. One price line, not two.
- **Tier C:** whichever branch is taken, the overlay line and the fetched window agree. If the 2y
  window ships: it goes through `history_with_source`, carries its own provenance, and a missing
  series renders "not available" rather than a shortened read.
- **This CR's own baselines re-measured post-promotion** — output-style compliance (timeframe 56%,
  setup 89%, no-setup acknowledgment 78%, levels 0%, numeric R:R 0%), cross-lane 5/18, novel numbers
  3.1%, over-budget 11%, bullets 50%, stance 18/18. A prompt edit whose effect is not re-measured is
  the CR105 Amendment-1 trap.
- `pytest backend/tests/unit/ -q` green throughout.

---

## Rejected — and why

**1. Add ATR(14) so entry/stop/target and R:R become derivable** (the data-sufficiency review's
headline recommendation, §6.3). **Rejected.** It buys the ability to satisfy an instruction that the
agent's own role text contradicts and that the Trader already owns — and it re-opens a parser surface
this agent has never touched. Any turn stating a full triple gets `_verify_and_annotate_geometry`'s
note, which since DEF235 names the mandate's single-name cap: a sizing figure in AMI's voice on the
turn of the agent told *"Recommend final position sizing. That's the Trader."* Deleting the demand is
free and matches measured behaviour (0/18); supplying a volatility feed to satisfy it is new math, a
new render, a new provenance key and a new failure surface. **ATR has separate merit as a
stop-distance sanity input for the *Trader*** — that is a different CR and a different agent.

**2. Extend the DEF231 directional-coherence check to the Market Analyst.** **Rejected on
measurement.** Replayed the production `_direction_contradictions` over all 16 turns whose prompt
carries a `last close` (the check needs one), with each turn's structured levels reconstructed from
its own prompt: **0 flagged.** The single candidate — KTOS 19:27, *"awaiting a pullback toward the
**$60** support"* — was correctly refused by `_match_structured_level`, because $60 is not a level of
that run (its 50-day low is $43.09). That is the designed miss and the right behaviour. Zero measured
yield; the check stays PM-only (`room_runner.py:3299`).

**3. Strip P/E, news, sentiment and the portfolio block from this agent's copy of the fact sheet**
(the blind review's CUT list). **Not rejected — owned by CR145 Tier C.** `_format_profile(profile)`
takes no `agent_id`, so this is a renderer change with a design decision behind it (Bull/Bear/RM/
Trader/PM legitimately need cross-lane data), not a prompt edit. The 5/18 table above is *evidence
for* that tier, not a second proposal.

**4. The blind review's "no position-in-range" and "direction-blind trend" complaints.** **Already
fixed** (DEF228, DEF227). HEAD renders `50-day range: $L–$H, last close $C (N% of that range)` and
`trend ∈ {uptrend, downtrend, consolidating}`. The blind review audited the stale sample — see Notes.

**5. Failure mode (a): "the model will fabricate concrete prices and an R:R."** **Did not reproduce.**
0/18 triples, 0/18 numeric ratios. Number provenance re-derived: 5 of 162 stated numbers (3.1%) are
"novel". Hand-read per P16 — **3 are the `14` in "RSI(14)"**, the indicator's own period, which the
prompt names in a section the sweep's fact-sheet slice does not cover (a measurement artifact); **1
is correct arithmetic** (BAC *"the midpoint of the 50-day range ($57.16)"* — (50.35+63.97)/2 = 57.16);
**1 is a genuinely invented level** (KTOS *"a pullback toward the $60 support"*). True fabrication:
**1 of 162 numbers, 1 of 18 turns.** The 3.1% headline overstates it ~5×.

**6. Failure mode (c): "the model will omit the STANCE line, add headings or tables, or run long."**
**Did not reproduce.** Stance parsed 18/18, conviction 18/18, headline 18/18 with none over the
32-char cap, **0 truncation marks**, median 3 sentences against a 2–4 guide with 2/18 over, 9/18
using bullets. The machine scaffolds are the healthiest part of this prompt — this is one of the two
agents DEF236 records as holding its length budget.

**7. Put raw OHLCV in the prompt.** **Rejected on budget.** The assembled prompt is already 9,353
chars (corpus median 9,363, range 9,134–9,602); 65 candles would multiply it. Rendering the derived
values (Tier B) is the honest fix, and it is what the Inputs section already implies.

**8. Add MACD / moving-average crossover / Bollinger Bands.** **Stay excluded** (DEF052). The
prompt's negative constraint measures **0/18 violations** — it is one of the few instructions in this
prompt that works exactly as written. Do not weaken it.

---

## Notes

**A correction to a figure this CR was handed.** The stub's *"cleanest of the four analysts —
sentiment 2/18, news 1/18"* and CR145's row's *"Only market_analyst is clean"* are both wrong in the
same direction: 5/18 turns (28%) cite another lane, three of them citing **earnings**, the first item
on this agent's own "You DO NOT" list, which neither figure counted. The ranking is unaffected — it
remains the lowest of the four by a wide margin — so CR145 Tier C's direction stands. Only the word
"clean" needs retracting.

**The corpus is not a single prompt epoch for this agent's data block.** `README.md` fixes the epoch
at 2026-08-07 12:00, but DEF227/DEF228 reached Alpha between **15:48 and 19:17** that day: the 13:32
(AMD) and 15:48 (GRAB) convenes still render `Recent range: $X–$Y` with no position-in-range and
`trend: trading`, a token HEAD cannot emit. That is **2 of 18 convenes, 24 of 216 turns**. Every rate
here was computed both ways; none moves by more than one turn (over-budget 2/18 → 2/16, bullets 9/18
→ 8/16, cross-lane 5/18 → 5/16, novel 3.1% → 3.3%, triples 0/18 → 0/16), so nothing in this CR turns
on it — but the README's own rule is that a pooled rate is meaningless, and the next sweep should cut
at 2026-08-07 19:00.

**`real_samples/market_analyst.prompt.txt` is one of the two stale prompts** (AMD, 13:32 — it is
literally corpus turn 0). It shows `trend: trading`, `Recent range:` with no position-in-range, a
`support/breakout` disclosure header where HEAD says `50-day range`, and an Inputs bullet predating
DEF229(b)'s *"These are levels, not entry triggers"*. Re-capture it before anyone quotes it again.

**What I could not verify.**

- Whether the invented `$60 support` (1/18) is a rate or an accident. n=18 cannot distinguish them,
  and a guard threshold chosen against the single example that motivated it is `failure_patterns`
  **P16** — the same trap DEF237 names for its own plausibility constant. Needs ≥30 convenes before
  it becomes scope. Recording it here so the next sweep looks for it.
- Whether the `Path.ACTIVE` 1H overlay branch ever fires in production. 0/18 in this corpus, and I
  have no query over the mandate table to say how many real users are on that path.
- The real token/rate-limit cost of Tier C's 2y fetch under load. It depends on convene spacing
  against the 60s TTL, which this corpus does not measure.

**Cross-cutting items deliberately not re-litigated here** — owned by
[CR145](../CR145_fundamentals_data_and_lane_discipline/CR145_fundamentals_data_and_lane_discipline.md):
the `_LENGTH_GUIDE` / `_PROSE_FORMAT` / `_STANCE_FORMAT` conflict (**DEF236**), `LearningStyle.QUICK`'s
*"terse, tabular"* against *"no tables"*, and the per-agent fact sheet (`_format_profile` takes no
`agent_id`). Already filed: **DEF235** (the `size` prose-parse — fixed; size now comes from the
mandate cap) and **DEF237** (the missing plausibility backstop on entry/stop/target — open). Tier A
*reduces* DEF237's exposure by removing this agent's instruction to produce its inputs; it does not
replace the backstop, which every other prose agent still needs.

**Sequencing.** Tier A is free, prompt-only, independent, and carries the whole DEF237-adjacent risk
reduction — it should ship alone and first. Tier B is small but must wait on (or knowingly widen)
CR145 Tier C. Tier C needs a decision from Saiful on whether a multi-quarter trend read is a product
feature worth an extra fetch per convene, or whether the overlay sentence should simply be told the
truth about its window.
