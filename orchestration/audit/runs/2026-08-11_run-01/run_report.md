# Run report — 2026-08-11_run-01

Item: **R68-BATCH9**, round 1. Architect SHAs `3e08d23e` + `e53b714a` (both on `main`, both on
origin). Verdict: **AWAITING_FIXES (round 1)** — 0 BLOCKER, 4 MAJOR, 5 MINOR.
Findings in `orchestration/audit/cr/R68-BATCH9.auditor.md`.

## Setup

Audited from an isolated worktree at `b402dbea`.
`git diff --stat e53b714a..HEAD` → `docs/**`, `orchestration/audit/cr/INDEX.md`,
`R68-BATCH9.architect.md` only. **Zero source/test delta**, so every in-scope file is byte-identical
to `e53b714a`; no separate detached checkout was needed and the DEF159 trap does not apply to the
tree I measured (it does apply to the architect's own quoted counts — see "Recorded, not scored").

Delivery confirmed on origin, not assumed:

```
git branch -r --contains 3e08d23e   → origin/HEAD -> origin/main, origin/main
git branch -r --contains e53b714a   → origin/HEAD -> origin/main, origin/main
git tag --contains 3e08d23e         → alpha-2026-08-11-7, alpha-2026-08-11-8
```

Scope read at file:line, not from the diff summary: `backend/app/services/social_context.py`
(rewritten around `_to_sentiment`/`_from_payload`/`_get_with_failover`/8 new formatters),
`news_context.py:237-310` (the floor), `room_prompts.py:949-1000` + `:1149-1195` (headers + detail
lines), `room_runner.py:78-88` + `:640-660` (imports + profile population), `config.py:232-241`,
`docker-compose.yml:269-277`, `test_cr148_cr147_feed_depth.py` (new, 36 tests),
`test_prompt_data_parity.py` (+37), `test_config_compose_parity.py` (+96).

## Regression suite (independent, absolute interpreter, per BINDINGS)

```
cd backend
"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest tests/unit/ -q
1 failed, 3446 passed, 2 skipped, 13 warnings in 3255.74s (0:54:15)
FAILED tests/unit/test_def136_room_convene_does_not_block_loop.py::test_the_loop_never_stalls_while_the_builders_block
```

**The failure is machine contention, not this batch.** It is a scheduler-jitter assertion:

```
AssertionError: the event loop STALLED for 0.167s in a single gap (threshold 0.150s)
assert 0.16683012497378513 < (0.3 / 2)
```

Missed by 17 ms while the box carried ~20 concurrent pytest suites (`uptime` load average 34–52
throughout). Re-run in isolation immediately afterwards:

```
"/Volumes/…/.venv/bin/python" -m pytest tests/unit/test_def136_room_convene_does_not_block_loop.py -q
2 passed in 6.54s
```

This batch adds no async code and touches nothing on the loop path. Not counted against the lane;
recorded OUT-OF-SCOPE because a 150 ms jitter threshold on a machine that routinely runs concurrent
audits will flake again.

**The architect's count reconciles exactly.** They report `3448 passed, 1 skipped` at `e53b714a`
(3449 collected); I get `3446 passed, 1 failed, 2 skipped` (3449 collected). The delta is precisely
the flake (1 pass → fail) plus one extra skip — `test_every_env_file_key_maps_to_a_settings_field_or_is_declared_non_app`,
which skips loudly when `infra/alpha.env` is absent (gitignored, main worktree only). No test
disappeared and none was added.

Targeted files, re-run separately:

```
tests/unit/test_cr148_cr147_feed_depth.py   → 36 tests collected
tests/unit/test_config_compose_parity.py    → 8 passed, 1 skipped
tests/unit/test_prompt_data_parity.py       → 17 passed
```

The one skip is `test_every_env_file_key_maps_to_a_settings_field_or_is_declared_non_app`, which
skips loudly when `infra/alpha.env` is absent (gitignored, main worktree only) — so the env-file →
Settings direction went unchecked in this run, by design.

## Red-before-green, reproduced against the exact pre-fix state (DEF260)

Restored `SOCIAL_CACHE_TTL_DAYS: ${SOCIAL_CACHE_TTL_DAYS:-30}` in `docker-compose.yml`:

```
FAILED tests/unit/test_config_compose_parity.py::test_inline_compose_defaults_match_settings
FAILED tests/unit/test_config_compose_parity.py::test_the_social_ttl_specifically_is_not_dark
        E   AssertionError: assert '30' == '7'
2 failed, 6 passed, 1 skipped in 4.91s
```

Both new tests red, every pre-existing test still green — which is exactly the claimed proof of the
blind spot. Mutation reverted immediately; `git status --short` empty afterwards.

## Independent re-derivation of the DEF260 measurement

Script (mine, not the guard) over `docker-compose.yml` + `Settings.model_fields`:

```
total env assignments in api-alpha block: 89
self-named inline ${KEY:-X} defaults:     84
  agree (post-fix):    78
  disagree:             2   SECRET_KEY (exempt, correct), PORTFOLIO_HEALTH_TRIAL_FINDINGS (exempt)
  skipped, no scalar:   4   APPLE_AUDIENCES, GOOGLE_AUDIENCES, LEAGUE_ELIGIBLE_PLANS, PORTFOLIO_HEALTH_PLANS
not matched by the regex: 5  ENV (${AMI_ENV:?…}) + 4 literal forwards
```

Pre-fix the split is 77 / 3 / 4. The submission's "88 … 81 agreed … 7 did not" is off by 4 in the
first two figures (MINOR M1); the `7` is right. All four skipped fields are `CsvList` with a
`default_factory` and are comparable through `Settings._csv_or_json_list` — all four agree today, so
nothing is hidden now, but the skip is undeclared (MAJOR-4).

## Live verification on Alpha (`alpha-2026-08-11-8`), reproduced not accepted

```
docker ps --filter name=ami_          → ami_api_alpha Up 36 minutes (healthy), postgres/redis/tunnel up
settings.social_cache_ttl_days        → 7          (DEF260's fix is effective)
bool(settings.adanos_api_key_secondary) → True
settings.portfolio_health_trial_findings → 7        (declared 3 — MAJOR-3)
grep PORTFOLIO_HEALTH ~/ami_trade/.env → (nothing)  (so the 7 is compose's inline default, not an operator override)
_NEWS_RECENCY_FLOOR_DAYS / _MIN_MENTIONS_FOR_A_PERCENTAGE → 7 / 100
fetch_live_news('SNOA')               → 3 items, newest ≈4.8 d old (floor does NOT fire — as disclosed)
fetch_live_news('NVDA')               → 3 items, minutes old
```

Forced the floor to fire in-container (fresh `python` process, one stale item + one undated item):

```
[info] news_context_recency_floor_dropped dropped=2 floor_days=7 kept=0 ticker=ZZZZ
RESULT None
STATE LiveDataState.UNAVAILABLE
```

Backward compatibility on real production data — a genuine pre-CR148 row read through `_cache_read`
inside the container:

```
_cache_read('BAER')  → HIT True
fetched_at 1785918125 | age: fetched 2026-08-05 (6d ago)
subreddit_stats ()   | format_subreddit_split ()
build_social_context_block('BAER') renders: header with the real fetch date, mention/pattern lines,
  community line, the SMALL SAMPLE caveat — and no per-community block
```

Postgres, read directly:

```
social_sentiment_cache: 183 rows, mean age 22.0 d, 162 older than 7 d, 21 inside the new TTL
NVDA row: mentions 2865 | pos 854 | neg 552 | neu 1459 | subreddit_count 49 | 3 stat rows
jsonb_typeof(payload->'subreddit_stats'->0) = object
  {"mentions": 1455, "subreddit": "wallstreetbets", "buzz_score": 73.0, "sentiment_score": 0.003}
Adanos primary: monthly_remaining 48 / monthly_used 202 (from the live social_context_adanos_call log)
```

## Blind adversarial pass 1 — the failover (`_get_with_failover`)

Own probe against the real method, recording the key sent on each call:

```
A. primary 200 remaining=0, secondary healthy              keys=['PRIMARY', 'RESERVE']   -> status 200
B. primary 200 remaining=0, secondary network error        keys=['PRIMARY', 'RESERVE']   -> None (feed UNAVAILABLE)
C. primary 200 remaining=0, secondary 500                  keys=['PRIMARY', 'RESERVE']   -> status 500
D. primary 429 while monthly_remaining=200 (burst limit)   keys=['PRIMARY', 'RESERVE']   -> status 200
E. primary 200 remaining=180                               keys=['PRIMARY']              -> status 200
```

A–D are MAJOR-2. E and the three refusals the submission enumerates all hold.

## Blind adversarial pass 2 — is the parity guard non-vacuous?

Four mutations, each in an isolated rsync copy of the tree (the real worktree was never touched),
each reverted before the next:

| mutation | result |
|---|---|
| drop `Engagement:` from `_social_detail_lines` | `[social-room]` FAILED — `['total_upvotes', 'unique_posts']` |
| drop the per-community loop | `[social-room]` FAILED |
| drop `Snapshot:` | `[social-room]` FAILED — `['fetched_at']` |
| drop `Classified:` from `build_social_context_block` | `[social-one_on_one]` FAILED — `['negative_count', 'neutral_count', 'positive_count']` |

Non-vacuous on both surfaces. No `INTENTIONALLY_OMITTED` entry was added for any of the eight new
fields (confirmed in the diff), so all eight are genuinely rendered.

## Blind adversarial pass 3 — blast radius of the new prompt bytes

Measured through the real `_format_profile`, same profile with and without the four new keys:

```
portfolio_manager      1819 -> 2324  (+505 chars, +27.8%)
bear_researcher        1819 -> 2324  (+505, +27.8%)
aggressive_debator     1819 -> 2324  (+505, +27.8%)
neutral_debator        1819 -> 2324  (+505, +27.8%)
social_media_analyst   1266 -> 1771  (+505, +39.9%)
news_analyst           1059 -> 1059  (+0)
```

9 of 12 Room agents carry the increase (`_AGENT_LANES` firewalls only 4 analysts; everything else
gets `_ALL_DOMAINS`). This contradicts the submission's own statement and is MAJOR-1.

## Stateful-construct lifecycle (PROTOCOL requirement)

- Durable Postgres cache: TTL is read per call from `settings.social_cache_ttl_days`
  (`social_context.py:148`), so the 30 → 7 change takes effect on existing rows without a migration —
  verified live (162 of 183 rows now fall outside it). Old-shape payloads load and degrade (above).
- L1 in-process cache: 300 s, unchanged, stores the same objects. No new invalidation path.
- `_AdanosSource` singleton: `httpx.Client` is thread-safe; keys are read per call. But `fetch`
  releases `self._lock` before the DB read and the HTTP call, so concurrent misses on one ticker each
  spend a live call — pre-existing, and the shorter TTL raises its cost (recorded OUT-OF-SCOPE).
- Alpha Vantage's 30-min cache and `CachingProvider`'s 5-min news cache both sit **upstream** of the
  recency floor, so the floor is re-evaluated on every call rather than frozen into a cache entry —
  checked, and it is the right side of the boundary.

## Registers

```
python scripts/registers/gen_registers.py verify all
[verify] DEF: OK — 261 rows, content identical to live
[verify] CR:  OK — 165 rows, content identical to live
exit 0
```

## Not verified

- The response-side rates (9/18 fabricated attribution, small-sample handling, freshness reading) are
  correctly declared unmeasured by the submission and are not measurable from here — they need the
  ≥30-convene post-promotion epoch the batch already owes.
- The env-file → Settings parity direction (`infra/alpha.env` absent in this worktree; the test skips
  loudly).
- Whether MAJOR-1's +505 chars actually moves DEF258's cap-hit rate. That is a decode-side
  measurement on a fresh epoch, which is exactly the measurement the batch deferred CR147 B.2 for.
