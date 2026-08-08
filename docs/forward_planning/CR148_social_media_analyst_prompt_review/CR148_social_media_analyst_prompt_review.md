# CR148 — The sentiment feed is live, 20 days old, and half-read

**Filed:** 2026-08-08 · **Status:** proposed · **Decision:** Saiful, 2026-08-08 — *"book CRs one for
each agent."* One CR per agent so each remedy is decided on its own evidence rather than bundled.
**Source:** CR143 Phase 1/3b + two independent reviews of the Social Media Analyst — a blind
prompt-coherence audit ([`external_review/room/social_media_analyst.md`](../CR143_agent_prompt_audit/external_review/room/social_media_analyst.md))
and a codebase-verified data-sufficiency audit ([`external_review/room/kimi/social_media_analyst_data_sufficiency.md`](../CR143_agent_prompt_audit/external_review/room/kimi/social_media_analyst_data_sufficiency.md)).

## Why

The Adanos Reddit feed is genuinely live and DEF096 is genuinely closed. Measured on the CR143 epoch
corpus (2026-08-07, n=18 convenes, 216 turns): **216 of 216** prompts carry the live-social
disclosure header, and **18 of 18** Social Analyst prompts render all four Inputs its own job names —
mention volume, buzz score, bullish/bearish split, most-active communities. The blind review's core
contradiction ("the prompt demands numbers and supplies none") does not hold on the live path.

Three different things are wrong instead, and none of them is a missing feed.

1. **"As of this call" is false for most turns, and nothing says so.** Queried against the live Alpha
   Postgres on 2026-08-08: `social_sentiment_cache` holds **175 rows**, mean age **20.2 days**, oldest
   **22.4 days**, **162 of 175 (93%) older than 7 days**, 151 of them sitting in a single 20–25 day
   bucket. `social_cache_ttl_days = 30` (`config.py:210`), forwarded (`docker-compose.yml:262`), and
   `printenv SOCIAL_CACHE_TTL_DAYS` in the running `ami_api_alpha` container returns `30`. The prompt
   says *"LIVE, real Reddit aggregate data **as of this call**"* (`room_prompts.py:635`). Of the 18
   epoch turns, **8** (AMD ×2, NVDA ×2, BAC, AVGO, MU, TSLA) were served from rows that have not been
   written since 2026-07-17 — roughly **21 days stale at the moment of the turn** — and 10 were
   fetched same-day. Sentiment is the most perishable field on the sheet; quotes cache for 60s and
   news for 5 minutes.

2. **Four dimensions arrive on the same API call and are thrown away.** `_to_sentiment`
   (`social_context.py:203-221`) reads 8 of the ~15 fields Adanos returns. Verified against the real
   captured response in `tests/unit/test_social_context.py:71-107`: per-subreddit `mentions` /
   `sentiment_score` / `buzz_score`, `total_upvotes`, `unique_posts`, `subreddit_count`, and
   `positive/negative/neutral_count` are all present and all discarded — only the subreddit *name*
   survives. In that captured sample r/wallstreetbets read −0.053 against r/ValueInvesting's +0.103,
   and WSB carried 904 of 1,993 mentions. The "fractured community" read this agent exists to make
   was in hand and dropped on the floor.

3. **The model fills the gaps, unlabelled.** Measured on the 18 turns: **9 of 18** attach a sentiment
   figure, tone or trend to a *named* subreddit the fact sheet carries no per-community data for
   (*"The bearish sentiment is accelerating in the most active communities, specifically
   r/wallstreetbets"* — KTOS, on 47 total mentions). The base prompt's own prohibition is
   *"You DO NOT … Speak on behalf of any specific community"* (`content/agents/social_media_analyst.md:34`).
   This is invisible to CR143's M3 number-provenance metric — which puts this agent at **0.0% novel
   numbers**, joint-best of the 11 prose agents — because every *number* is real. It is the
   *attribution* that is invented.

The through-line: **this agent is not short of a feed, it is short of the half of the feed we already
pay for, and short of an honest freshness label on the half we render.**

## Scope — four tiers, ordered by cost

### Tier A — render what is already fetched and discarded (free on quota, one API call unchanged)

| payload field | present at | fate today |
|---|---|---|
| `top_subreddits[].sentiment_score` / `.buzz_score` / `.mentions` | `test_social_context.py:88-93` | only `.subreddit` kept (`social_context.py:204-206`) |
| `neutral_count` (and `positive_count` / `negative_count`) | `:80` | dropped; `bullish_pct`/`bearish_pct` read, residue never stated |
| `total_upvotes`, `unique_posts` | `:81-82` | dropped — the entire engagement/intensity dimension |
| `subreddit_count` | `:83` | dropped — 41 subreddits in the sample, 3 named |

Extend the `SocialSentiment` NamedTuple + `_to_sentiment`, render under the existing
`_social_detail_lines` detail block (`room_prompts.py:763-784`). Two measured problems close here:

- **The neutral residue is the majority class and is never stated.** Across the 18 turns
  `100 − bullish_pct − bearish_pct` ranged **42%–71%, median 52.5%**. Two of 18 turns noticed.
- **Per-community divergence** — the fix for the 9/18 fabricated attribution above. Supply the split
  and the invention has nothing to do.

**Guard that bites, and must be updated in the same commit:** `test_prompt_data_parity.py` asserts
`set(SocialSentiment._fields)` is *rendered-or-declared* on **both** the `room` and `one_on_one`
surfaces (`:157`, `:386`, `:410-419`). Every new tuple field needs a fingerprint entry and a render
on both surfaces, or an explicit `INTENTIONALLY_OMITTED` entry with a written reason. Adding fields
and not touching that test turns it red — this is the CR105 shape and it is the reason this tier is
"hours", not "minutes".

Also here, and cheap: **sample-size disclosure.** Measured mention counts across the epoch spanned
**10 to 3,990**; **5 of 18** turns ran on fewer than 52 mentions. At GRAB's n=10, *"bullish 30% /
bearish 10%"* is 3 posts against 1, rendered by `format_pattern` (`social_context.py:313-314`) in the
byte-identical shape it uses at n=3,990. The count is already on the sheet — what is missing is any
instruction that a percentage over 10 mentions is not a percentage. Two of the six small-n turns
flagged the thinness; four did not, and SNOA (n=12) produced *"signaling organic momentum"* and
*"extreme euphoria often precedes volatility"*.

### Tier B — stop claiming freshness we do not have (needs one quota decision from Saiful)

Two halves, and only the second costs anything:

- **Free half — render the age.** Replace *"as of this call"* with the row's `fetched_at`, e.g.
  `Retail sentiment (Reddit via Adanos, fetched 2026-07-17 — 21d ago)`. No parser reads this string;
  it is prompt-facing only. Fix the three-way drift in the same commit: `social_context.py:8-9` and
  `:228` still say **"24h TTL"**, config says **30 days**, the prompt says **"as of this call"**.
- **Paid half — shorten the TTL.** Arithmetic, not an estimate: the free tier is 250 calls/month and
  one uncached ticker costs one call, so a 30-day TTL supports ~250 distinct tickers/month while a
  7-day TTL costs ~4.3 calls per distinct ticker/month and caps at ~58. That is a product decision
  about breadth-vs-freshness, and it is Saiful's.
- **Latent, DEF063-class:** `ADANOS_API_KEY_SECONDARY` exists in melehost's `.env` but **no
  `adanos_api_key_secondary` setting exists in `config.py` and nothing forwards it in
  `docker-compose.yml`** — a second 250-call budget was provisioned (DEF063's 2026-07-21 note) and
  never wired. `test_config_compose_parity.py` cannot catch it because it is not a setting. Wiring it
  is the cheapest way to buy the TTL decision room.

CR040 applies squarely: a 21-day-old sentiment snapshot presented as "as of this call" is a silent
fallback, and the question the convention asks — *if this fires constantly and silently, what does
the user end up believing?* — answers itself.

### Tier C — three instructions with no data dimension behind them (design decision)

Each is a demand the prompt makes, the data cannot satisfy, and the model satisfies anyway. This is
the CLAUDE.md rule in miniature: **prompt instructions are not controls.**

| instruction | data dimension | measured behaviour (n=18) |
|---|---|---|
| *"Distinguish organic enthusiasm from coordinated activity"* (`:25`) | **none** — no account, velocity or coordination field exists anywhere in the Adanos payload | 5/18 turns use coordination/organic language regardless |
| *"Surface contrarian signals (extreme greed → reversion risk…)"* (`:26`) | **none** — no baseline; `_cache_write` keeps exactly one row per ticker and overwrites it (`social_context.py:91-112`), so no series ever accumulates | 10/18 use extreme/euphoria/panic/frenzy language; 11/18 use contrarian/reversion/exhaustion |
| *"meme cycles"*, *"early-warning system for euphoria and panic"* (`:12`) | same missing series | — |

Two ways out per row: **supply the dimension** (Tier D for the baseline; a new provider for
coordination) or **delete the instruction**. Tier A softens the first two without closing them —
engagement intensity and per-community divergence are the honest evidence an organic-vs-coordinated
*framing* could rest on, and `buzz_score` gains meaning once a per-subreddit distribution sits next to
it. The extremes call does not survive without a baseline, so as long as Tier D is unfunded the
extremes instruction should be rewritten to something the snapshot can support.

Also in this tier, cheap and unambiguous: **scope the excerpt promise to 1-on-1.** The base prompt
says *"you may see real (anonymized-by-omission) excerpts as context"* (`:17`); measured, the string
`Sample community reactions` appears in **0 of 216** Room prompts. See the rejected-claims section —
the Room omission is correct and must stay; it is the prompt clause that is wrong.

### Tier D — not available without new wiring (separate decisions, not this CR)

- **Sentiment baseline / history.** Adanos is point-in-time (one endpoint, no history parameter,
  `social_context.py:136-139`) and the durable cache overwrites in place. An append-only history table
  would build a baseline out of the provider we already pay for — a schema change, not a new feed.
  It is also the only route to a **mention-trend magnitude**: the payload carries an absolute
  `mentions` and a `trend` *string* (`rising`/`falling`/`stable`), never a delta. Note that the old
  fabricated *"up 40% week-over-week"* was already removed (`room_runner.py`, CR034 comment) — this is
  a gap, not a regression.
- **Organic-vs-coordinated detection.** Needs a provider that does not exist in our stack.

## Verified findings

Every finding below carries its supplier check (does the code inject what the prompt claims?) and its
parser check (does anything read the output this instruction shapes?).

**F1 — the freshness claim is false for most turns.** Supplier: `_cache_read` gates on
`settings.social_cache_ttl_days` (`social_context.py:68`); nothing anywhere renders `fetched_at`.
Parser: none — prompt-facing string, safe to change. Measured: mean cache age 20.2d, 93% of rows
>7d, 8 of 18 epoch turns ~21d stale. Docstring says 24h, config says 30d, prompt says "this call".

**F2 — four payload dimensions fetched and discarded.** Supplier: verified field-by-field against the
real captured Adanos response. Parser: `test_prompt_data_parity.py` is the guard, and it will bite.

**F3 — invented per-community attribution.** 12/18 turns name a subreddit; **9/18** attach a
sentiment quantity, tone or trend to a named one. Violates the agent's own *"Speak on behalf of any
specific community"* prohibition. Not caught by M3 (0.0% novel numbers) because the numbers are real.

**F4 — sample size never disclosed.** n ranged 10→3,990; 5/18 turns under 52 mentions; identical
render shape at both ends; 4 of 6 small-n turns did not flag it.

**F5 — the tone label and the score are two unrelated derivations printed side by side.**
`format_sentiment_tone` (`:291-296`) is a bull/bear **percentage-gap** classifier (bullish if
bull > bear + 5); `format_sentiment_score` (`:299-300`) is the raw signed composite. Measured: 10 of
18 turns render tone `bullish`, and **6 of those carry |score| < 0.10** — AMD's *"bullish (+0.04)"* is
the code working as written, not a fetch bug. Fix is a render rule (state the basis) or drop one of
the two.

**F6 — three role instructions have no data dimension.** Detail in Tier C.

**F7 — the illustrative-fallback branch contradicts the CR077 parallel-phase line, and it is
reachable.** All 18 prompts carry both *"reason qualitatively and illustratively instead, using
whatever real price/fundamentals/news context is available from the other analysts and the debate
transcript"* (base prompt `:18`) and *"You are speaking AT THE SAME TIME as the other analysts and
cannot see their contributions — the transcript above is empty by design"* (`room_prompts.py:439`).
Reachability, traced: `resolve_social_feed` returns `UNAVAILABLE` on any Adanos network error, any
non-200 (**including a 429 once the 250/month budget is spent**), or `found: false`; `room_runner.py`
then leaves the crc32-seeded scaffolding in place and `_social_detail_lines` returns `[]` (gated on
`field_state["social"] == "live"`). On that branch the entire social block collapses to one line —
`Retail sentiment: moderately bullish (typical intensity (illustrative))` — which is *exactly* the
prompt the blind review was handed. **0 of 216 epoch turns hit it**, so it is untested in production,
but it is one outage or one quota exhaustion away, and when it fires the agent is told to borrow from
a transcript the next paragraph tells it is empty. Same branch, smaller: the header calls them
*"Retail sentiment/mention/**influencer** fields"* (`room_prompts.py:650`) while nothing named
influencer ever renders — the live path labels the same field `Communities:`.

**F8 — the excerpt promise is 1-on-1-only, and the Room omission is deliberate and correct.** See
rejected claims R5. The prompt clause is the defect, not the omission.

**F9 — out-of-lane citation: 13 of 18 turns, and the CR143 stub over-attributes it.** With a lane
regex tightened to exclude the phrase *"mention volume"* (which is this agent's **own** lane, and
accounts for 6 of the stub's technicals hits): price technicals **6/18**, valuation/fundamentals
**7/18**, news/catalyst **4/18**, at least one of the three **13/18**, a `$` price quoted **2/18**.
The sharpest instance is the HEADLINE — the single line the UI renders as the agent's summary — where
**3 of 18** are out of lane: `19.0x P/S`, `Bullish sentiment clash with overbought RSI`,
`98% of 50-day range`. The remedy (per-agent fact sheet) is **CR145 Tier C**; recorded here as this
agent's measurement, not re-scoped.

**F10 — cross-agent, surfaced here, not scoped here.** `parse_stance_envelope` **nulls** a headline
over `STANCE_HEADLINE_MAX_CHARS = 32` — *"Nulled, never cut"* (`room_runner.py:1779`,
`room_prompts.py:255`) — so the turn renders with no headline at all. Measured across all 192
envelope-carrying turns: **11 nulled**; social **2 of 18** (one by a single character, at 33). Highest
rates are bull_researcher and news_analyst at 3/18 each. This belongs with CR145 Tier B's
post-promotion re-measure of the CR143 baselines, not with a Social-only edit.

## Rejected claims and why

This section is the point of the exercise. CR105 was written from prompt files alone and two of its
four findings were wrong once checked against the parser.

**R1 — "DEF096 is open / the social feed is dark."** REJECTED, measured. All four named Inputs render
in **18/18** social prompts; **216/216** prompts carry the live header; 0 carry the withheld or
synthetic variant. DEF096 is `fixed` in the register (`dc29c5c`) and the fix is visible in production
output. `PHASE1_ground_truth.md:110` already carries the corrected statement — no doc fix needed.

**R2 — blind review: "Numbers demand vs. absent social data" as the agent's core contradiction.**
REJECTED for the live path (0/216 non-live). Its sample predates DEF096's fix and was captured on the
synthetic branch. **Retained in a different form** as F7 — the branch is reachable and the fix belongs
to the fallback text, not to a rewrite of the live prompt.

**R3 — blind review: "hallucinated social metrics" as the failure mode.** REJECTED on the corpus.
CR143's M3 puts `social_media_analyst` at **0.0% novel numbers**, joint-lowest of the 11 prose agents
with `news_analyst`; an independent read of all 18 replies found no figure outside the fact sheet.
What is invented is **non-numeric attribution** (F3) — a different defect with a different fix, and
one no number-provenance metric can see.

**R4 — blind review CUT list: delete the duplicated mandate block and the whole simulated-portfolio
section from this agent's prompt.** REJECTED as this CR's scope, on two grounds. (a) Both are
*shared* Room scaffolding that all 12 agents receive; cutting them for one agent forks a prompt path,
and the principled version of that change is CR145 Tier C's per-agent visibility matrix. (b) **No
measured harm:** a scan for portfolio / sizing / allocation / drawdown / stop / cash / holdings
language across the 18 social turns returns **0 of 18**. The bloat is a token cost, not a behaviour
defect, for this agent.

**R5 — kimi review §6.4: "inject the snippets into the Room, they're already fetched."** REJECTED,
and this is the supplier check that matters most. `sample_snippets` is real Reddit post text.
The Room profile dict is **also** the format source for `_TEMPLATES[AgentId.SOCIAL_MEDIA_ANALYST]`
(`room_runner.py:207-215`), the scripted non-LLM fallback that is rendered **directly to users** on
any LLM outage — `"Retail sentiment on {ticker} reads as {sentiment_tone} … Community read:
{influencer_take}. Pattern: {pattern}."`. A snippet placed in the profile ships verbatim Reddit
content to a user. The omission is not an oversight: it is written into the module docstring
(`social_context.py:14-20`) **and** registered with a reason in `test_prompt_data_parity.py`'s
`INTENTIONALLY_OMITTED` map. If snippets are ever wanted in the Room they need a separate LLM-only
channel that never touches the profile dict — out of scope. What is in scope is the *prompt clause*
that promises them (Tier C).

**R6 — kimi review §3 #8: "mention-trend magnitude" as a cheap gap.** PARTIALLY REJECTED as framed.
It is not renderable from the payload at any price — Adanos supplies an absolute count and a trend
*string*, never a delta. It is downstream of the history table, so it sits in **Tier D**, not in the
cheap tier where the review's §6 list implies.

**R7 — kimi review §3 #9: "no cross-platform sentiment."** Agreed and no action — it is disclosed
honestly in the prompt as a scope limit, and no Twitter/X, StockTwits, Google Trends or Discord
integration exists or is planned.

**R8 — kimi review §2: "~85–90% accuracy on the scoped deliverable, ~50–60% against the full role."**
REJECTED as evidence and deliberately not carried into this CR. No method is stated and neither
figure is reproducible from the corpus. Every number in this document was computed against
`corpus/llm_audit_2026-08-07-epoch.json` or the live Alpha database in the same session.

**R9 — the CR143 stub's "cites technicals 13/18."** CORRECTED to 6/18 (see F9). Six of the original
hits are the phrase *"mention volume"* — this agent's own Input, named as such in its base prompt at
`:16`. The **13/18** figure is right for *at least one* other lane, which is how it should have been
labelled. The stub's `valuation 3/18` and `news 2/18` also move (to 7/18 and 4/18) once `consensus`,
`profit margin` and `earnings` are counted.

## Acceptance

All re-measurable post-promotion with the same scripts against a fresh epoch export.

- **Tier A:** per-subreddit sentiment/buzz/mentions, the neutral share, `total_upvotes`,
  `unique_posts` and `subreddit_count` appear in the Room fact sheet under `field_state` provenance.
  `test_prompt_data_parity.py` green **and non-vacuous** — every new `SocialSentiment` field either
  renders on both surfaces or carries a written `INTENTIONALLY_OMITTED` reason. Re-measured on ≥30
  convenes: turns attaching a sentiment figure or tone to a named subreddit **without** the supporting
  per-community number fall from **9/18** to ≤1 in 30.
- **Tier A (sample size):** no turn running on <60 mentions states a bull/bear percentage without the
  count in the same clause. Re-measured: currently 4 of 6 such turns fail this.
- **Tier B:** no prompt anywhere claims *"as of this call"* for a cached field. The rendered social
  block carries the fetch date. `social_context.py`'s "24h TTL" docstring, `config.py`'s
  `social_cache_ttl_days` and the prompt string agree — a grep for `24h TTL` returns nothing stale.
  If the TTL is shortened, `social_sentiment_cache` mean row age re-measured post-promotion is below
  the new TTL, and `social_context_adanos_budget_nearly_exhausted` has not fired.
- **Tier B (secondary key):** either `adanos_api_key_secondary` is a real setting forwarded in
  `docker-compose.yml` (and `test_config_compose_parity.py` covers it), or the unused key is removed
  from melehost's `.env` — no provisioned-but-unread key survives this CR.
- **Tier C:** every instruction remaining in `content/agents/social_media_analyst.md` names a field
  that the Room fact sheet can supply, or says plainly that it is a framing rather than a measurement.
  Re-measured on ≥30 convenes: unhedged coordination/organic claims (currently 5/18) and unhedged
  "extreme/euphoria/panic" claims (currently 10/18) each fall by more than half, **or** the
  corresponding instruction is gone.
- **Tier C (fallback branch):** with Adanos forced to fail, the assembled Social prompt contains no
  instruction to draw on other analysts or the transcript during the parallel ANALYSTS phase, and no
  reference to an "influencer" field. A unit test asserts this against a `UNAVAILABLE` social feed —
  the branch is currently 0/216 exercised in production and must not stay untested.
- **F5:** the fact sheet does not print a directional tone label beside a near-zero composite score
  without stating the tone's percentage-gap basis. Currently 6 of 18 turns receive that pairing.
- `pytest backend/tests/unit/ -q` green throughout.

## Out of scope

- **Owned by [CR145](../CR145_fundamentals_data_and_lane_discipline/CR145_fundamentals_data_and_lane_discipline.md):**
  the `_LENGTH_GUIDE` / `_PROSE_FORMAT` / `_STANCE_FORMAT` conflict (DEF236), `_LEVEL_PATTERNS` vs the
  prose format (DEF235), `LearningStyle.QUICK`'s *"tabular"* against *"no tables"*, and the per-agent
  fact sheet (`_format_profile` takes no `agent_id`) — which is the real remedy for F9's 13/18
  out-of-lane rate and F10's nulled headlines.
- **DEF063's other half.** Verified still open on 2026-08-08: `ALPHA_VANTAGE_API_KEY` is absent from
  melehost's `.env` and empty in the `ami_api_alpha` container, so 0 of 216 catalyst lines carry a
  per-article sentiment tag. That is the News Analyst's CR, not this one. The overlap is only that
  both halves of DEF063 were provisioning gaps; the Adanos half is closed and live.
- Snippet injection into the Room (R5), cross-platform sentiment (R7), coordination detection and a
  sentiment history table (Tier D) — each a separate decision.

## Notes

Tier A is free on quota and independent — it can ship alone, and it is the tier that closes the
fabricated-attribution defect. Tier B's free half (render the fetch date) should ship with it; its
paid half waits on Saiful's breadth-vs-freshness call. Tier C is a prompt edit whose effect **must**
be re-measured post-promotion — an unmeasured prompt edit is the CR105 Amendment-1 trap, and this
agent already demonstrates the reason: it has been told *"never present a specific number … as if it
were measured"* since CR024 and complies perfectly on numbers, while inventing the per-community
attribution nobody wrote a rule against.
