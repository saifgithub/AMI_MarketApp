<!--
R68-BATCH9.auditor.md — auditor lane. Round 1 verdict against the architect submission in
R68-BATCH9.architect.md. Written by track U; the architect never edits this file.
-->

# R68-BATCH9 — auditor lane

Audited: `3e08d23e` (batch) + `e53b714a` (DEF260). Both on `main`, both on origin
(`git branch -r --contains <sha>` → `origin/main`). Promoted `alpha-2026-08-11-8`
(`git tag --contains 3e08d23e` → `alpha-2026-08-11-7`, `alpha-2026-08-11-8`).

`SCOPE: chunk` → no Definition-of-Done table owed; gap-fill 7 waives enforcement in any case.
`depends-on: R68-BATCH4` — that lane's own round-1 verdict landed on origin while this audit was
running (`cee6c124`) and is **AWAITING_FIXES**. Guardrail 3: a COMPLETE here could only ever have
been PROVISIONAL until Batch 4 closes.

Tree under test: worktree at `b402dbea`. `git diff --stat e53b714a..HEAD` = docs + lane files only,
**zero source/test delta**, so every in-scope file is byte-identical to `e53b714a`.

Run report: `orchestration/audit/runs/2026-08-11_run-01/run_report.md`.

## Verdict summary

**0 BLOCKER · 4 MAJOR · 5 MINOR.** Round 1 bounces.

The engineering is largely right and several of the riskiest claims reproduce exactly, live, against
production data (see CONFIRMED below). The four MAJORs are: one factual claim about prompt size that
is wrong in the direction that matters; one retry path that can only lose; one live-wrong value
parked in an exemption dict instead of a register row; and a new guard whose skip set is undeclared
and whose register row says something false about what covers it.

---

## MAJOR-1 — "adds prompt bytes to the social lane only" is false: Tier A adds **+505 chars (+27.8%)** to the shared fact sheet of **9 of 12 Room agents**, including all four DEF258 measured clipping

The submission's *What is NOT claimed* says:

> This batch adds prompt bytes to the social lane only. The eight full-sheet agents that clipped in
> DEF258 are unaffected by the Tier A renders, but the news header edit reaches all twelve.

Both halves are wrong, and in opposite directions.

`room_prompts.py:782-803` — `_AGENT_LANES` names **only four** firewalled analysts; `_lane_for`
returns `_ALL_DOMAINS` for everything else. So `_in_lane("social")` (`room_prompts.py:1095`) is TRUE
for every full-sheet agent, and `_social_detail_lines` renders the new block to all of them.

Measured through the real renderer (`_format_profile`, same profile dict with and without the four
new keys):

```
portfolio_manager      sheet  1819 ->  2324  (+505 chars, +27.8%)
bear_researcher        sheet  1819 ->  2324  (+505 chars, +27.8%)
aggressive_debator     sheet  1819 ->  2324  (+505 chars, +27.8%)
neutral_debator        sheet  1819 ->  2324  (+505 chars, +27.8%)
social_media_analyst   sheet  1266 ->  1771  (+505 chars, +39.9%)
news_analyst           sheet  1059 ->  1059  (+0 chars, +0.0%)
```

Per-agent lane sweep: `social` in lane for `social_media_analyst`, `bull_researcher`,
`bear_researcher`, `research_manager`, `trader`, `aggressive_debator`, `conservative_debator`,
`neutral_debator`, `portfolio_manager` (+ `concierge`) — **9 of 12 Room agents**, not one.
`fundamentals_analyst`, `market_analyst`, `news_analyst` get +0.

The news header edit is the mirror image: it sits behind `if not _in_lane("news")`
(`room_prompts.py:946`), so it reaches `news_analyst` + the 8 full-sheet agents = **9 of 12**, not
"all twelve".

**Why MAJOR rather than a documentation nit.** This is the premise the batch used to defer its own
sibling item. The same section says CR147 B.2 is held back because it "would add ~430 chars to a
**shared** block × 12 agents … sizing that against DEF258's cap-hit rate needs the post-promotion
measurement first." Tier A shipped **+505 chars** — more than the deferred item — onto the same
shared sheet, and onto `portfolio_manager`, `aggressive_debator`, `neutral_debator` and
`bear_researcher` specifically, which are exactly the four agents DEF258 measured hitting
`max_tokens`. Either the B.2 deferral reasoning is wrong, or this shipped unsized under a belief
about the code that the code does not support. It cannot be both.

Not claimed by me: that this *causes* a DEF258 recurrence (DEF258 is decode-side). The finding is
that the risk was assessed against a false statement of blast radius.

**Fix direction:** state the real blast radius, and either size it against DEF258's post-promotion
cap-hit rate (the standard the batch itself set for B.2) or gate the per-community block to the
social lane.

## MAJOR-2 — `_get_with_failover` discards a valid primary payload, and the retry can only lose

`social_context.py:244-267`. When the primary answers **200 with real data** but
`x-ratelimit-remaining-monthly: 0`, `_quota_spent` returns True, the good response is thrown away
and the reserve key is called. Probed against the real method (fake transport, key recorded per
call):

```
A. primary 200 remaining=0, secondary healthy              keys=['PRIMARY', 'RESERVE']   -> status 200
B. primary 200 remaining=0, secondary network error        keys=['PRIMARY', 'RESERVE']   -> None (feed goes UNAVAILABLE)
C. primary 200 remaining=0, secondary 500                  keys=['PRIMARY', 'RESERVE']   -> status 500
D. primary 429 while monthly_remaining=200 (burst limit)   keys=['PRIMARY', 'RESERVE']   -> status 200
E. primary 200 remaining=180                               keys=['PRIMARY']              -> status 200
```

- **B/C are a data loss.** The primary already returned the payload. After failover, a secondary
  network error returns `None` (`:256`) and a secondary 500 returns a non-200 that `fetch` discards
  (`:312-314`) — so a turn whose sentiment was *in hand* renders `UNAVAILABLE`. The batch's own
  design rule ("a second key does not fix a network") is violated in the one case where the first
  key already succeeded.
- **The failover on a 200 is strictly dominated.** No exhaustion state is carried between calls, so
  the next `fetch` starts at `index 0` again regardless. Failing over on a successful 200 therefore
  buys nothing and costs one reserve call. The test's own justification —
  `test_a_spent_monthly_budget_retries_even_on_a_200`, *"the header is the earlier signal and the
  one that avoids a wasted round trip"* — is backwards: it **adds** the round trip.
- **D contradicts the docstring.** `:241` says failover fires "on quota exhaustion ONLY", but
  `_quota_spent` (`:211-212`) returns True for **any** 429 without consulting
  `x-ratelimit-remaining-monthly`. Adanos also enforces a burst limit — its own header is in the
  live log line (`burst_remaining: 99`, melehost `docker logs ami_api_alpha`), so a burst 429 with
  200 monthly calls left spends a reserve call.

**Live relevance, not hypothetical:** the primary key reads `monthly_remaining=48 / monthly_used=202`
on Alpha right now (`social_context_adanos_call`, 2026-08-11T16:03:06Z). The `remaining=0`
transition is days away, and this batch is what turned the failover on.

**Fix direction:** return a 200 as-is and let the *next* call fail over (or remember exhaustion), and
gate the 429 branch on the monthly header rather than on the status alone.

## MAJOR-3 — a known-wrong live value is parked in an exemption dict instead of a register row, and DEF219's register status is now false

Live, in the running container at `alpha-2026-08-11-8`:

```
ssh melehost "docker exec ami_api_alpha python -c \"from app.core.config import settings; print(settings.portfolio_health_trial_findings)\""
7
```

Against `config.py:334` (`portfolio_health_trial_findings: int = 3`),
`portfolio_health_constants.py:396` (`TRIAL_FINDINGS_DEFAULT = 3`),
`test_cr136_metrics_engine.py:782` (`assert TRIAL_FINDINGS_DEFAULT == 3`), and DEF219's own register
row, which reads status **`fixed`** and states its fix as *"`TRIAL_FINDINGS_DEFAULT` /
`portfolio_health_trial_findings` go 7 → 3"*. `health_gate.py:96` reads the **settings** value, so
the trial budget Alpha actually enforces is 7 — the pre-DEF219 number. DEF219 is recorded as fixed
and is dark in production.

Cause confirmed rather than inferred: `grep PORTFOLIO_HEALTH ~/ami_trade/.env` on melehost returns
**nothing**, so the live 7 comes from `docker-compose.yml:341`'s `${PORTFOLIO_HEALTH_TRIAL_FINDINGS:-7}`
inline default — the same mechanism DEF260 was filed for, on a second key, still live.

**The judgement call the submission asked me to challenge.** Not changing the value here is right —
altering another lane's shipped entitlement on an unrelated promotion would be worse. What is not
right is the disposition. `_INLINE_DEFAULT_EXEMPT` is documented, three lines above the entry, as
*"Known, **DELIBERATE** disagreements. Each states why compose's value is right and the Settings
default is not simply out of date"* — and the entry says the exact opposite ("compose 7 wins over
Settings 3 today — reconcile there, not here"). Compare the dict's other entry, `SECRET_KEY`, which
is genuinely deliberate and load-bearing (`main.py:55-84` refuses to boot on an empty key in any
non-local env): that is what a deliberate exemption looks like. One slot now holds a real design
decision and the other holds an admitted stale value, which is precisely the *"allow-list becomes
the place bugs go to hide"* failure this module's own two other allow-lists are written to prevent
(`test_config_compose_parity.py:106-110`, `:200-205`).

The claim that "the exemption entry **is** the flag" does not hold: the entry lives inside a
permanently-green test, names no owner outside a comment, carries no ID, and appears in no register.
`CLAUDE.md` § Change governance is explicit — a defect is filed the same way when you spot one, and
the Architect is the ID minter. A one-line row makes it visible; an exemption string makes it
invisible in a new way.

**Fix direction:** mint a DEF for the compose-7 / Settings-3 / constant-3 disagreement (value
unchanged, CR136 lane owns the number), cite that ID in the exemption string, and correct DEF219's
row so it does not read `fixed` while the deployed value is the pre-fix one.

## MAJOR-4 — the new third parity direction skips 8 forwards without declaring them, and the register row says something false about what covers them

Re-derived independently from `docker-compose.yml` + `Settings.model_fields`, using the guard's own
regex (script, not the guard):

| bucket | count | keys |
|---|---|---|
| env assignments in the `api-alpha` block | 89 | — |
| self-named `${KEY:-X}` inline defaults | **84** | — |
| agree with the `Settings` default (post-fix) | 78 | — |
| disagree | 2 | `SECRET_KEY` (exempt, correct), `PORTFOLIO_HEALTH_TRIAL_FINDINGS` (exempt, MAJOR-3) |
| **skipped — no scalar default** | **4** | `APPLE_AUDIENCES`, `GOOGLE_AUDIENCES`, `LEAGUE_ELIGIBLE_PLANS`, `PORTFOLIO_HEALTH_PLANS` |
| **not matched by the regex at all** | 5 | `ENV` (`:?`, correctly out of scope) + 4 literal forwards |

**The four skipped ones are not unjudgeable.** Every one is a `CsvList` field with a
`default_factory` (`config.py:322`, `:336`, `:556`, `:563`), and `Settings._csv_or_json_list`
(`config.py:19-32`) is the function that makes the compose string comparable to the factory value —
it lives in the same module the guard already imports:

```
APPLE_AUDIENCES        compose='ai.agenticmarketintel.amiTrade'  factory=['ai.agenticmarketintel.amiTrade']
GOOGLE_AUDIENCES       compose=''                                factory=[]
LEAGUE_ELIGIBLE_PLANS  compose=''                                factory=[]
PORTFOLIO_HEALTH_PLANS compose='trader,floor_manager'            factory=['trader', 'floor_manager']
```

All four agree today, so **no live drift is hidden right now** — the finding is the silent skip, not
a current bug. But `field.default is PydanticUndefined → continue` passes with no exempt entry, no
reason, and no record, on a field family that includes `APPLE_AUDIENCES` / `GOOGLE_AUDIENCES` —
DEF038's own fields, the defect this entire module was written for. The four **literal** forwards
(`DATABASE_URL`, `REDIS_URL`, `CORS_ORIGINS`, `BUG_ATTACHMENTS_DIR`) are likewise unseen by the new
direction; checked by hand, also clean today.

**The false claim.** DEF260's register row states, under *What is NOT claimed*, that "a forward under
a different name, or a field with a validator/factory default, is still the other two directions'
problem." It is not. Both other directions test **reachability** — `test_every_settings_field_is_forwarded_or_explicitly_excluded`
matches `^\s+([A-Z][A-Z0-9_]*):` and never reads a value; `test_every_env_file_key_maps_to_a_settings_field_or_is_declared_non_app`
walks key names only (and **skips entirely** in any checkout without `infra/alpha.env`, as it did in
mine). Nothing in the repo compares a value for those 8 keys. A register row is the durable record of
what is guarded, and this one over-states it on the exact defect class it was written for.

**Fix direction:** compare through the field's own validator (`Settings._csv_or_json_list`) — a
three-line change — or list the four in `_INLINE_DEFAULT_EXEMPT` with reasons, and correct the
row's coverage sentence.

---

## MINOR

- **M1 — the DEF260 measurement is off by 4 in both published figures.** The lane file, the commit
  message and DEF260's register row all say "88 self-named inline defaults … 81 already agreed; 7 did
  not." Re-derived with the guard's own regex: **84** self-named inline defaults; pre-fix **77**
  agree / 3 disagree / 4 skipped; post-fix 78 / 2 / 4. The `7` is right (3 mismatches + 4 skipped);
  the 88 is the block's **89** env assignments minus the one `:?` line, i.e. it counts the four
  literal (non-`${}`) forwards as inline defaults. Also: "leaves the **seven** pre-existing ones
  passing" — the file has **six** pre-existing tests, and one of them (`…_maps_to_a_settings_field…`)
  *skips* in a checkout without `infra/alpha.env`, so the observed shape is `2 failed, 6 passed,
  1 skipped` where 6 = 5 pre-existing + 1 new. Also: the lane's own CR148 Tier A heading says "six
  dimensions" where the field count is eight. Numbers in a register row are the durable claim; these
  are stated as *"Measured, not estimated."*
- **M2 — `_MIN_MENTIONS_FOR_A_PERCENTAGE = 100` is derived from the wrong statistic.** The arithmetic
  quoted is correct — `sqrt(0.25/100) = 5.0pp` — but that is the SE of a **single** proportion, and
  `format_sentiment_tone` thresholds a **difference** of two proportions. For a trinomial,
  `Var(p̂₁−p̂₂) = [p₁+p₂−(p₁−p₂)²]/n`: at AAPL's real 22/20 split that is **6.5pp** at n=100, at
  30/10 (GRAB) **6.0pp**, at 50/50 **10.0pp**. The 5-point gap equals one SE **of the gap** only at
  n≈168–400. So the conclusion ("below 100 the gap is inside one SE") is true, but it stays true well
  above 100 — 100 is a floor, not the derived threshold, and "DERIVED, not chosen" is stronger than
  the derivation supports. `test_the_small_sample_threshold_is_derived_from_this_modules_own_classifier`
  enshrines the same conflation. Direction of error is permissive (the caveat fires less often than
  the stated principle implies); CR148's own acceptance asks for `<60`, which 100 still satisfies, so
  nothing shipped is wrong.
- **M3 — a dead news feed logs at the same level and in the same shape as a routine drop.**
  Reproduced live in-container: forcing two stale/undated items gives
  `[info] news_context_recency_floor_dropped dropped=2 floor_days=7 kept=0 ticker=ZZZZ`, then
  `RESULT None`, then `STATE LiveDataState.UNAVAILABLE` — correct behaviour, and the drop of
  `published_at == 0` is confirmed. But `kept=0` (the feed is dead everywhere) is `logger.info`, the
  same level and event name as `kept=2, dropped=1` (business as usual), while **every** other failure
  path in `news_context.py` uses `logger.warn`. The realistic trigger is a supplier schema change:
  `market_data.py:650-656` derives `published_at` from `content["pubDate"]` and falls back to
  `providerPublishTime`, `0` if neither is present — a yfinance field rename now takes news to
  UNAVAILABLE for **every** ticker, and the only signal is an INFO line. The submission calls this
  count "the only thing that says so"; make it say so louder when `kept == 0`.
- **M4 — old cache rows still make the full-coverage claim Tier A fixes, for up to 7 more days.**
  `format_community_read` only appends the breadth qualifier when `subreddit_count > len(top_subreddits)`,
  and pre-CR148 payloads carry `subreddit_count = 0`. Live on Alpha: 21 rows are inside the new TTL and
  19 of them are old-shape, so those turns still render `most active in r/pennystocks, r/smallstreetbets.`
  with no "N of M" (verified by reading the real `BAER` row through `_cache_read` in-container).
  Self-healing within the 7-day TTL; recorded so it is not mistaken for a defect later.
- **M5 — the 500-call arithmetic is a full-month figure and does not describe August.** The TTL
  decision is reasoned against "a 500-call budget that caps at ~116 distinct tickers/month". Live, the
  primary is at `monthly_used=202 / monthly_remaining=48` and the reserve is untouched, so ~298 calls
  remain for the rest of this month against **162 rows that just went stale** (`select count(*) …
  fetched_at < now() - interval '7 days'` → 162 of 183). The submission does flag `monthly_remaining=49`;
  the ceiling sentence next to it does not carry the caveat.

## OUT-OF-SCOPE (pre-existing; auditor never mints an ID)

- **`_AdanosSource.fetch` releases its lock before the DB read and the HTTP call**
  (`social_context.py:298-309`), so concurrent misses on the same ticker each spend a live call. Pre-
  existing and not caused here — but the 30 → 7 TTL raises the miss rate roughly fourfold against a
  hard monthly quota, so the exposure is materially larger after this batch than before it.
- **`test_def136_room_convene_does_not_block_loop.py::test_the_loop_never_stalls_while_the_builders_block`
  flakes under machine load.** It failed once in my full-suite run —
  `the event loop STALLED for 0.167s in a single gap (threshold 0.150s)`, i.e. **17 ms** over, while
  the box carried ~20 concurrent pytest suites (load average 34–52). Re-run in isolation immediately
  afterwards: `2 passed in 6.54s`. Nothing in this batch is async or on the loop path, so it is not
  counted against the lane — but a 150 ms jitter threshold on a machine that routinely runs
  concurrent audits will produce this again, and a spurious red in a full-suite gate is expensive.

## CONFIRMED (reproduced independently, not accepted)

- **DEF260 is red against the exact pre-fix state.** Restored `SOCIAL_CACHE_TTL_DAYS: ${SOCIAL_CACHE_TTL_DAYS:-30}`
  in my worktree → `2 failed, 6 passed, 1 skipped`, failing exactly
  `test_inline_compose_defaults_match_settings` and `test_the_social_ttl_specifically_is_not_dark`
  (`assert '30' == '7'`), with every pre-existing test still green. Mutation reverted; `git status`
  clean.
- **DEF260's fix is effective on Alpha.** `docker exec ami_api_alpha python -c "… settings.social_cache_ttl_days"`
  → **7**; `adanos_api_key_secondary` present.
- **`_NEWS_RECENCY_FLOOR_DAYS = 7` really is CR147's own acceptance criterion**, not a number picked
  at build time: `CR147_news_analyst_prompt_review.md:227` — *"Tier B: … Re-run the age parse over a
  fresh epoch: `>7d` must be 0, or the run must be `UNAVAILABLE`."* Verified by reading the CR, not
  by accepting the claim.
- **Backward compatibility holds on real production data.** Read a genuine pre-CR148 row
  (`BAER`, written 2026-08-05, no `subreddit_stats`, no `fetched_at`) through `_cache_read` **in the
  Alpha container**: loads without raising, `subreddit_stats == ()`, `format_subreddit_split → ()`,
  and the age renders from the ROW as `fetched 2026-08-05 (6d ago)`. The full 1-on-1 block renders
  correctly with the per-community section absent and the small-sample caveat present.
- **`_cache_read` supplying the ROW timestamp is the right choice** — the row is what
  `settings.social_cache_ttl_days` is compared against (`social_context.py:148-161`), so rendering
  the age from anything else could show a payload age the TTL never judged.
- **`subreddit_stats` really persists as dicts.** Live: `jsonb_typeof(payload->'subreddit_stats'->0)`
  → `object`, value `{"mentions": 1455, "subreddit": "wallstreetbets", "buzz_score": 73.0, "sentiment_score": 0.003}`.
  A field reorder cannot transpose.
- **The failover's three stated refusals all hold** (probes E, and the suite's network-error /
  no-secondary / unparseable-header cases re-run here): a healthy primary never touches the reserve;
  a network error is not retried; an unparseable `remaining` is not read as exhaustion; no secondary
  means no retry. MAJOR-2 is a *fourth* case they did not enumerate, not a failure of these three.
- **The parity fingerprints are non-vacuous.** Four independent mutations in an isolated copy of the
  tree, each reverted:
  - drop the `Engagement:` render → `[social-room]` fails naming `['total_upvotes', 'unique_posts']`
  - drop the per-community loop → `[social-room]` fails
  - drop the `Snapshot:` render → `[social-room]` fails naming `['fetched_at']`
  - drop `Classified:` from `build_social_context_block` → `[social-one_on_one]` fails naming
    `['negative_count', 'neutral_count', 'positive_count']`

  All eight new `SocialSentiment` fields are rendered — no `INTENTIONALLY_OMITTED` entry was added for
  any of them, confirmed in the diff.
- **The call site is genuinely covered.** `test_the_room_fact_sheet_actually_carries_the_new_social_depth`
  drives `_format_profile` with a hand-built profile, and `test_prompt_data_parity.py`'s `env` fixture
  drives the real `room_runner._profile_for_ticker` → `_format_profile` chain. Between them the DEF238
  blind spot (builder tested, caller not) is closed.
- **The surcharge claim holds end to end.** `_resolve_and_charge_feeds` (`room_runner.py:3075-3086`)
  counts only `LiveDataState.LIVE` into `n_available` and `live_data_surcharge` returns 0 at
  `n_live_analysts <= 0` (`credit_service.py:102-110`); an all-stale feed classifies UNAVAILABLE
  (reproduced live, above), so the debit falls from `base + 2` to `base` with no second debit site.
- **The freshness premise reproduces.** `social_sentiment_cache` today: **183 rows, mean age 22.0
  days, 162 older than 7 days** — the same shape as the 175 / 20.2 d / 162 measured on 2026-08-08,
  three days on.
- **The in-container verification numbers are real.** Read NVDA's row straight out of Postgres rather
  than from the submission: `2865 | 854 | 552 | 1459 | subreddit_count 49 | 3 stat rows` — an exact
  match for the quoted figures.
- **The SNOA disclosure is accurate and does not undercut the batch.** Live now: SNOA returns 3
  headlines, newest ≈4.8 d old, so the floor does not fire on it. Stating that against interest was
  the right call. CR147's own corpus put staleness at 3/54 (5.6%), all in one convene — the floor is
  a control against a tail, and its evidence is the unit tests plus the forced live drop above, both
  of which hold.
- **Registers are consistent.** `gen_registers.py verify all` → `DEF: OK — 261 rows`, `CR: OK — 165
  rows`, exit 0, worktree clean.
- **The suite count reconciles.** My independent run:
  `1 failed, 3446 passed, 2 skipped, 13 warnings in 3255.74s`. The architect reports `3448 passed,
  1 skipped` at `e53b714a` — 3449 collected in both. The delta is exactly the load flake above
  (1 pass → fail) plus one extra skip (`…_maps_to_a_settings_field…`, which skips when
  `infra/alpha.env` is absent — gitignored, main worktree only). No test vanished, none was added.

## Recorded, not scored

- No Definition-of-Done table: `SCOPE: chunk`, and gap-fill 7 waives enforcement.
- Backend-only change (`git show --stat` on both SHAs) — no Flutter surface, so the mobile half of
  the bindings' regression row does not apply.
- The submission's suite figures are described as measured on the **shared checkout**, which is the
  DEF159 trap by name. My own count is in the run report; the architect's should be re-taken from a
  detached worktree before it is quoted as evidence again.
- `depends-on: R68-BATCH4` is itself AWAITING_FIXES (`cee6c124`, round 1); guardrail 3 would have
  capped this lane at a PROVISIONAL COMPLETE even with zero findings.

---

**VERDICT: AWAITING_FIXES (round 1)**

ROUND: 1
