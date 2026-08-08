# External review — news_analyst (data sufficiency + supplier check)

> Reviewer: `kimi-for-coding` · Kimi track K session.
> Corpus reviewed: `docs/forward_planning/CR143_agent_prompt_audit/real_samples/news_analyst.prompt.txt`
> (AMD run, fact sheet as of 2026-08-07) and `real_samples/news_analyst.reply.txt`.
> Unlike `external_review/room/news_analyst.md` (blind prompt-coherence audit, AAPL-variant
> prompt, no code access), this review had codebase access. Every availability claim below
> is verified against the actual fetch path — these are **findings, not hypotheses**.

## 1. Question

Does the News Analyst have enough data in the fact sheet to do its job to
~95% accuracy?

## 2. Answer

**Mostly yes for a thin signal-vs-noise read, no for the role as written.**

The job as the turn-level instructions scope it — lead with the highest-signal
headline, tag noise vs signal, anchor to the earnings/FOMC dates — is executable:
the data block carries 3 real headlines (prompt line 101), a live earnings date +
consensus EPS (line 109), and a real FOMC countdown (line 101). But only **1 of the
3 headlines is on-ticker** (the Taalas M&A item); the other two are macro-futures
and unrelated-earnings wire filler. The analyst's news surface is one headline deep.

The role as written demands more than that: of the five "Output style" requirements
(prompt lines 19–23), three are unproducible with the supplied data — expected-vs-actual
(line 21), second-order effects (line 22), and the role guidance's macro weighting
(line 71) and holdings+watchlist filtering (line 68, watchlist half).

Estimated accuracy on the scoped deliverable: **~85–90%** (limited by headline
depth/relevance, not honesty). Against the full role as written: **~50–60%**.

## 3. Data gaps (from the prompt alone)

| # | Gap | Impact |
|---|---|---|
| 1 | Headline depth: 3 headlines, 1 on-ticker | "Lead with the highest-signal item" (line 20) is trivially satisfiable but shallow; "3 items max" (line 23) and "quality over quantity" ring hollow when the pool is one AMD story plus wire filler. |
| 2 | No expected-vs-actual data | The style example "consensus was +2.1%, actual was +4.3% — beat" (line 21) is unproducible: only a *forward* EPS estimate ($1.92529, line 109) exists; no reported actual, no surprise history. |
| 3 | No peer/supplier/customer mapping | "Identify second-order effects (peers, suppliers, customers)" (line 22) has zero entity data behind it. Sector/industry strings (line 107) are the only hook. |
| 4 | No macro substance to weight | Role guidance says "Weight macro structural news (Fed cycle, fiscal policy) higher than single events" (line 71); the entire macro dataset is one FOMC countdown (line 101). No Fed path, CPI, or fiscal item. |
| 5 | No watchlist | "Filter headlines to user's holdings + watchlist relevance" (line 68): holdings ARE in the prompt (lines 76–80), the watchlist is not. Half-executable. |
| 6 | No per-headline sentiment tags in practice | Inputs claim an Alpha Vantage sentiment-scored feed "where configured" (lines 12–13); no headline in the block carries a tag. |
| 7 | Headline titles only, no bodies/summaries | Signal-vs-noise discrimination (line 19) runs on ~15 words per story. |
| 8 | No regulatory-filings feed | Honestly disclosed (line 15); listed for completeness — the role (line 8) names regulatory actions as core domain. |

Role-vs-input contradiction worth naming: the guidance ranks macro structural news
highest (line 71) while the Inputs section simultaneously discloses no macro calendar
exists (line 15) — the agent is told to prioritise a category containing exactly one
forward date.

## 4. Supplier check — what the codebase can actually deliver

Room news path: `resolve_news_feed()` (`backend/app/services/news_context.py:273-300`),
pre-priced per run in `start_run` (`room_runner.py:2455-2531`, CR090 charge==render),
threaded into `_profile_for_ticker` (`room_runner.py:567-587`): top headline →
`profile["catalyst"]`, all → `profile["news_headlines"]` (`room_runner.py:584-586`),
rendered by `_catalyst_line` (`room_prompts.py:874-883`). The block is the SHARED fact
sheet — all 12 agents see the same headlines (`room_prompts.py:379`); the 1-on-1 path
has a News-Analyst-only block (`build_news_context_block`, `news_context.py:342-369`).
Role guidance text: `overlay_generator._news_block` (`backend/app/agents/overlay_generator.py:292-310`);
the macro-weighting line is conditional on `Path.LONG_HORIZON` (`overlay_generator.py:306-307`).

| # | Item | Verdict | Evidence / effort |
|---|---|---|---|
| 1 | More headlines | **AVAILABLE, NOT WIRED — trivially** | Hard cap `DEFAULT_HEADLINE_LIMIT = 3` (`news_context.py:46`); both sources fetch and merge at that limit (`news_context.py:237-258, 303-318`). yfinance returns more than 3; raising the constant costs nothing extra on the Yahoo leg (same call, bigger slice, 5-min cache already in `market_data.py:453-463`). No relevance ranking exists — recency only (`news_context.py:317`). |
| 6 | Per-headline sentiment tags | **ALREADY WIRED, DARK ON ALPHA** | Full Alpha Vantage NEWS_SENTIMENT source: fetch + per-ticker label mapping (`news_context.py:144-229`), 30-min TTL cache (`news_context.py:48`), merged dedup-preferring-AV (`news_context.py:19-21, 303-318`), rendered by `format_headline` (`news_context.py:321-328`). On/off switch is `settings.alpha_vantage_api_key` (`news_context.py:250`); compose forwards it (`docker-compose.yml:258`) but `infra/alpha.env:84` has `# ALPHA_VANTAGE_API_KEY=` commented out — hence no tags in the sample prompt. Config decision, not code work. |
| 7 | Article summaries | **AVAILABLE, NOT WIRED** | `YfinanceProvider.news` parses each article's `content` dict but keeps only title/link/publisher/published_at (`market_data.py:585-603`); Yahoo's `summary` field is on the payload and discarded. `NewsItem` (`market_data.py:83-89`) + `LiveHeadline` (`news_context.py:106-115`) would each need one field. |
| 2 | Expected vs actual | **AVAILABLE, NOT WIRED** | yfinance `.earnings_dates` exposes historical EPS Estimate / Reported EPS / Surprise(%) — not referenced anywhere in `backend/` (grep: zero hits). Today only `.calendar`'s forward "Earnings Average" is read (`market_data.py:614, 643, 656`). Would ride the existing 6h earnings cache (`market_data.py:406`). |
| 5 | Watchlist | **AVAILABLE, NOT WIRED** | `WatchlistStore.list_for_user` (`backend/app/services/watchlist_store.py:32-39`), `sim_watchlists` table, router mounted (`backend/app/main.py:321`) — never read by `room_runner.py` or `room_prompts.py` (grep: zero hits). Holdings side already injected via the CR055 portfolio snapshot (`room_runner.py:295-297`). |
| 4 | Macro data | **NOT AVAILABLE without a new provider** | Only the hardcoded `_FOMC_DECISION_DATES` list (`room_runner.py:266-269`) → `_forward_catalyst_text` (`room_runner.py:272-282`). CR038 already deleted the synthetic sector-earnings half (`room_runner.py:273-276`). No CPI/rate-path/fiscal feed exists in the stack. |
| 3 | Peers/suppliers/customers | **NOT AVAILABLE as-is; DIY-able at best** | Same verdict as the fundamentals audit: no peer data in yfinance beyond the sector/industry strings we already fetch (rendered `room_prompts.py:839-846`). Building a peer map is a dataset project, not a feed. |
| 8 | Regulatory filings | **NOT AVAILABLE without a new provider** | No SEC/EDGAR integration anywhere. The disclosure (prompt line 15; base prompt `content/agents/news_analyst.md:19`) stays correct. |

## 5. Structural caveats before wiring #1 / #2 / #6 / #7

1. **The news block is shared by all 12 agents.** Every headline/summary/sentiment
   field added lands in 11 other prompts too, and the fundamentals reply sample already
   showed cross-domain borrowing. Enlarging this block raises scope-bleed surface
   unless paired with per-agent fact-sheet views.
2. **Mock/degraded path has no news at all.** `MockWalkProvider.news` → None
   (`market_data.py:300-301`), `YahooQuoteProvider.news` → None (`market_data.py:379-380`);
   a Yahoo outage flips `field_state["news"]` to UNAVAILABLE and the Room renders the
   honest synthetic-catalyst disclosure (`room_prompts.py:626-630`). More headline
   slots = more conspicuous absence when degraded.
3. **Alpha Vantage is metered.** The 30-min cache (`news_context.py:48`) exists, but
   `resolve_news_feed` probes availability even for non-entitled users (noted in its
   own docstring, `news_context.py:289-294`) — enabling the key makes quota a
   entitlement-gating question, per the DEF063 warning at `docker-compose.yml:256-257`.
4. **`.earnings_dates` adds one yfinance call per run.** Must ride the 6h earnings
   cache from day one — the news/fundamentals pattern (zero caching on fundamentals)
   is the anti-precedent.
5. **The FOMC list is hand-maintained** (`room_runner.py:263-265`): needs a manual
   refresh once the Fed publishes the 2027 schedule; it silently goes stale, no alarm.

## 6. Recommended slice (if this becomes a CR)

Cheap, high-yield, no new provider:

1. Raise `DEFAULT_HEADLINE_LIMIT` (3 → 6–8) and render titles + summaries for the
   News Analyst — ideally via a per-agent news block rather than the shared sheet.
2. Wire `.earnings_dates` (last 4 quarters: estimate vs actual vs surprise) onto the
   existing 6h earnings cache; render one "last reported: est $X, actual $Y — beat/miss"
   line. Makes the role's own style example producible.
3. Decide Alpha Vantage: populate `ALPHA_VANTAGE_API_KEY` on Alpha (sentiment tags go
   live, zero code) or trim the "where configured" Inputs claim from the base prompt.
4. Inject the watchlist tickers (one line from `WatchlistStore.list_for_user`) or
   delete "watchlist" from the role guidance (`overlay_generator.py:296`).
5. Either supply macro data (new provider — separate decision) or soften the
   "weight macro structural news higher" guidance to match the FOMC-only reality.

Peers and filings stay out of scope — new-provider decisions.

## 7. Relationship to the blind review (`../news_analyst.md`)

The blind review audited an AAPL-variant prompt; same template, different ticker and
portfolio. Against its hypotheses:

- **CONFIRMED — UNFOLLOWABLE-B (expected vs actual).** Verified at the data layer:
  only a forward EPS estimate is wired (`market_data.py:643,656`); no actuals/surprise
  anywhere. Its remedy stands; `.earnings_dates` makes it fixable cheaply (§6.2).
- **CONFIRMED — UNFOLLOWABLE-C (second-order effects).** No peer/supplier/customer
  data exists in the stack; not a wiring gap, a provider gap.
- **CONFIRMED — UNFOLLOWABLE-D (macro weighting).** The FOMC countdown
  (`room_runner.py:266-282`) is the entire macro dataset, exactly as it suspected.
- **HALF-CONFIRMED — UNFOLLOWABLE-A (holdings/watchlist filter).** It said filtering
  was impossible because AAPL wasn't held. Refinement: holdings ARE injected every run
  (CR055 portfolio snapshot), so holdings-relevance filtering is executable; the
  watchlist half is the genuine gap — the store exists and is never read.
- **CONFIRMED live — failure mode 3 (format).** The real reply dropped the mandated
  bullets and filled HEADLINE with a topic phrase, not "the single number or fact"
  (§8). Its contradiction-A/C analysis (thesis+bullets vs 2–3 sentences vs 3 items
  max) correctly predicted this.
- **KILLED — failure mode 2 (hallucinated ticker-specific signal).** On the real AMD
  run the model invented nothing; every number traces to the block (§8). The grounding
  directive held where the blind review expected it to break.
- **KILLED — failure mode 1 (stance conflict output).** The model escaped via
  `STANCE: neutral | CONVICTION: low`, consistent with its own cautious body — the
  contradiction exists in the prompt but did not produce a compliance failure here.
- **COULD NOT SEE (its structural limit):** the 3-headline hard cap
  (`news_context.py:46`), sentiment tags wired-but-dark (`infra/alpha.env:84`),
  discarded Yahoo summaries, the unwired `.earnings_dates` and watchlist, and the
  hand-maintained FOMC list. Its CUT list (portfolio/mandate blocks) is
  prompt-coherence territory this review does not re-assess.

## 8. Reply-sample verification (`real_samples/news_analyst.reply.txt`)

Checked line-by-line against the data block (prompt lines 93–109).

**Numerically clean.** Every figure is in the block: P/E **126.4** (line 94),
EV/EBITDA **82.6x** (line 106), **$1.92529** and **88 days** (line 109), RSI **49**
(line 97), volume in-line (line 99). One distortion, not a fabrication: "15-minute
buzz" repurposes the Taalas headline's "15m ago" publication recency (line 101) into
a buzz-duration claim. Zero training-memory numbers. **GROUNDED on facts.**

**Defects:**

1. **Format violation — predicted by the blind review.** Mandate: "lead with a
   one-sentence thesis, then short bullet points" (line 122). The reply is three
   prose sentences, **no bullets**. (It does satisfy "Write 2–3 sentences" — the two
   instructions are in direct tension, blind-review contradiction A/C.) Bold usage,
   no headings, stance line shape and placement, no "As the X" preface: all compliant.
   HEADLINE field "M&A signal vs. valuation gap" is 28 chars (≤32 ✓) but is a topic
   phrase, not "the single number or fact that carries your view" (line 128).
2. **Scope bleed — same failure mode as the fundamentals reply.** Sentence 2 is a
   valuation argument (P/E, EV/EBITDA "requires precise execution to justify" vs
   consensus EPS) — Fundamentals Analyst's lens. Sentence 3 leads with RSI/volume
   ("no immediate price pressure") — Market Analyst's lens, skirting the "comment on
   chart patterns" bar (line 29). Only sentence 1 is actually news. The turn
   instruction "Stay strictly inside your OWN domain… that discipline is what keeps
   the four analyst contributions from overlapping" (line 120) did not hold: 2 of 3
   sentences borrow other analysts' fields.
3. **Mild unlabeled inference.** "Requires precise execution to justify" (no execution
   data supplied) and "no immediate price pressure" (inference from RSI 49 + in-line
   volume — defensible, but an inference presented as reportorial fact).

**Stance-evidence tension: none.** `STANCE: neutral | CONVICTION: low` matches a body
arguing "the catalyst is noise until earnings prove the strategy" — and neutral is
the compliant escape from the DO-NOT-predict-direction (line 27) vs forced-stance
(line 126) contradiction. Header and body agree.

**Net:** GROUNDED numerically — no hallucination. Non-compliant on format (missing
bullets, off-spec HEADLINE content) and undisciplined on domain (valuation +
technicals dominate a news lens). The shared fact sheet supplies the temptation;
the role firewall did not hold.
