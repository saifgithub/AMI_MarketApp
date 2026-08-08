# External review — social_media_analyst (data sufficiency + supplier check)

> Reviewer: `kimi-for-coding` · Kimi track K session.
> Corpus reviewed: `docs/forward_planning/CR143_agent_prompt_audit/real_samples/social_media_analyst.prompt.txt` (AMD, 2026-08-07) + `real_samples/social_media_analyst.reply.txt`.
> Unlike `external_review/room/social_media_analyst.md` (blind prompt-coherence audit,
> run against an older AAPL synthetic-scaffolding sample),
> this review had codebase access. Every availability claim below is verified against
> the actual fetch path — these are **findings, not hypotheses**.
> Note: the blind review's sample had **no live social data**; this sample has the full
> LIVE Adanos block. The two reviews are not looking at the same prompt generation.

## 1. Question

Does the Social Media Analyst have enough data in the fact sheet to do its job to
~95% accuracy?

## 2. Answer

**Yes for the job as scoped in the prompt, no for the full early-warning role.**

The prompt names the agent's Inputs explicitly (line 12): "mention volume, buzz score,
bullish/bearish split, most-active communities." In this LIVE sample all four are
present (lines 101–104): **637 mentions over 7d, trend: rising; buzz 73/100; bullish
32% / bearish 19%; r/wallstreetbets, r/ValueInvesting, r/stocks**. DEF096 is visibly
fixed — `_social_detail_lines()` (`room_prompts.py:763-784`) now renders the mention,
pattern, and community detail that the Room used to drop.

Estimated accuracy on the scoped deliverable (a 2–3-sentence sentiment read over
live aggregates): **~85–90%**.

Against the full role — "early-warning system for euphoria and panic," meme-cycle
phase, organic-vs-coordinated distinction, contrarian extremes (lines 8, 21–22) —
the data caps out at **~50–60%**: a single snapshot with no baseline, no history,
no intensity or coordination dimension cannot support any of those calls.

## 3. Data gaps (from the prompt alone)

| # | Gap | Impact |
|---|---|---|
| 1 | No sentiment baseline/history | "Surface contrarian signals (extreme greed → reversion risk)" (line 22) requires knowing what extreme *is*. Buzz 73/100 with no percentile, no prior-period value, and "trend: rising" with no magnitude makes the extremes call ungrounded. "Meme cycles" (line 8) needs a series; one snapshot is given. |
| 2 | No engagement/intensity data | Mention count only. No upvotes, unique posts, or subreddit breadth — the difference between 637 mentions from 40 posts and 637 from 400 posts IS the conviction signal. |
| 3 | No per-community split | Communities are named (line 104) with no per-community sentiment. WSB-vs-ValueInvesting divergence is exactly the "fractured" read this agent exists to make. |
| 4 | No organic-vs-coordinated signal | Role demands the distinction (line 21, "as a conceptual framing"). No account-level, velocity, or coordination data exists in the prompt. |
| 5 | Neutral share unstated | 32% bull + 19% bear = 51% classified; the 49% neutral residue — the actual story here — is left for the model to infer. |
| 6 | Tone vs score tension | "Retail sentiment: bullish (+0.04 …)" (line 101): a near-zero aggregate score under a "bullish" tone label, with no reconciliation guidance. |
| 7 | Promised excerpts never arrive | Inputs text (line 13): "you may see real (anonymized-by-omission) excerpts as context." The Room prompt contains none — role guidance contradicts the available inputs. |
| 8 | No mention-trend magnitude | "trend: rising" (line 102) carries no % delta. The agent cannot say how fast. |
| 9 | Cross-platform sentiment | Disclosed honestly as nonexistent (line 12). Not a defect — a scope limit. |

## 4. Supplier check — what the codebase can actually deliver

Fetch path: `fetch_live_sentiment(ticker)` → `_AdanosSource.fetch` —
`backend/app/services/social_context.py:121-185` (Adanos
`GET /reddit/stocks/v1/stock/{ticker}`, `social_context.py:38,136-139`).
Room overlay: `room_runner.py:605-611` (five formatted fields only).
Render: `room_prompts.py:725-733` + `_social_detail_lines` (`room_prompts.py:763-784`).
Evidence for payload contents: captured real Adanos response at
`backend/tests/unit/test_social_context.py:71-107`.

| # | Item | Verdict | Evidence / effort |
|---|---|---|---|
| 2 | Engagement metrics (total_upvotes, unique_posts, subreddit_count, positive/negative/neutral counts) | **FETCHED, DISCARDED** | All present in the real payload (`test_social_context.py:78-83`: `total_upvotes: 38369`, `unique_posts: 410`, `subreddit_count: 41`, `neutral_count: 1151`). `_to_sentiment` (`social_context.py:202-221`) reads none of them. Extend the `SocialSentiment` NamedTuple + one render line each. Zero extra quota cost — same API call. |
| 3 | Per-community sentiment/buzz/mentions | **FETCHED, DISCARDED** | Each `top_subreddits` entry carries `mentions`, `sentiment_score`, `buzz_score` (`test_social_context.py:88-93` — WSB −0.053 vs ValueInvesting +0.103 in the captured sample). `_to_sentiment` keeps only the subreddit **name** (`social_context.py:204-206`). The divergence signal is in hand and thrown away. Same one-call cost. |
| 5 | Neutral share | **FETCHED, DISCARDED** | `neutral_count` in payload (`test_social_context.py:80`); `bullish_pct`/`bearish_pct` already read (`social_context.py:215-216`) — neutral % is one subtraction even without the count. |
| 7 | Sample snippets in the Room | **FETCHED, DELIBERATELY NOT SURFACED** | `sample_snippets` extracted (`social_context.py:207-209`) and rendered only on the 1-on-1 path (`build_social_context_block`, `social_context.py:317-343`); the Room profile structurally never carries them (module docstring `social_context.py:14-20` — the profile also feeds the scripted non-LLM fallback shown to users; overlay list at `room_runner.py:605-611` confirms). The line-13 "you may see real excerpts" promise is true only of 1-on-1. Surfacing them in the Room is a policy decision, not a fetch problem. |
| 6 | Tone/score reconciliation | **ALREADY WIRED, MISLABELLED BY CONSTRUCTION** | Tone is derived from the pct gap (`format_sentiment_tone`, `social_context.py:291-296`: bullish if bull > bear + 5); the score is the raw aggregate (`format_sentiment_score`, `social_context.py:299-300`). Two different derivations rendered side by side with no explanation — "bullish (+0.04)" is the expected output of the current code, not a fetch bug. Fix is a render-rule change (e.g., state the pct-gap basis), not new data. |
| 1 | Sentiment baseline/history | **NOT AVAILABLE as-is; DIY-able** | Adanos returns point-in-time only (single endpoint, no history param, `social_context.py:136-139`). The durable cache keeps exactly one row per ticker and overwrites it (`_cache_write`, `social_context.py:91-112`) — no series is accumulated. An append-only history table would build a baseline from the existing provider over time; that's a schema change, not a new feed. |
| 8 | Mention-trend magnitude | **NOT AVAILABLE as-is** | Payload carries absolute `mentions` + a `trend` string, no delta (`test_social_context.py:76,84`). Computable only once #1 lands. The old fake "up 40% week-over-week" string was deliberately removed (`room_runner.py:435-440`). |
| 4 | Organic-vs-coordinated signal | **NOT AVAILABLE** | No such dimension anywhere in the Adanos payload (`test_social_context.py:71-107`). Needs a new provider. The line-21 demand is unsatisfiable from any wired source. |
| — | Influencer dimension | **NOT AVAILABLE** | The synthetic profile carries an `influencer_take` field (`room_runner.py:446`), and the non-live disclosure header still says "sentiment/mention/influencer fields" (`room_prompts.py:650`); the live path overwrites `influencer_take` with the community read (`room_runner.py:610`). Adanos has no influencer data. |

## 5. Structural caveats

1. **The 30-day cache makes "LIVE as of this call" a lie of up to 30 days.**
   Durable TTL is `social_cache_ttl_days = 30` (`config.py:210`); the header claims
   "LIVE, real Reddit aggregate data **as of this call**" (`room_prompts.py:634-637`).
   Sentiment is the most perishable field on the sheet — a 30-day-old "trend: rising"
   is materially misleading, worse than the quotes (60s) and news (5min) TTLs in
   `market_data.py`. The module docstring still says "24h TTL"
   (`social_context.py:8-9`) — three-way drift between docstring, config, and prompt
   claim. Quota pressure is real (250 calls/month free tier, `social_context.py:8-12`),
   but 30 days is a quota-driven decision that the prompt's freshness language does
   not disclose.
2. **Surfacing #2/#3 is free on quota** — same Adanos call, wider read. No
   rate-limit concern. #1 (history) adds storage only, not calls.
3. **WITHHELD_PAID path stays synthetic-honest.** Non-entitled turns get the
   scaffolding plus a paywall disclosure (`room_prompts.py:639-647`); the blind
   review's "no social numbers" critique still applies verbatim to those runs.
4. **Per-field provenance works here.** `field_state["social"]`
   (`room_runner.py:612`) gates every social render; gaps degrade to an honest
   synthetic block, not silence.

## 6. Recommended slice (if this becomes a CR)

Cheap, high-yield, no new provider, no extra quota:

1. Extend `SocialSentiment` + `_to_sentiment` to carry per-subreddit
   sentiment/buzz/mentions, neutral share, `total_upvotes`, `unique_posts`,
   `subreddit_count`; render under the existing `Retail sentiment:` detail block.
   Directly powers the divergence ("fractured") and intensity reads the role names.
2. Fix the freshness claim: either drop `social_cache_ttl_days` toward 24–72h or
   render the cache age ("as of <fetched_at>") instead of "as of this call."
   Align the `social_context.py` docstring in the same change.
3. Reconcile tone vs score at render (state the pct-gap basis) or stop rendering
   one of the two.
4. Decide the excerpts question for the Room: either inject snippets LLM-only
   (they're already fetched) or delete the "you may see real excerpts" clause from
   the base prompt's Inputs for the Room path.

Organic/coordinated detection and a real sentiment history are separate decisions —
new provider and schema change respectively.

## 7. Relationship to the blind review (`../social_media_analyst.md`)

The blind review ran against an **older AAPL sample with synthetic scaffolding**;
this sample is LIVE. Its hypotheses resolve as follows:

- **"Numbers demand vs. absent social data" (its core contradiction) — KILLED for
  the live path.** All four Inputs the job names are injected here (DEF096 fixed
  since its sample was captured). **Still VALID** for WITHHELD_PAID / UNAVAILABLE /
  synthetic runs (`room_prompts.py:639-651` renders scaffolding under those states).
- **Failure mode "hallucinated social metrics" — KILLED in this sample.** The reply
  invented zero numbers (§8).
- **Failure mode "lane drift into fundamentals" — CONFIRMED live.** The reply cites
  P/E 126.4 (its line 4) despite "Sentiment is your lane" — empirically supports
  the blind review's CUT recommendation to strip non-social fields from this prompt.
- **"Extreme-signal framing vs. moderate data" — CONFIRMED and generalized.** Even
  with live data there is no baseline for "extreme"; the reply stretched to
  "extreme retail enthusiasm" anyway. The gap is structural (§3 #1), not
  synthetic-path-only as the blind review assumed.
- **"Use other analysts' context vs. transcript empty" contradiction — CONFIRMED
  as prompt text.** Both lines survive verbatim in the real sample (line 14 vs
  line 119). The turn tail (`room_prompts.py:437-445`) and the base Inputs text
  were written against different phases and never reconciled for the concurrent
  ANALYSTS phase.
- **CUT list (mandate/portfolio bloat) — not re-adjudicated** (prompt-coherence
  scope, not data-sufficiency scope), but confirmed present: the real AMD prompt
  carries the same duplicated mandate block and the full simulated-portfolio
  section (lines 42–79) ahead of a first-speaking sentiment agent.

## 8. Reply-sample verification (`real_samples/social_media_analyst.reply.txt`)

Checked line-by-line against the data block.

**Numerically clean.** Every figure is in the block: **73/100** (line 103), **32%**
and **19%** (line 103), **7 days** (line 102, "over 7d"), **r/wallstreetbets**
(line 104), **P/E 126.4** (line 93). Zero hallucinated numbers. The grounding
directive held on facts.

**Four non-numeric defects:**

1. **Scope bleed — blind-review failure mode confirmed live.** Reply line 4:
   "High valuation metrics (**P/E 126.4**) combined with extreme retail enthusiasm
   signal reversion risk" — the valuation half is the Fundamentals Analyst's barred
   domain (prompt line 38: "For everything else (chart, fundamentals, news, trade),
   redirect"). The data block carries P/E for another agent; the model used it anyway.
2. **Unlabeled inference — coordination.** Reply line 3: "suggests potential
   coordination or meme-driven volatility" from "rising mentions in r/wallstreetbets."
   Zero supporting data (§3 #4); the role itself permits this only "as a conceptual
   framing, not a claim" (line 21). The reply states it as a finding.
3. **Unlabeled inference — "extreme".** "Extreme retail enthusiasm" over buzz
   73/100 with a near-zero sentiment score (+0.04) and a 32/19 split. "Strong" was
   defensible; "extreme" is a stretch with no baseline in the data (§3 #1).
4. **Format deviation — no bullets.** The prompt mandates "a one-sentence thesis,
   then short bullet points for supporting evidence" (line 121). Reply lines 2–4
   are three plain sentences; no bullet markers. Stance-line shape, single
   occurrence, HEADLINE "73 buzz" (7 chars ≤ 32), 3-sentence length, and bold usage
   all comply.

**Stance-evidence tension: mild, acceptable.** `STANCE: neutral | CONVICTION: medium`
over a body that reads cautionary (fractured interest, volatility, reversion risk).
Defensible here — the underlying data genuinely is mixed (buzz 73 vs score +0.04 vs
49% unclassified), so "neutral" is arguably the *correct* read of a block the tone
label calls "bullish." The tension is with the data's own labels, not internally
incoherent.

**Net:** the reply is GROUNDED on facts — no hallucinated numbers, no
training-memory leakage. It is not bound to its lane (one fundamentals citation),
overclaims coordination and extremity the data cannot support, and misses the
mandated bullet format. Three of the four defects trace back to prompt-side causes
identified above: other-lane numbers left in the block, a coordination demand with
no data dimension, and an extremes demand with no baseline.
