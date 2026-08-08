# External review — fundamentals_analyst (data sufficiency + supplier check)

> Reviewer: `kimi-for-coding` · Kimi track K session.
> Corpus reviewed: `docs/forward_planning/CR143_agent_prompt_audit/corpus/REAL_fundamentals_analyst_prompt_AMD.txt`.
> Unlike `external_review/room/fundamentals_analyst.md` (blind prompt-coherence audit),
> this review had codebase access. Every availability claim below is verified against
> the actual fetch path — these are **findings, not hypotheses**.

## 1. Question

Does the Fundamentals Analyst have enough data in the fact sheet to do its job to
~95% accuracy?

## 2. Answer

**Yes for the job as scoped in the prompt, no for a real fundamental read.**

The prompt itself narrows the job: "from what real market data actually delivers —
not a full research-desk statement package." Against that narrowed scope (a
ratio-based thesis + evidence bullets), coverage is good:

- Valuation stack complete: P/E **126.4**, P/S **19.5x**, EV/EBITDA **82.6x**,
  PEG **1.12**, FCF yield **1.1%** — enough to triangulate "expensive, growth-priced".
- Growth/profitability snapshot: TTM revenue growth **50%**, profit margin **16%**,
  net cash **$8,835M**.
- Forward anchor: next earnings **2026-11-03**, consensus EPS **$1.925**, Street
  target **$608.23** correctly labelled consensus, not guidance.

Estimated accuracy on the scoped deliverable: **~90–95%**.

Against a genuine fundamental assessment (margin durability, capital allocation,
balance-sheet quality — the very things the role guidance says to prioritise),
the data caps out closer to **70–75%**.

## 3. Data gaps (from the prompt alone)

| # | Gap | Impact |
|---|---|---|
| 1 | No margin trend (direction, YoY bps) | The prompt's own style example ("32.4% gross margins, up 180bps YoY") is unproducible with this data. |
| 2 | P/E basis unstated (trailing vs forward) | At P/E 126.4 and consensus EPS ~$1.93/qtr this materially changes the thesis. |
| 3 | No FCF dollar figure, only 1.1% yield | Can't speak to FCF consistency/scale. |
| 4 | No revenue mix / segments | For AMD, data centre vs client vs gaming IS the fundamental story. |
| 5 | No peer baseline | "Expensive" is absolute, never relative to semis. |
| 6 | No debt detail | Net cash implies strength; no gross debt, no maturities. |
| 7 | Buybacks unavailable | Yet role guidance says prioritise capital allocation; live catalyst is an acquisition. |
| 8 | M&A history unavailable | Same contradiction. |
| 9 | Company guidance unavailable | Correctly labelled as such; consensus is a partial substitute. |

## 4. Supplier check — what the codebase can actually deliver

Fetch path: `fetch_live_fundamentals(ticker)` — `backend/app/services/fundamentals.py:116-284`.
The **only** yfinance fundamentals call today is `yf.Ticker(t).info`
(`fundamentals.py:141`). No statement endpoints (`income_stmt`, `balance_sheet`,
`cashflow`) are called anywhere in the repo. Fact-sheet assembly:
`room_runner.py:424-612` (per-field `field_state` provenance, field lists at
`room_runner.py:337-354`); renderers `room_prompts._format_profile`
(`room_prompts.py:503`) and `build_live_data_block` (`fundamentals.py:355-442`).

| # | Item | Verdict | Evidence / effort |
|---|---|---|---|
| 2 | Forward P/E | **ALREADY WIRED** | `forwardPE` read at `fundamentals.py:180-181` (DEF233), labelled render via `pe_line()` (`fundamentals.py:287-316`). The AMD corpus shows trailing-only because AMD's `forwardPE` was absent at fetch time — provider gap, not missing wiring. |
| 3 | FCF dollars | **FETCHED, DISCARDED** | `freeCashflow` read at `fundamentals.py:247`, immediately divided by `marketCap` into `fcf_yield`. One render-key change. |
| — | Market cap (not in my original gap list; flagged by the parallel blind review as making the liquid-only rule unfollowable) | **FETCHED, DISCARDED** | `marketCap` is already in hand (denominator of the FCF-yield calc). Same one-render class as FCF $. |
| 6 | Gross debt | **FETCHED, DISCARDED** | `totalDebt` read at `fundamentals.py:220`, consumed only inside `net_cash_millions`. One render. Coarse short/long split additionally available un-wired via `.balance_sheet`. Maturity ladder: **not available** from Yahoo, ever. |
| 1 | Margin trend | **AVAILABLE, NOT WIRED** | `.income_stmt` / `.quarterly_income_stmt` expose gross/operating/net lines for ~4 annual + 5 quarterly periods — margins and YoY direction computable with zero new providers. Cheap variant: `.info` already carries point-in-time `grossMargins`/`operatingMargins` keys we don't read (we only take `profitMargins`, `fundamentals.py:215`); a trend needs the statement series. |
| 7 | Buybacks | **AVAILABLE, NOT WIRED** | `.cashflow` / `.quarterly_cashflow` carries "Repurchase Of Capital Stock" history; `get_shares_full()` gives share-count trend as proxy. Note: `fundamentals.py:253-254` and the agent base prompt in `content/agents/` currently claim buybacks are "not available" — true of `.info`, **false once statement endpoints are used**. Wiring this retires a baked-in disclosure; prompt and `PHASE1_ground_truth.md` must update alongside. |
| 5 | Peer baseline | **NOT AVAILABLE as-is; DIY-able** | No peer list or industry-average multiples in yfinance (code says so itself, `fundamentals.py:259-262`). Could be built from the sector/industry strings we already fetch + a static peer mapping + N extra `.info` calls — that's building a dataset, not using a feed. |
| 4 | Revenue mix / segments | **NOT AVAILABLE** | Yahoo exposes no segment revenue. Needs a new provider (SEC EDGAR, Alpha Vantage). |
| 8 | M&A history | **NOT AVAILABLE** | Needs filings/news-derived source. Current "not available" disclosure stays correct. |
| 9 | Company guidance | **NOT AVAILABLE** | Not in Yahoo's data. Closest: Street estimate ranges via `.earnings_estimate` / `.revenue_estimate` / `.growth_estimates` — already labelled consensus, never guidance (`fundamentals.py:270-282`). |

## 5. Structural caveats before wiring #1 / #7

1. **Fundamentals have zero caching.** Every Room convene and every 1-on-1 message
   hits `yf.Ticker().info` live. (Quotes 60s, news 5-min, earnings 6h via
   `CachingProvider` in `market_data.py`; Reddit sentiment has a durable Postgres
   cache in `social_context.py`.) Adding 2–3 heavier statement calls per run
   multiplies Yahoo rate-limit exposure unless a TTL fundamentals cache lands in
   the same change.
2. **Statement endpoints are flakier than `.info`.** Per-field `field_state`
   provenance already exists, so gaps degrade cleanly to UNAVAILABLE — but expect
   more missing fields than on the quote path.

## 6. Recommended slice (if this becomes a CR)

Cheap, high-yield, no new provider:

1. Render FCF $, market cap, gross debt (all already fetched).
2. Wire `.income_stmt` (margin trend) and `.cashflow` (buybacks).
3. Add a TTL fundamentals cache in the same change (mandatory companion to step 2).
4. Update the fundamentals analyst base prompt (`content/agents/`) and
   `PHASE1_ground_truth.md` to retire the "buybacks not available" disclosure.

Segments, M&A, and guidance stay out of scope — they need a new provider and
should be a separate decision.

## 7. Relationship to the blind review (`../fundamentals_analyst.md`)

~30% overlap: both flag the margin/capital-allocation data gap, with opposite
remedies — the blind review says *cut the demand* (delete the 180bps example,
narrow the role guidance), this review says *supply the data* (the provider
already has it). The other ~70% doesn't intersect: the blind review covers
prompt-internal contradictions (format, scope-bleed, mandate noise) that this
review does not assess; this review supplies the codebase verification the blind
review structurally cannot. The two compose: its cut list defines what the agent
should see; this supplier check defines what we can actually put in front of it.

## 8. Reply-sample verification (`real_samples/fundamentals_analyst.reply.txt`)

The actual model response to the AMD corpus prompt was checked line-by-line
against the data block.

**Numerically clean.** Every figure cited is verifiably in the data block
(126.4 P/E, 19.5x P/S, 50% growth, 16% margin, $8,835M net cash, 82.6x
EV/EBITDA, 1.1% FCF yield, 1.12 PEG, $149.22–$584.73, $494.31, $608.23,
RSI 49, 2026-11-03, $1.92529). Zero hallucinated numbers. The "near the upper
end" claim is arithmetically sound (~79% of the 52-week range). The grounding
directive held on facts.

**Three non-numeric defects:**

1. **Scope bleed — blind-review failure mode #2 confirmed live.** Bullet 3 is
   half technical analysis ("testing momentum", "technical neutrality via a 49
   RSI", "in-line volume") — the Market Analyst's barred domain. Bullet 1 leans
   on the Taalas headline — news flow, the News Analyst's barred domain. The
   data block carries RSI and headlines *for other agents*; the model used them
   anyway. This empirically supports the blind review's CUT recommendation to
   strip technical/catalyst/sentiment fields from the fundamentals prompt.
2. **Inference beyond the data.** "Ample runway for continued R&D" (no R&D
   figure exists) and "aggressive capital allocation strategy" (the prompt
   states capital-allocation data is unavailable) — no numbers claimed, so the
   letter of "never claim a number" held, but the spirit did not.
3. **Stance-evidence tension.** `STANCE: for | CONVICTION: medium` over a body
   that reads cautionary ("significant near-term execution risk", "premium
   valuation that requires sustained high growth to justify", "the market is
   waiting for the next catalyst"). Defensible, but the header is stronger than
   the argument beneath it.

**Net:** the reply is bound to the data on facts, not bound to its role on
domains. Two of three bullets drift into other agents' lanes — exactly the
overlap the four-analyst separation exists to prevent.
