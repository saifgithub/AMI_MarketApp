# External review — market_analyst (data sufficiency + supplier check)

> Reviewer: `kimi-for-coding` · Kimi track K session.
> Corpus reviewed: `docs/forward_planning/CR143_agent_prompt_audit/real_samples/market_analyst.prompt.txt`
> and `real_samples/market_analyst.reply.txt` (AMD, fact sheet as of 2026-08-07).
> Unlike `external_review/room/market_analyst.md` (blind prompt-coherence audit),
> this review had codebase access. Every availability claim below is verified against
> the actual fetch path — these are **findings, not hypotheses**.
>
> **Staleness caveat on the sample itself:** the captured prompt predates HEAD on
> three renderer points. It shows `trend: trading` — a token current code can no
> longer emit (DEF227 made the read directional: `uptrend`/`downtrend`/
> `consolidating`, `technicals.py:126-133`); it shows `Recent range:` with no
> position-in-range — current code renders `50-day range: $low–$high, last close
> $X (N% of that range)` (DEF228, `room_prompts.py:795-813`); and its disclosure
> header says `support/breakout` where HEAD says `50-day range`
> (`room_prompts.py:599`). Two of the blind review's data complaints are therefore
> already remediated in HEAD; the sample should be re-captured.

## 1. Question

Does the Market Analyst have enough data in the fact sheet to do its job to
~95% accuracy?

## 2. Answer

**Yes for the narrow deliverable the data block actually supports, no for the
job the role text describes.**

The supplied technicals are seven scalars: reference price **$494.31**
(prompt line 99), RSI **49** + tone (line 103), trend label (line 103),
50-day range **$424.03–$584.73** (line 104), volume tone **in-line with
20-day average** (line 105), 52-week range **$149.22–$584.73** (line 106).
That is enough for: a trend/momentum read, a range-position statement, a
support/resistance pair, and an honest "no setup" call — which is exactly
what the live reply produced. Estimated accuracy on that scoped deliverable:
**~90–95%**.

Against the job as written — "You read charts" (line 4), "Patterns … support
and resistance, trend identification" (line 8), "Provide specific levels:
entry, target, stop-loss" + "Risk-reward ratio" (lines 28–29), role guidance
"Emphasise monthly/quarterly trend" (line 76) — coverage caps out at
**~55–65%**. There is no chart, no OHLCV series, no moving-average values, no
volatility measure, and only ~65 daily candles of lookback behind the scenes.
The entry/target/stop + R:R demands are structurally unsatisfiable without
violating the grounding directive (line 2); the only compliant escape is
declaring no setup, which the model did.

## 3. Data gaps (from the prompt alone)

| # | Gap | Impact |
|---|---|---|
| 1 | No OHLCV series / no chart | The Inputs section claims "Daily price history (yfinance OHLCV)" (line 12) as an input; only derived scalars are rendered. "You read charts" is unfollowable literally. |
| 2 | SMA-20 / SMA-50 values absent | The trend label cites "a 20/50-day moving-average trend read" (line 13) the agent cannot verify or reason from — a label with the evidence withheld. |
| 3 | No position-in-range in the sample | The model had to join the quote (line 99) to the range (line 104) itself — the exact join DEF228 records failing on live Alpha. Fixed in HEAD; stale sample. |
| 4 | No trend direction in the sample | `trend: trading` is direction-blind; fixed in HEAD (DEF227). Stale sample. |
| 5 | No monthly/quarterly trend | Role guidance says "Emphasise monthly/quarterly trend. Skip noise-level intraday signals" (line 76); the computation behind the sheet fetches only `3m` (~65 daily candles, `technicals.py:42`). A quarterly read is unproducible. |
| 6 | No volatility measure (ATR or similar) | Entry/target/stop and R:R (lines 28–29) cannot be sized; only two range levels exist. |
| 7 | No volume numbers | Only a three-state tone string; the recent-vs-baseline ratio is computed then discarded. |
| 8 | No RSI history/direction | Single point reading; "RSI clearing 70 off an oversold base" (Voice, line 41) requires a series that is computed but not surfaced. |
| 9 | Voice examples outrun the data | "Breakout from a 3-month base" (line 41) vs a support/breakout window of 50 trading days (~2.4 months, `technicals.py:148-149`). |
| 10 | Role/style self-contradiction | Output style demands inferred levels + R:R (lines 28–29); grounding directive forbids inference (line 2). Not a data gap — a spec defect the data cannot fix by itself. |

## 4. Supplier check — what the codebase can actually deliver

Compute path: `compute_technicals(ticker)` — `backend/app/services/technicals.py:75-162`
(Cutler's RSI, SMA-20/50, 5-day vs 20-day volume, 50-day min-low/max-high,
over `MarketDataProvider.history(ticker, "3m")`). Profile wiring:
`room_runner.py:494-526` (one `field_state["technicals"]` gate for the block,
WITHHELD_TENURE path at `room_runner.py:506-507`). Rendering:
`room_prompts.py:694-711` + `_range_line` (`room_prompts.py:795-813`).
Indicator library: `backend/app/trading_math/indicators.py:20-50` — `rsi`,
`rsi_tone`, `sma` only; no ATR/MACD/Bollinger anywhere.

| # | Item | Verdict | Evidence / effort |
|---|---|---|---|
| 2 | SMA-20/50 values | **FETCHED, DISCARDED** | `sma_short`/`sma_long` computed at `technicals.py:114-115`, consumed only by the alignment test at `:126-127`, then dropped. One render-key change — the trend claim becomes verifiable. |
| 3 | Position-in-range | **ALREADY WIRED (post-sample)** | `range_position_pct` (`technicals.py:62-72`) rendered via `_range_line` (`room_prompts.py:795-813`, DEF228). The sample predates it; the AMD join (494.31 in 424.03–584.73 = ~44%) would now be stated. |
| 4 | Trend direction | **ALREADY WIRED (post-sample)** | `technicals.py:126-133` (DEF227). Sample's `trading` token is unreachable in HEAD. |
| 5 | Monthly/quarterly trend | **AVAILABLE, NOT WIRED** | Same provider, same call shape: `_PERIOD_MAP["2y"]` = 504 daily bars (`market_data.py:156`, CR136) supports SMA-100/200 and a genuine quarterly read; `"1y"` weekly bars also exist (`market_data.py:155`). Effort: one extra `history()` call + a long-window SMA in `compute_technicals`. No new provider. |
| 6 | ATR / volatility | **AVAILABLE, NOT WIRED** | OHLCV already in hand inside `compute_technicals` (`technicals.py:103-106`); ATR is new code in `trading_math/indicators.py` (which today has only rsi/rsi_tone/sma), not a new feed. This is the missing ingredient for grounded stop distances and R:R. |
| 7 | Volume numbers | **FETCHED, DISCARDED** | `recent_vol`/`baseline_vol` computed at `technicals.py:135-136`, reduced to a tone at `:138-144`. Ratio (e.g. "0.9× 20-day avg") is one render. |
| 8 | RSI series | **AVAILABLE, NOT WIRED** | Computable from `closes` already fetched (`technicals.py:103`); needs a few lines in `trading_math/indicators.py`. |
| 1 | OHLCV in prompt | **WIRED, DELIBERATELY NOT RENDERED** | Candles flow through the block and are dropped after computation. Surfacing 65 rows would blow the prompt budget; the honest fix is rendering the *derived* values (2, 5–8), not raw bars. The Inputs line "Daily price history (yfinance OHLCV)" (sample line 12) overstates what the agent receives. |
| 9 | 3-month base window | **AVAILABLE, NOT WIRED** | Support/breakout is fixed at 50 candles (`technicals.py:148-149`) inside a 3m fetch; widening to the full ~65-candle window or a 6m fetch is a constant change. |

Note on the shared fact sheet: the four analysts are deliberately "four
independent lenses on ONE shared data block" (`room_runner.py:145-156`) —
there is **no per-agent field filtering today**. The blind review's CUT list
(strip P/E, news, sentiment, portfolio block from the market analyst's copy)
is therefore a code change in `room_prompts._format_profile` /
`room_runner`, not a prompt edit.

## 5. Structural caveats before wiring #5 / #6

1. **History is cached 60s, keyed `ticker:period`.** `CachingProvider`
   (`market_data.py:404, 437-446`). A `"2y"` pull adds one heavier yfinance
   `.history()` call (~504 rows) per ticker per convene; back-to-back runs
   within 60s amortize, spaced runs multiply Yahoo exposure — same
   rate-limit class as the fundamentals statement calls flagged in the
   fundamentals review.
2. **Failure mode is already clean.** `compute_technicals` never raises and
   returns None on short/non-finite/synthetic series (`technicals.py:97-108,
   160-162`); the runner degrades the whole block to UNAVAILABLE
   (`room_runner.py:523-524`) and the renderer prints "not available this
   call" (`room_prompts.py:710-711`). Adding a second period must keep the
   same all-or-nothing contract — a 2y gap must not silently shrink the
   long-trend read without provenance.
3. **Synthetic feed is refused for technicals** (DEF229, `technicals.py:97-99`)
   — MockWalk produces quotes/candles only, so a yfinance outage already
   renders "not available", never fabricated indicators. Any new window
   inherits this only if it goes through `history_with_source`, not raw
   `history()`.

## 6. Recommended slice (if this becomes a CR)

Cheap, high-yield, no new provider:

1. Render SMA-20/50 values and the volume ratio (already computed, discarded).
2. Add a long-window read via the existing `"2y"` daily series (SMA-100/200
   or a 13-week trend) to back the "monthly/quarterly" role guidance — or
   soften that guidance line.
3. Add ATR(14) to `trading_math/indicators.py` and surface it, so
   entry/target/stop + R:R become *derivable* rather than *inferred* —
   this is the only way to resolve the grounding-vs-levels contradiction
   on the supply side. Companion: scope the output style so levels/R:R are
   required only "when a setup is present".
4. Re-capture `real_samples/market_analyst.prompt.txt` — it predates DEF227/
   DEF228 and misrepresents what HEAD sends.

MACD/crossover/Bollinger stay excluded by design (DEF052); raw OHLCV stays
out of the prompt (budget). Per-agent fact-sheet filtering (the blind
review's CUT list) is a separate, structural decision.

## 7. Relationship to the blind review (`../market_analyst.md`)

~50% overlap, mostly confirmatory:

- **Confirmed:** contradiction (a) — grounding directive vs demanded
  entry/target/stop + R:R. Structural; the live reply escaped it only by
  declaring no setup. Supplier check shows the supply-side fix exists (ATR,
  #6 above).
- **Confirmed:** contradiction (c) — "read charts" with no chart. The Inputs
  section claims OHLCV as an input; only scalars render
  (`room_prompts.py:694-711`).
- **Confirmed:** "trend without MA values" — SMA values computed and
  discarded (`technicals.py:114-115`).
- **Confirmed:** the length-cap and tabular-tone tensions are real but
  benign — the live reply satisfied 2–4 sentences, bullets, bold, and the
  stance line simultaneously.
- **Killed as live behaviour:** failure mode (a) hallucinated levels/R:R —
  did not occur; the model withheld levels rather than fabricate them.
  Failure mode (b) domain bleed into fundamentals/news — did not occur for
  this agent (contrast the fundamentals_analyst reply, where it did).
- **Outdated premises:** the blind review's "no position-in-range" and
  direction-blind trend complaints are already fixed in HEAD (DEF227/DEF228);
  it audited a stale renderer, same as this sample.
- **Could not see (code-level):** the shared-fact-sheet architecture
  (`room_runner.py:145-156`), which turns its CUT list from a prompt edit
  into a renderer change; the WITHHELD_TENURE stripping path
  (`room_runner.py:506-507`, `room_prompts.py:690-693`); the synthetic-feed
  refusal and 60s history cache.

## 8. Reply-sample verification (`real_samples/market_analyst.reply.txt`)

The actual model response was checked line-by-line against the data block.

**Numerically clean.** Every figure cited is in the block: **49** (line 103),
**$494.31** (line 99), **$424.03** (line 104), **$584.73** (lines 104/106),
**in-line with 20-day average** (line 105), **trading** (line 103). Zero
hallucinated numbers, zero training-memory leakage.

**Arithmetic spot-check.** "Sitting in the middle of the 424.03–584.73
range": (494.31 − 424.03) / 160.70 ≈ **43.7%** — defensibly "middle" (2%
below the midpoint). HEAD would now state this as "44% of that range"
(DEF228). "52-week high of 584.73" matches line 106 exactly.

**One unlabeled inference.** "A lack of institutional conviction" — volume
in-line says nothing about institutions; qualitative, no supporting datum.
No number claimed, so the letter of the grounding directive held; the spirit
bent. "Key resistance"/"floor for mean reversion" are level labels directly
grounded in the range fields — acceptable.

**Scope bleed: none.** No fundamentals, no catalysts, no sentiment, no
sizing — despite all of those sitting in the shared fact sheet. The role
firewall held where the fundamentals_analyst's reply failed. Zero
violations of the "You DO NOT" list.

**Stance-evidence tension: none.** `STANCE: neutral | CONVICTION: medium`
over a body arguing neutral/wait-for-levels — header and body agree.

**Format compliance.** Stance line first, exact shape, written once;
HEADLINE "RSI 49 at $494.31" = 17 chars ≤ 32. One-sentence thesis + 3
bullets; **bold** on metrics; no headings/tables/fences; no "As the X"
preface; 4 sentences total against a 2–4 cap. Timeframe stated ("daily
chart"); setup correctly declared absent per "Acknowledge when a setup is
*not* present". Entry/target/stop and R:R omitted — the only grounding-
compliant choice available, and itself evidence for gap #10.

**Net: GROUNDED.** The reply is bound to the data on facts and, unlike the
fundamentals_analyst sample, bound to its role on domains. Its one defect
(unlabeled "institutional conviction" inference) is minor; its compliance
under a self-contradictory spec is evidence that the spec — not the model —
is the defect carrier here.
