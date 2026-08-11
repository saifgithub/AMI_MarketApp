<!--
R68-BATCH9.architect.md — architect submission lane. State derives from round numbers here vs
R68-BATCH9.auditor.md.
GATE: none was used while building. Batch 9 of the CR143 prompt + data-feed remediation programme
(one handshake PER BATCH, Saiful 2026-08-11).
-->

# R68-BATCH9 — audit lane (CR148 A + B · CR147 B.1 · the DEF063 residue)

**SHA:** `3e08d23e`, **plus `e53b714a`** (DEF260 — see below). Both on `main`, pushed to origin.
**SCOPE:** chunk — the two paid feeds, plus one defect the promotion itself uncovered. CR147 and
CR148 both go `in_progress`; **DEF260 closes**.
**PROMOTED:** `alpha-2026-08-11-8`, verified in-container (see "Live verification" below).
**depends-on:** R68-BATCH4 (`6b5fe052`, awaiting) — Batch 4 wired the Adanos secondary key into
config and compose, and this batch is what makes the fetch path actually send it.

**Item:** the News and Social Analysts' live feeds. Prompt bytes change ⇒ **CR142 Tier A**.

**Unblocked by a Saiful decision taken this session** (`AskUserQuestion`, 2026-08-11): the Adanos
cache TTL, **30 days → 7**. That was the only thing holding this batch; CR148 Tier A and CR147 B.1
never needed it and could have shipped earlier.

---

## The shape both feeds share

Neither analyst is short of a provider. Both are short of **the half of the payload we already pay
for**, and short of an **honest freshness label** on the half we render. That is why one batch
covers two agents.

## CR148 Tier A — six dimensions fetched and discarded

`_to_sentiment` kept 8 of ~15 fields. Verified field-by-field against the real captured Adanos
response, not against a shape we assumed.

The expensive one is the **per-community split**. 12 of 18 turns named a subreddit and **9 of 18
attached a sentiment quantity, tone or trend to a named one** — against the agent's own prohibition,
*"You DO NOT … Speak on behalf of any specific community"*. CR143's number-provenance metric scores
this agent **0.0% novel numbers**, joint-best of eleven prose agents, because every *number* is
real; it is the **attribution** that is invented, and no numeric-provenance metric can see that.
Supplying the split leaves the invention nothing to do.

Two details that are decisions rather than transcription:

- **`subreddit_count` is the payload's own (41), never `len(top_subreddits)`.** The latter would
  have turned a truncation into a full-coverage claim — *"3 of 3 subreddits"* — which is worse than
  the silence it replaced.
- **The name list and the stat list are sliced by one shared `_TOP_SUBREDDIT_LIMIT`.** A stat block
  describing different communities than the *"most active in"* line above it would be worse than
  neither, and two inline `[:3]`s is how that drift starts.

**The neutral residue** is the same shape as the attribution defect: it is the **majority class**
(42–71% of the sample, median 52.5%) and 2 of 18 turns noticed it existed. AAPL renders as 22%
bullish / 20% bearish, and the 58% saying neither was unreachable.

### Sample size — and why the threshold is derived

`_MIN_MENTIONS_FOR_A_PERCENTAGE = 100` is **not chosen**. This module's own
`format_sentiment_tone` calls a tone on a **5-point** bull/bear gap; the standard error of a
proportion at p≈0.5 is **exactly 5.0pp when n = 100**. Below that, the gap the classifier uses to
decide *"bullish"* sits inside one standard error of its own sample. The test asserts both halves of
that derivation rather than the constant.

Measured: mention counts ran **10 → 3,990**, 5 of 18 turns under 52, and `format_pattern` rendered
n=10 in the byte-identical shape it uses at n=3,990.

The caveat **restates the percentages as the post counts they are** (*"~3 post(s) against ~1"*)
instead of instructing the model to be careful. A prompt line telling a model to discount a number
is precisely the control **P2** says does not hold — CR038 measured such instructions at ~30%. A
reader cannot round *"3 posts against 1"* up into a market read the way it can round up *"bullish
30% / bearish 10%"*.

## CR148 Tier B — the freshness claim

*"As of this call"* was false for most turns. Measured on live Alpha Postgres 2026-08-08: **175
rows, mean age 20.2 days, 162 of 175 (93%) older than seven days**, with 8 of the 18 epoch turns
reading rows ~21 days stale at the moment of the turn.

- **Free half.** `fetched_at` is an epoch `int` — the same representation as
  `LiveHeadline.published_at`, for the same reason: it survives the JSON cache round-trip and renders
  as a relative age. It is rendered **first** in the social block, because everything under it is
  only as true as its date, and a date printed after the numbers reads as a footnote.
- **The three-way drift** (docstring "24h", config 30d, prompt "this call") is reconciled by pointing
  the docstring **at the setting** instead of restating a number — a fourth copy of the number is how
  the drift happened.
- **Paid half.** TTL **7 days**, Saiful's call. At ~4.3 calls per distinct ticker/month against a
  500-call budget that caps at ~116 distinct tickers/month, against a cache that has accumulated 175
  rows over its entire life.

## The DEF063 residue — and it was worse than the row recorded

Batch 4 added `adanos_api_key_secondary` to `config.py` and forwarded it in `docker-compose.yml`.
**Nothing at fetch time ever sent it.** `headers={"X-API-Key": settings.adanos_api_key}` — primary
only. So `/v1/admin/config-check` reported the key `configured: true` while the **effective quota
stayed at 250**.

That is the DEF063 failure one layer further in: forwarded, and still dark. It is also the
arithmetic the TTL decision was taken against, so it had to become true rather than remain wired.

`_get_with_failover` retries on the secondary, and **only on quota exhaustion** — a 429, or a
`x-ratelimit-remaining-monthly` header at zero. Three refusals are asserted, because each is a way
to burn the reserve budget on something a second key cannot fix:

| condition | behaviour |
|---|---|
| network error on the primary | **no retry** — a second key does not fix a network |
| unparseable `remaining` header | **no retry** — guessing spends the reserve on a bad header |
| no secondary configured | **no retry** — the primary's response is returned as-is |

**No new Defect ID.** DEF063's row already deferred this explicitly (*"would need a small follow-up
(failover or split-quota rotation) to actually use it"*) and CR148 Tier B's row already carries it as
its own *"Latent DEF063-class"* finding. It closes where it was filed.

## CR147 Tier B.1 + A.6 — the news recency floor

Probed live across 8 tickers, yfinance returned 10 articles for 7 of them. **SNOA got 3, and its
newest was 354 days old**, rendered under a header stating the catalyst was real *"as of this call"*.
More headlines was never the fix.

- **`_NEWS_RECENCY_FLOOR_DAYS = 7` is this CR's own acceptance criterion** — *"re-run the age parse
  over a fresh epoch: `>7d` must be 0, or the run must be UNAVAILABLE"* — not a number picked at
  implementation time.
- **It sits in `fetch_live_news`, the one choke point both surfaces pass through.** Filtering in
  `resolve_news_feed` would have left the 1-on-1 `build_news_context_block` rendering the 354-day
  headline under the identical live header. Asserted on the 1-on-1 surface specifically.
- **An item with `published_at == 0` is dropped too.** *"Date unknown"* cannot be certified recent,
  and passing it through is the exact thing the floor exists to stop (CR040).
- **Drops are logged with a kept/dropped count.** If this fires on every ticker the feed is not
  "working with a filter", it is dead — and the count is the only thing that says so before the
  disclosure quietly flips to synthetic.

**The surcharge stops for free, through the existing mechanism.** An UNAVAILABLE feed is not counted
in `n_available`, so `live_data_surcharge` shrinks by itself — no second debit site, no new branch.
Asserted **end-to-end through the real `_resolve_and_charge_feeds`** with a fresh-news run and an
all-stale run against the same user and balance, not by reasoning about the arithmetic.

A.6: the shared header now states *"published within the last 7 days … anything older was dropped,
not shown"* — the claim the filter actually enforces.

## Backward compatibility, deliberately

175 rows are already in Postgres and 13 of them survive the new 7-day cutoff.

- Every CR148 field carries a **default**, so an old payload loads instead of raising.
- **`_cache_read` supplies the ROW's own timestamp** for `fetched_at`, so an old row's age is
  correct even though its payload never stored one. The row is what staleness is judged against, so
  it is what the age must be rendered from.
- `subreddit_stats` persists as **dicts, never bare NamedTuple arrays** — read back positionally, a
  future field reorder would silently transpose mentions and buzz.

## DEF260 — found by promoting this batch, and it made half of Tier B a no-op

Commit `e53b714a`. **This is not a tidy-up; without it CR148 Tier B did not work on Alpha.**

The TTL change was committed, the suite was green, the promotion reported success, every smoke check
passed and `/v1/admin/config-check` was clean — and an in-container read of
`settings.social_cache_ttl_days` returned **30**. `docker-compose.yml` **always sets** the variable,
so `${SOCIAL_CACHE_TTL_DAYS:-30}` is what the container runs and `config.py`'s value is dead code.

**The DEF038/DEF063 family one layer further out.** Those were an *absent* key degrading a feature
silently. This is a *present* key carrying a **stale second copy of the number** — and the existing
parity guard could not see it, because both of its directions ask whether a field is **reachable**
and neither asks whether the value that arrives is the one the code declares. It is the worse
failure mode of the two: a dark feature at least looks suspicious when you go looking, whereas here
the setting reads `configured: true`, the value is present, and it is simply wrong.

**Measured, not estimated.** 88 self-named inline defaults in the `api-alpha` block; **81 already
agreed**; 7 did not. Two are real — this one, and `PORTFOLIO_HEALTH_TRIAL_FINDINGS` at compose `7`
vs Settings `3`, meaning **7 is what the CR136 portfolio-health feature runs today** and the declared
3 is dead. One is deliberate (`SECRET_KEY` empty in compose so an unset key fails the boot check
rather than inheriting the in-code dev placeholder). Four have no scalar default to compare.

**A third parity direction, not a comment.** Every `${KEY:-X}` must equal its `Settings` default or
carry an `_INLINE_DEFAULT_EXEMPT` entry saying why compose is right. **Verified red against the exact
pre-fix state before green** — restoring `:-30` fails both new tests and leaves the seven
pre-existing ones passing, which is itself the proof of the blind spot.

**`PORTFOLIO_HEALTH_TRIAL_FINDINGS` is recorded, NOT changed.** It belongs to the CR136 lane, and
picking a number for it here would alter another lane's shipped feature on a promotion that has
nothing to do with it. Its exemption entry names the owner and the live value; that entry **is** the
flag. **Auditor: this is a judgement call and worth challenging** — the alternative reading is that
leaving a known-wrong declared default in place is itself a defect.

## Live verification (post-promotion, in-container on Alpha)

Not claimed from unit tests — read out of the running container at `alpha-2026-08-11-8`:

- `settings.social_cache_ttl_days` → **7** (was 30 before DEF260, on the same code).
- `fetch_live_sentiment('NVDA')` → 2,865 mentions; **854 positive / 552 negative / 1,459 neutral**
  (neutral **51%**); 552 distinct posts, 12,894 upvotes; `subreddit_count` **49** with three
  `SubredditStat` rows carrying real per-community sentiment and buzz; `fetched_at` rendering
  *"fetched 2026-08-11 (1m ago)"*.
- `fetch_live_news` → NVDA 3 kept at 5m/1h/1h; **SNOA 3 kept at 4d/5d/5d**.
- **The SNOA result is stated against my own expectation, not for it**: CR147 measured its newest
  article at 354 days, and today its coverage is inside the floor. The floor therefore did **not**
  fire on the one ticker that motivated it. That is a real change in the supplier, not evidence the
  fix works — the fix's evidence is the unit tests, and this line exists so the auditor does not
  find the discrepancy first.
- The primary Adanos key logged `monthly_remaining=49`. The failover shipped here is about to carry
  real traffic rather than sit idle — worth knowing when reading the quota reasoning above.

## Verification

- `backend/tests/unit/test_cr148_cr147_feed_depth.py` — **36 tests**.
- `backend/tests/unit/test_config_compose_parity.py` — 3 new tests (DEF260), red-before-green.
- **`test_prompt_data_parity.py` bit exactly as CR148 predicted it would**, and was answered with
  renders rather than with `INTENTIONALLY_OMITTED` entries: all eight new `SocialSentiment` fields
  are rendered-or-declared on **both** the `room` and `one_on_one` surfaces. The `fetched_at`
  fingerprint is derived **independently of the formatter under test** (the news `published_at` entry
  takes the other route and calls its formatter; doing that for both would leave neither
  non-vacuous).
- **The call site, not just the builder.** `test_the_room_fact_sheet_actually_carries_the_new_social_depth`
  drives the real `_format_profile` render — the DEF238 blind spot, where a PM-only feature never
  worked once in production while its tests passed for the feature's entire life.
- Full shared-checkout suite at `3e08d23e`: **3445 passed, 1 skipped**, 437.85s; at `e53b714a` (with DEF260): **3448 passed, 1 skipped**, 435.76s.

## What is NOT claimed

- **The 9-of-18 fabricated-attribution rate is response-side and is NOT re-measured here.** Supplying
  the per-community split is the necessary half; whether the agent stops attributing to communities
  it was not given is the measurement, and CR105 Amendment 1 says an unmeasured prompt edit is the
  trap. Owed on ≥30 convenes post-promotion.
- Same for the small-sample caveat and the freshness label: both are supply-side.
- **The floor does not make the feed thicker.** Whether SNOA's 354-day feed is a rate or an accident
  is still n=1 of 18. A ticker whose only coverage is a year old now correctly reads UNAVAILABLE —
  which is a *reduction* in rendered data, and the honest one.
- **CR148 Tier C is untouched** — the three instructions with no data dimension behind them
  (organic-vs-coordinated, contrarian extremes, meme cycles) still have none. Tier D likewise.
- **CR147 B.2 (Yahoo `summary`) and B.3 (the watchlist) are not here.** B.2 would add ~430 chars to a
  **shared** block × 12 agents, and this batch already adds to the social lane; sizing that against
  DEF258's cap-hit rate needs the post-promotion measurement first.
- This batch adds prompt bytes to the social lane only. The eight full-sheet agents that clipped in
  DEF258 are unaffected by the Tier A renders, but the news header edit reaches all twelve.

---

**SUBMITTED: round 1**
