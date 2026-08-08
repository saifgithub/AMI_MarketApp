# CR147 — The News Analyst does everyone else's job, and half its feed is about another company

**Filed:** 2026-08-08 · **Status:** proposed · **Decision:** Saiful, 2026-08-08 — *"book CRs one for
each agent."* One CR per agent so each remedy is decided on its own evidence.
**Source:** CR143 Phase 1/3b plus two independent reviews of the News Analyst — a blind
prompt-coherence audit ([`external_review/room/news_analyst.md`](../CR143_agent_prompt_audit/external_review/room/news_analyst.md))
and a codebase-verified data-sufficiency audit ([`external_review/room/kimi/news_analyst_data_sufficiency.md`](../CR143_agent_prompt_audit/external_review/room/kimi/news_analyst_data_sufficiency.md)).
Every claim below went through a **supplier check** (does the code inject what the prompt claims?)
and a **parser check** (does anything read the output the instruction shapes?), and every rate was
re-derived against the committed epoch corpus — `corpus/llm_audit_2026-08-07-epoch.json`, n=18
News Analyst turns inside 216 turns / 18 convenes. CR105's Amendment 1 is why: written from prompt
files alone, 2 of its 4 findings were wrong and its "fix" would have turned an existing guard red.

## Why

### 1. The lane firewall does not hold at all here — and the figure this CR was handed understated it

The stub, and CR145's row, say this agent cites *valuation 16/18, technicals 13/18, sentiment 9/18*.
Re-derived per-turn and hand-read against all 18 replies:

| lane cited | rate | rule |
|---|---|---|
| valuation / fundamentals | **18/18** | any of P/E · P/S · EV/EBITDA · PEG · FCF yield · rev growth · profit margin · net cash · 52-wk · analyst consensus / price target |
| — fundamentals ratio or balance-sheet field only | 16/18 | the narrower rule the handed figure was measuring |
| technicals | **14/18** | RSI · trend · volume vs 20-day · 50-day range · last close · overbought/consolidating |
| sentiment | **7/18** numeric · 9/18 including a bare mention | Reddit · buzz · bull/bear split · sentiment score |
| **cites at least one other lane** | **18/18** | — |
| **stays inside its own lane** | **0/18** | — |

16/18 is defensible under the narrower rule; the honest headline is **18/18 — every single News
Analyst turn in the epoch borrows another analyst's numbers, and not one turn stays in lane.**
Technicals is 14/18, not 13. Sentiment's 9/18 counts bare mentions; a *number* appears in 7.

Run under one consistent rule across the four analysts, same 18 convenes:

| analyst | own lane | cites ≥1 other lane |
|---|---|---|
| **news_analyst** | news 16/18 | **18/18** |
| fundamentals_analyst | valuation 18/18 | 11/18 |
| social_media_analyst | sentiment 18/18 | 11/18 |
| market_analyst | technicals 18/18 | 6/18 |

**"Worst cross-lane offender" survives, at the ceiling.** (CR146 and CR148 re-derived their own
agents under their own rules and land within ±2 of this table; the sibling CRs' ranking is
unaffected. This is rule drift between three independently written measurements, not disagreement.)

The sharpest form of it is the agent's own explicit prohibition: *"Comment on chart patterns. That's
the Market Analyst"* (`content/agents/news_analyst.md:33`) — **15/18 turns use a chart/technical
term** (14/18 with a number). And the leading claim of the turn — the first sentence or first
bullet — is a non-news claim in **5/18**. Of the 18 `HEADLINE:` fields, the one line the UI shows
as the summary, **7 are pure valuation** (*"357x P/E vs 2% margin"*, *"85% TTM revenue growth"*,
*"Consensus target of $5.89"*).

This is the same root CR145 Tier C owns — `_format_profile(profile)` takes no `agent_id`
(`room_prompts.py:503`), so all 12 agents get a byte-identical sheet. **This CR does not
re-litigate that; it supplies the strongest evidence for it.** The News Analyst is the acid test:
its own lane's data is the thinnest on the sheet (three headline strings and a date), so it reaches
for the richest thing in front of it.

### 2. A permanently-false conditional in the prompt, and it produced a fabricated provenance

The base prompt promises *"where configured — Alpha Vantage's per-article sentiment-scored feed"*
and *"Where Alpha Vantage supplies it, a sentiment tag per headline"*
(`content/agents/news_analyst.md:16-17`); the shared fact-sheet header repeats it to all 12 agents:
*"Some headlines may carry a sentiment tag; treat it as one input, not a verdict"*
(`room_prompts.py:613-615`).

Verified on both halves, live on Alpha 2026-08-08:

- **News IS live** — and via **Yahoo/yfinance**, not Adanos. `USE_REAL_MARKET_DATA=true`;
  `_YfinanceSource` (`news_context.py:122-141`) delegates to the shared provider stack. All 18
  epoch convenes rendered real headlines. Adanos powers the **Social** analyst's Reddit feed, a
  different supplier on a different lane — the two must not be conflated.
- **Alpha Vantage is genuinely absent.** `infra/alpha.env:84` has `# ALPHA_VANTAGE_API_KEY=`
  commented out; `docker exec ami_api_alpha printenv ALPHA_VANTAGE_API_KEY` returns empty, so
  `settings.alpha_vantage_api_key` is falsy and `fetch_live_news` never even tries the second source
  (`news_context.py:250`). Measured on the corpus: **216/216 prompts assert the tag may exist;
  0/216 catalyst lines carry one.** (Same finding CR148 recorded and handed to this CR.)

What the model does with a condition that is never true: **1 of 18 News turns invented the tag.**
SNDK 19:27 — *"the sentiment tag from 24/7 Wall St. regarding Seagate/Micron volatility requires
careful noise filtering"*. There is no sentiment tag, and 24/7 Wall St. issued none. This is not a
wrong number — CR143's M3 puts this agent at 0.0% novel numbers and that holds (below) — it is an
invented **provenance**, which no numeric-provenance metric can see. CR040's own test applies:
*if this fires constantly and silently, what does the user end up believing?*

### 3. Two of the five Output-style bullets cannot be executed, and never were

| instruction | supplier check | measured |
|---|---|---|
| *"State the expected vs actual (e.g. 'consensus was +2.1%, actual was +4.3% — beat')"* (`:25`) | Only a **forward** consensus exists. `YfinanceProvider.earnings` reads `.calendar`'s `Earnings Average` (`market_data.py:643,656`); `.earnings_dates` — which carries EPS Estimate / Reported EPS / Surprise(%) — **appears nowhere in `backend/`** (grep: zero hits) | **0/18** turns state an expected *and* an actual. 3/18 use beat/miss language, all qualitative and all lifted from a headline |
| *"Identify second-order effects (peers, suppliers, customers)"* (`:26`) | **No entity data of any kind.** Sector/industry strings (`room_prompts.py:839-846`) are the only hook | 0/18 derive one from supplied data; the 3 turns naming another company (Taalas, Nvidia/Microsoft, Micron) took the name from a headline |
| *"Weight macro structural news (Fed cycle, fiscal policy) higher than single events"* (`overlay_generator.py:306-307`, `Path.LONG_HORIZON` only) | The **entire** macro dataset is `_FOMC_DECISION_DATES` → one countdown string (`room_runner.py:266-282`); CR038 already deleted the synthetic sector-earnings half | 18/18 prompts carry it. Two turns duly made the FOMC countdown their headline claim — the instruction is followed by promoting a date with no content |
| *"Filter headlines to user's holdings + watchlist relevance"* (`overlay_generator.py:296`) | Holdings **are** injected (CR055 snapshot, `room_runner.py:295-297`). `WatchlistStore.list_for_user` exists (`watchlist_store.py:32-39`), the router is mounted — and `room_runner.py`/`room_prompts.py` never read it (grep: zero hits) | half-executable by construction |

*"3 items max per response"* is the one that holds: 0/18 turns exceed 3 bullets.

### 4. The feed has no relevance ranking — and the user is charged for it

`_merge_headlines` dedupes and **sorts by recency only** (`news_context.py:303-318`). There is no
relevance score anywhere in the path. Measured on the epoch:

- **26/54 headlines (48%) mention the ticker or the company name.**
- **The top headline — the one that becomes `profile["catalyst"]`, the single item the shared fact
  sheet leads with for all 12 agents — is off-ticker in 9/18 convenes (50%).** AVGO's Room was
  handed *"The Toughest Questions AMD Faced On Its Latest Call"*; the AMD 19:25 convene got three
  headlines, all about Nvidia.
- **2/18 convenes had zero on-ticker headlines** (AMD 19:25, AVGO).
- The model largely copes — it named the mismatch outright in AMD 19:25, and **5/18 turns
  (ANET, MU, AVGO, LITE, SNOA) reference no supplied headline at all**, which is the honest
  response to a feed with nothing in it and also a News Analyst turn containing no news.

This is a paid feature. A LIVE news feed adds `LIVE_DATA_SURCHARGE = 2` credits per convene
(`credit_service.py:99-110`, charged in `_resolve_and_charge_feeds`, `room_runner.py:2547-2565`).
Whatever the ranking is worth, it is being billed.

### 5. Staleness: a thin-coverage tail, **not** the social-cache problem

CR148 found `social_sentiment_cache` 93% older than 7 days, mean 20.2 days, under a header saying
*"as of this call"*. **The news path does not have that defect.** `CachingProvider.news` has a
**5-minute TTL** (`market_data.py:463`) — the fetch is fresh by construction. Publication age,
parsed off all 54 rendered catalyst lines:

| | value |
|---|---|
| median age | **0.083 d ≈ 2.0 h** |
| under 1 day | 49/54 (91%) |
| over 7 days | **3/54 (5.6%)** — all three in one convene |
| mean | 20.18 d |

**The mean is a trap and it is worth naming explicitly, because it coincides to two decimal places
with CR148's social figure.** It is one ticker: SNOA's three headlines were 353 d, 358 d and 358 d
old, rendered under *"Recent catalyst/headline: LIVE, real news as of this call"*
(`room_prompts.py:613`). Probed live from the Mac 2026-08-08, `yf.Ticker("SNOA").news` returns
**3 articles, newest `2025-08-19`** — so this is a **supplier** fact about a thin microcap, not a
cache fact, and no cache change touches it. The model refused it correctly (*"No live headline data
or earnings catalysts are present in the current feed"*), which is the right behaviour arriving
from the model rather than from a control. There is no recency floor in the code.

### What is working, stated so it is not re-opened

- **Grounding holds.** 207 numeric tokens across the 18 replies; **0 (0.0%) absent from that
  turn's own prompt.** The blind review's predicted "hallucinated ticker-specific signal" did not
  reproduce. The defect in §2 is non-numeric.
- **The machine channel parses.** `parse_stance_envelope` returns a stance in **18/18** and a
  conviction in 18/18.
- **The level parser is inert on this agent.** 8/18 turns state a `target` (an analyst price
  target); **0 state an `entry` and 0 a `stop`**, so `_verify_and_annotate_geometry` — which runs on
  every prose agent (`room_runner.py:3526`) — trips **0/18**. The DEF235/DEF237 family has no
  exposure here.
- **Truncation: 0/18.** No turn ends unterminated; median 636 chars against a 600-token budget.

## Scope — three tiers, ordered by cost

### Tier A — prompt-only, free, ships alone

1. **Resolve the Alpha Vantage conditional (§2).** Either populate `ALPHA_VANTAGE_API_KEY` on
   melehost (zero code — compose already forwards it at `docker-compose.yml:258`, `config.py:195`
   exists, the source, cache, merge and `format_headline` render are all wired,
   `news_context.py:144-229`) **or** delete both claims: `content/agents/news_analyst.md:16-17` and
   the shared header line `room_prompts.py:613-615`. Not both half-done. Note the header line goes
   to **all 12 agents**, so deleting it is a shared-block edit under CR145 Tier B's blast radius.
   If the key is turned on instead, `resolve_news_feed`'s own docstring warning applies
   (`news_context.py:289-294`): availability is probed even for non-entitled users, so a metered
   key makes quota an entitlement-gating question — the DEF063 warning at `docker-compose.yml:256-257`.
2. **Delete `content/agents/news_analyst.md:25` (expected vs actual)** unless Tier C ships in the
   same pass. It is the only instruction in the prompt that models a number shape the stack cannot
   produce, inside a grounding directive that forbids inventing it.
3. **Delete `:26` (second-order effects).** No entity data exists and none is planned. This is the
   same class as CR145 Tier A's `32.4% gross margins` example.
4. **Fix the watchlist half of `overlay_generator.py:296`** — delete the word, or wire it (Tier B).
5. **Soften `overlay_generator.py:306-307`** to the macro that exists (one FOMC countdown), or
   supply macro data (a new provider, out of scope).
6. Add the recency qualifier to the catalyst header, paired with Tier B's floor.

**Not in this CR:** *"Like a Bloomberg wire report compressed to two paragraphs"* vs
*"Write 2–3 sentences"* vs *"thesis + bullet points"* — that is DEF236, owned by CR145 Tier B.
Measured here for its baseline: guide 2–3 sentences, median **3**, **8/18 (44%) over**, bullets
**9/18 (50%)** — the stub's figures re-derive exactly.

### Tier B — supplier work already paid for (same call, no new provider)

1. **A recency floor on the news feed.** Verified live: yfinance returned **10 articles for 7 of 8
   probed tickers** and 3 for SNOA, whose newest was 354 days old. The fix is not more headlines,
   it is refusing to label a year-old article *"as of this call"* — drop items past a threshold and
   let `field_state["news"]` fall to `UNAVAILABLE` (the honest synthetic-catalyst disclosure at
   `room_prompts.py:626-630` already exists and already works), or render the absolute age. Also
   the honest place to stop charging the 2-credit surcharge for it.
2. **Render Yahoo's `summary`.** `YfinanceProvider.news` parses each article's `content` dict and
   keeps only title/link/publisher/published_at (`market_data.py:585-603`); `summary` is on the
   payload and dropped. Verified live across 73 articles: **present on every one**, median 143
   chars, range 33–500. One field each on `NewsItem` (`market_data.py:83-89`) and `LiveHeadline`
   (`news_context.py:106-115`). **Cost to state honestly:** ~430 chars on a **shared** block
   (+4.5% of a 9,630-char prompt) **× 12 agents per convene**. Gated on CR145 Tier C for the same
   reason CR146 Tier B is — widening the shared sheet widens the leak §1 measures.
3. **Inject the watchlist.** One line from `WatchlistStore.list_for_user`. Sized before building:
   Alpha holds **29 rows across 10 users, mean 2.9 tickers; 58 distinct users have run a Room**, so
   this reaches **10/58 (17%)** of them today. Small, real, and cheaper than deleting the
   instruction is honest.

### Tier C — one new fetch, gated on the cache decision

**Wire `.earnings_dates`** (last 4 quarters: EPS Estimate / Reported EPS / Surprise %) so
Tier A #2's instruction becomes producible, and render one *"last reported: est $X, actual $Y —
beat/miss"* line. Verified available on the pinned client: `yfinance 1.3.0`, both
`Ticker.earnings_dates` and `Ticker.get_earnings_dates` present. It must ride the **existing 6-hour
earnings cache** (`market_data.py:476`) from day one — `fundamentals.py`'s zero-caching is the
anti-precedent CR145 Tier D is gated on.

**Out of scope, new-provider decisions:** peers/suppliers/customers (a dataset project, not a
feed), a macro-indicator calendar (CPI / rate path / fiscal), and SEC/EDGAR regulatory filings. The
existing disclosures for all three (`news_analyst.md:19`) are correct and stay.

## Acceptance

- Tier A: no prompt layer asserts a capability that is off. Either a sentiment tag renders in the
  catalyst line on Alpha, or the word "sentiment tag" appears in **neither**
  `content/agents/news_analyst.md` **nor** `room_prompts.py`. Re-measure the fabricated-provenance
  scan (`sentiment tag` in replies): must be 0.
- Tier A: the expected-vs-actual and second-order-effect bullets are gone, or the data behind them
  is in. No instruction survives that the fact sheet cannot supply.
- Tier A/B: every prompt edit re-measured post-promotion against CR143's baselines — over-budget
  rate, bullet usage, stance emission, truncation, novel-number rate. **A prompt edit whose effect
  is not re-measured is the CR105 Amendment-1 trap**, and this agent's baselines are all recorded
  above.
- Tier B: no headline older than the floor ever renders under a "LIVE … as of this call" header.
  Re-run the age parse over a fresh epoch: `>7d` must be 0, or the run must be `UNAVAILABLE`.
- Tier B: `test_prompt_data_parity.py` green and non-vacuous after any `NewsItem` / `LiveHeadline`
  field is added.
- Tier C: no uncached `.earnings_dates` call on the convene path; the surprise line carries
  `field_state` provenance.
- **The lane number is the one that decides whether this worked.** Cross-lane citation for
  news_analyst falls materially from **18/18**, re-measured on ≥30 convenes under the rule stated
  in §1. That fix lives in CR145 Tier C; this CR owns the measurement and the target.
- `pytest backend/tests/unit/ -q` green throughout.

## Rejected, with the evidence that killed each

1. **"Raise `DEFAULT_HEADLINE_LIMIT` 3 → 6–8"** — the data-sufficiency review's lead recommendation.
   **Rejected on a live measurement.** yfinance returns 10 for most tickers, so it is cheap — but
   it does not buy relevance, which is the actual defect (§4). Probed 2026-08-08 across 8 corpus
   tickers: the first 3 headlines are **13/24 (54%)** on-ticker, the next 7 are **20/49 (41%)**.
   The marginal headline is *less* relevant, because `_merge_headlines` ranks by recency and
   nothing else. More rows would also land in 11 other agents' prompts. A relevance filter, or
   nothing.
2. **"The news feed has the social feed's staleness problem"** — the hypothesis this CR was told to
   check hard. **Rejected:** 5-minute TTL, median publication age 2.0 h, 91% under a day. The 20.18-day
   mean is one microcap and coincidentally equals CR148's social mean; anyone quoting it without the
   median will draw the wrong conclusion. The narrow real defect (no recency floor) is Tier B.
3. **"The news/social feed is dead on Alpha"** — **rejected**, and the correction is finer than the
   one handed over: news is live via **Yahoo**, not Adanos. Adanos is the Social analyst's Reddit
   supplier. Only Alpha Vantage's sentiment tagging is dark.
4. **Blind review failure mode 2, "hallucinated ticker-specific signal"** — **killed**: 0/207
   numeric tokens absent from the prompt.
5. **Blind review failure mode 1, "stance conflict output"** — **killed as a compliance failure**:
   18/18 stances parse. The contradiction is real (*"Do not predict up or down"* vs a forced
   `for|against|neutral`) and the model escapes to **neutral in 13/18 (72%)** — second-highest of
   11 prose agents, against 33% for market_analyst and 6% for the Trader. That is a **signal about
   the contradiction, not a defect to fix here**: the stance is load-bearing (it reaches the
   transcript, the `agent_done` event and the client comb, `room_runner.py:3560-3580`), so it
   cannot simply be deleted, and the reconciliation is DEF236's.
6. **`_LEVEL_PATTERNS` exposure from quoted price targets** — **rejected on the parser check**:
   8/18 turns state a `target`, 0 an `entry`, 0 a `stop`; geometry annotation trips 0/18. The
   DEF235/DEF237 risk class does not reach this agent.
7. **The 32-char `HEADLINE` nulling as a News-specific defect** — **rejected as News-specific.**
   Real and user-visible: **3/18** News headlines are silently nulled by
   `parse_stance_envelope`'s *"Nulled, never cut"* (`room_runner.py:1829-1832`), and all three are
   valuation phrasings. But it is not this agent's: neutral_debator 33%, conservative_debator 22%,
   news_analyst and bull_researcher 17%. Cross-agent, already recorded by CR148, belongs with
   DEF236.
8. **The blind review's CUT list** (portfolio snapshot, risk caps, duplicated mandate) — not
   rejected on merit, **owned by CR145 Tier C**. Measured harm here is the §1 table, which is the
   argument for that tier, not for a per-agent scissors job.
9. **The data-sufficiency review's "~85–90% / ~50–60% accuracy" scores** — **rejected as
   evidence.** No method, not reproducible. Same call CR148 made.

## Notes and what could not be verified

- **The real sample is stale.** `real_samples/news_analyst.prompt.txt` is byte-identical to corpus
  turn 0 (AMD 13:32) and is one of only **2/18** news prompts predating DEF227/DEF228 — it renders
  `Recent range:` and `trend: trading`, which HEAD cannot emit. Both external reviews quote that
  block. The same epoch caveat CR146 found; re-capture before quoting prompt line numbers again.
  Prompt size: the stub's 9,798 chars is the **first** turn; the corpus range is 9,331–9,854,
  median 9,630.
- **Could not verify:** whether the client strips Markdown from the `HEADLINE` field — LITE 19:28
  emitted `**4 days** to earnings`, which the parser accepts intact at 22 chars; whether the
  353-day SNOA feed is a rate or an accident (n=1 of 18; needs ≥30 convenes across thin names);
  what Alpha Vantage's tags are actually worth, since with no key they cannot be probed; whether
  the hand-maintained `_FOMC_DECISION_DATES` list (`room_runner.py:266-269`, populated through
  2026-12-09, no alarm when it runs out) has ever gone stale in production.
- **Already filed, not re-opened:** DEF235 (fixed), DEF237 (open) — neither has exposure on this
  agent per §"What is working". Cross-cutting and owned by CR145: DEF236, `LearningStyle.QUICK`'s
  *"tabular"* against *"no tables"*, and the per-agent fact sheet.
- Tier A is free, prompt-only and can ship alone; it is also where the one fabrication in the
  corpus comes from. Tier B's recency floor is small and independent; its summary and watchlist
  halves should wait on CR145 Tier C so they do not widen the shared sheet. Tier C is the only
  tier that costs a fetch.
